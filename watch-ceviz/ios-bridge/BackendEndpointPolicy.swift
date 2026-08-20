import Foundation

/// Release networking policy: HTTPS is accepted everywhere. Plain HTTP is
/// limited to the explicit same-Wi-Fi relay mode and local/private hosts.
enum BackendEndpointPolicy {
    static func isAllowed(_ value: String, connectionMethod: String) -> Bool {
        guard let components = URLComponents(string: value),
              let scheme = components.scheme?.lowercased(),
              let host = components.host?.lowercased(),
              components.user == nil,
              components.password == nil else { return false }

        if scheme == "https" { return true }
        guard scheme == "http", connectionMethod == "relay" else { return false }
        return isLocalHost(host)
    }

    private static func isLocalHost(_ host: String) -> Bool {
        if host == "localhost" || host.hasSuffix(".local") { return true }
        if host == "::1" || host.hasPrefix("fe80:") || host.hasPrefix("fc") || host.hasPrefix("fd") {
            return true
        }

        let parts = host.split(separator: ".").compactMap { Int($0) }
        guard parts.count == 4, parts.allSatisfy({ (0...255).contains($0) }) else { return false }
        switch (parts[0], parts[1]) {
        case (10, _), (127, _):
            return true
        case (172, 16...31):
            return true
        case (192, 168):
            return true
        case (169, 254):
            return true
        default:
            return false
        }
    }
}
