//! Pack gateway — the realtime read path only (Doc 04 §2).
//!
//! Replays a hunt's event stream from any `from_seq`, then live-tails it to every
//! WebSocket client. ZERO agent logic. It never writes and never touches Postgres — it
//! reads Redis Streams (XRANGE for replay, XREAD for the live tail). One JSON envelope
//! format end to end, the same as the engine emits.
//!
//! Fallback (Doc 04 §2): if this gateway ever blocks us, delete it and let FastAPI serve
//! the stream directly. Nothing upstream changes.

use std::env;
use std::sync::Arc;

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{Path, Query, State};
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;
use redis::streams::{StreamRangeReply, StreamReadOptions, StreamReadReply};
use redis::AsyncCommands;
use serde::Deserialize;

#[derive(Clone)]
struct AppState {
    redis_url: Arc<String>,
}

#[derive(Debug, Deserialize)]
struct StreamParams {
    #[serde(default)]
    from_seq: i64,
}

fn stream_key(hunt_id: &str) -> String {
    format!("hunt:{hunt_id}:events")
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    let redis_url = env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379/0".into());
    let port = env::var("GATEWAY_PORT").unwrap_or_else(|_| "8080".into());

    let state = AppState {
        redis_url: Arc::new(redis_url),
    };

    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        // WS /hunts/:id/stream?from_seq=n — replays the gap, then live-tails.
        .route("/hunts/:hunt_id/stream", get(ws_handler))
        .with_state(state);

    let addr = format!("0.0.0.0:{port}");
    tracing::info!("pack-gateway listening on {addr}");
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn ws_handler(
    Path(hunt_id): Path<String>,
    Query(params): Query<StreamParams>,
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| tail(socket, hunt_id, params.from_seq, state))
}

/// Replay from `from_seq`, then live-tail. Each event is sent as a JSON text frame.
async fn tail(mut socket: WebSocket, hunt_id: String, from_seq: i64, state: AppState) {
    let key = stream_key(&hunt_id);
    let client = match redis::Client::open((*state.redis_url).clone()) {
        Ok(c) => c,
        Err(e) => {
            tracing::error!("redis open failed: {e}");
            return;
        }
    };
    let mut con = match client.get_multiplexed_async_connection().await {
        Ok(c) => c,
        Err(e) => {
            tracing::error!("redis connect failed: {e}");
            return;
        }
    };

    // --- Replay the gap (XRANGE - +) ---
    let mut last_id = "0-0".to_string();
    let range: StreamRangeReply = match con.xrange(&key, "-", "+").await {
        Ok(r) => r,
        Err(e) => {
            tracing::error!("xrange failed: {e}");
            return;
        }
    };
    for entry in range.ids {
        last_id = entry.id.clone();
        if let Some(raw) = entry.get::<String>("event") {
            if event_seq(&raw).is_none_or(|s| s >= from_seq)
                && socket.send(Message::Text(raw)).await.is_err()
            {
                return; // client gone
            }
        }
    }

    // --- Live tail (XREAD BLOCK 0) ---
    let opts = StreamReadOptions::default().block(0).count(64);
    loop {
        let reply: StreamReadReply = match con.xread_options(&[&key], &[&last_id], &opts).await {
            Ok(r) => r,
            Err(e) => {
                tracing::error!("xread failed: {e}");
                return;
            }
        };
        for stream_key in reply.keys {
            for entry in stream_key.ids {
                last_id = entry.id.clone();
                if let Some(raw) = entry.get::<String>("event") {
                    if socket.send(Message::Text(raw)).await.is_err() {
                        return;
                    }
                }
            }
        }
    }
}

/// Pull `seq` out of the envelope JSON without fully deserializing it.
fn event_seq(raw: &str) -> Option<i64> {
    serde_json::from_str::<serde_json::Value>(raw)
        .ok()
        .and_then(|v| v.get("seq").and_then(|s| s.as_i64()))
}
