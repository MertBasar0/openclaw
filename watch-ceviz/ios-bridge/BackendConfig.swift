import Foundation

/// Central backend endpoint configuration for the iPhone bridge.
///
/// The Watch Ceviz backend runs in WSL (port 8080) and is published to the
/// tailnet via Tailscale Serve:
///   https://koltiginmasaustu.tail0289bf.ts.net/ceviz -> http://127.0.0.1:8080
/// The /ceviz mount prefix is stripped by Tailscale before proxying, so paths
/// passed to `url(_:)` must start with the backend's own root (e.g. /api/v1/...).
enum BackendConfig {
    /// Base URL of the Watch Ceviz backend (no trailing slash).
    static let baseURL = URL(string: "https://koltiginmasaustu.tail0289bf.ts.net/ceviz")!

    static func url(_ path: String) -> URL {
        URL(string: baseURL.absoluteString + path)!
    }
}
