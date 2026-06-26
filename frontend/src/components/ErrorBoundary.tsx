// A top-level error boundary so one component throwing (e.g. the canvas) doesn't white-screen the
// whole app. Shows a recoverable fallback instead of a blank page.

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("Pack crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="fixed inset-0 bg-[#0F0F0F] text-white flex items-center justify-center p-6">
          <div className="max-w-md text-center flex flex-col items-center gap-4">
            <div className="text-2xl">Something broke</div>
            <p className="text-[13px] text-[#a1a1aa] m-0">
              The screen hit an error. Your hunts are safe — reload to pick back up.
            </p>
            <p className="text-[11px] text-[#52525b] font-mono break-all m-0">
              {this.state.error.message}
            </p>
            <div className="flex gap-2 mt-1">
              <button
                onClick={() => this.setState({ error: null })}
                className="rounded-lg border border-[#2a2a2a] text-[#d4d4d8] hover:text-white px-3 py-1.5 text-[13px] cursor-pointer bg-transparent"
              >
                Try again
              </button>
              <button
                onClick={() => window.location.reload()}
                className="rounded-lg bg-white text-black px-3 py-1.5 text-[13px] font-medium cursor-pointer border-none"
              >
                Reload
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
