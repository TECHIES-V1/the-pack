# Pack gateway — Rust/Axum read-only WS fan-out. Build context: repo root.
# Multi-stage: compile in the Rust image, ship a slim runtime. gateway/ is never modified.
#   docker build -f deploy/gateway.Dockerfile -t pack-gateway .
FROM rust:1-slim AS build
WORKDIR /src
COPY gateway/Cargo.toml gateway/Cargo.lock ./
COPY gateway/src ./src
RUN cargo build --release --locked

FROM debian:stable-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/pack-gateway /usr/local/bin/pack-gateway
EXPOSE 8080
# Reads REDIS_URL + GATEWAY_PORT from the environment (see env_file in the compose).
CMD ["pack-gateway"]
