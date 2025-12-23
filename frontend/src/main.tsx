import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Simple ErrorBoundary to surface runtime errors in the page instead of a blank screen.
class ErrorBoundary extends React.Component<React.PropsWithChildren<{}>, { error: Error | null; info: React.ErrorInfo | null }> {
	state: { error: Error | null; info: React.ErrorInfo | null } = { error: null, info: null };

	static getDerivedStateFromError(error: Error) {
		return { error, info: null };
	}

	componentDidCatch(error: Error, info: React.ErrorInfo) {
		this.setState({ error, info });
		// also log to console (and any reporting service if configured)
		console.error("Unhandled error caught by ErrorBoundary:", error, info);
	}

	render() {
		if (this.state.error) {
			return (
				<div style={{ padding: 24, fontFamily: "system-ui,Segoe UI,Roboto,Arial", color: "#b91c1c" }}>
					<h1>Application error</h1>
					<p style={{ whiteSpace: "pre-wrap" }}>{this.state.error.message}</p>
					<details style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>{this.state.info?.componentStack}</details>
				</div>
			);
		}
	return this.props.children as React.ReactNode;
	}
}

// Global window handlers to catch errors that aren't thrown during React render (optional)
window.addEventListener("error", (ev) => {
	// show in-console for now; ErrorBoundary will catch render errors
	console.error("Window error:", ev.error || ev.message, ev);
	// try to surface by writing into the root if React hasn't mounted
	const root = document.getElementById("root");
	if (root && root.childElementCount === 0) {
		root.innerHTML = `<div style="padding:24px;font-family:system-ui,Segoe UI,Roboto,Arial;color:#b91c1c;"><h1>Window error</h1><pre>${(ev.error && ev.error.stack) || (ev.message as string)}</pre></div>`;
	}
});

window.addEventListener("unhandledrejection", (ev) => {
	console.error("Unhandled promise rejection:", ev.reason);
	const root = document.getElementById("root");
	if (root && root.childElementCount === 0) {
		root.innerHTML = `<div style="padding:24px;font-family:system-ui,Segoe UI,Roboto,Arial;color:#b91c1c;"><h1>Unhandled rejection</h1><pre>${String(ev.reason)}</pre></div>`;
	}
});

createRoot(document.getElementById("root")!).render(
	<ErrorBoundary>
		<App />
	</ErrorBoundary>
);
