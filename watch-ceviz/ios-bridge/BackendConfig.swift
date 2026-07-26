import Foundation

/// Backend endpoint yapilandirmasi.
///
/// URL ve auth token kullaniciya ait: Ayarlar ekranindan girilir ya da QR
/// ile eslesir. Token KEYCHAIN'de saklanir (uygulama silinse bile kalir);
/// URL UserDefaults'ta. Bos birakilirsa gelistirme varsayilanina duser.
/// Backend WATCH_CEVIZ_AUTH_TOKEN ile calisiyorsa tum /api istekleri
/// "Authorization: Bearer <token>" ister.
enum BackendConfig {
    static let urlDefaultsKey = "cvz.backendURL"
    static let tokenDefaultsKey = "cvz.backendToken"   // eski UserDefaults konumu (migrasyon)
    static let tokenKeychainKey = "backendToken"
    static let developmentBaseURL = "https://koltiginmasaustu.tail0289bf.ts.net/ceviz"

    static var baseURLString: String {
        let stored = UserDefaults.standard.string(forKey: urlDefaultsKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        var base = stored.isEmpty ? developmentBaseURL : stored
        while base.hasSuffix("/") { base.removeLast() }
        return base
    }

    static func setBaseURL(_ value: String) {
        UserDefaults.standard.set(value.trimmingCharacters(in: .whitespacesAndNewlines), forKey: urlDefaultsKey)
    }

    static var token: String {
        if let kc = KeychainStore.get(tokenKeychainKey) {
            return kc.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        // Eski surumden migrasyon: UserDefaults'taki token'i Keychain'e tasi.
        if let legacy = UserDefaults.standard.string(forKey: tokenDefaultsKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines), !legacy.isEmpty {
            KeychainStore.set(legacy, for: tokenKeychainKey)
            UserDefaults.standard.removeObject(forKey: tokenDefaultsKey)
            return legacy
        }
        return ""
    }

    static func setToken(_ value: String) {
        KeychainStore.set(value.trimmingCharacters(in: .whitespacesAndNewlines), for: tokenKeychainKey)
    }

    /// ceviz://pair?u=<url>&t=<token> eslesme baglantisini isle. Basarili
    /// oldu ise (url, token) doner.
    @discardableResult
    static func applyPairing(_ url: URL) -> (url: String, token: String)? {
        guard url.scheme == "ceviz", url.host == "pair",
              let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let items = comps.queryItems else { return nil }
        let u = items.first(where: { $0.name == "u" })?.value ?? ""
        let t = items.first(where: { $0.name == "t" })?.value ?? ""
        guard !u.isEmpty, !t.isEmpty else { return nil }
        setBaseURL(u)
        setToken(t)
        return (u, t)
    }

    static func url(_ path: String) -> URL {
        URL(string: baseURLString + path) ?? URL(string: developmentBaseURL + path)!
    }

    static func applyAuth(_ request: inout URLRequest) {
        let t = token
        if !t.isEmpty {
            request.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        }
    }

    static func request(_ path: String, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: url(path))
        request.httpMethod = method
        applyAuth(&request)
        return request
    }
}
