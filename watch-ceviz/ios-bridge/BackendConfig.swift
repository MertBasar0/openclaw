import Foundation

/// Backend endpoint yapilandirmasi.
///
/// URL ve auth token artik kullaniciya ait: Ayarlar ekranindan girilir,
/// UserDefaults'ta saklanir. Bos birakilirsa gelistirme varsayilanina
/// (Mert'in tailnet mount'u) duser. Backend WATCH_CEVIZ_AUTH_TOKEN ile
/// calisiyorsa tum /api istekleri "Authorization: Bearer <token>" ister.
enum BackendConfig {
    static let urlDefaultsKey = "cvz.backendURL"
    static let tokenDefaultsKey = "cvz.backendToken"
    static let developmentBaseURL = "https://koltiginmasaustu.tail0289bf.ts.net/ceviz"

    static var baseURLString: String {
        let stored = UserDefaults.standard.string(forKey: urlDefaultsKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        var base = stored.isEmpty ? developmentBaseURL : stored
        while base.hasSuffix("/") { base.removeLast() }
        return base
    }

    static var token: String {
        UserDefaults.standard.string(forKey: tokenDefaultsKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    static func url(_ path: String) -> URL {
        URL(string: baseURLString + path) ?? URL(string: developmentBaseURL + path)!
    }

    static func applyAuth(_ request: inout URLRequest) {
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
    }

    static func request(_ path: String, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: url(path))
        request.httpMethod = method
        applyAuth(&request)
        return request
    }
}
