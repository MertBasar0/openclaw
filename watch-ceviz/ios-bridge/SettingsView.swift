import SwiftUI

/// Backend baglanti ayarlari: sunucu adresi + erisim token'i.
/// Kurulum scripti bu degerleri uretir; kullanici buraya girer.
struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var urlText: String = UserDefaults.standard.string(forKey: BackendConfig.urlDefaultsKey) ?? ""
    @State private var tokenText: String = UserDefaults.standard.string(forKey: BackendConfig.tokenDefaultsKey) ?? ""
    @State private var testState: TestState = .idle

    private enum TestState: Equatable {
        case idle, testing
        case success(String)
        case failure(String)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("AYARLAR")
                    .font(CVZ.mono(12, .semibold))
                    .tracking(1.5)
                    .foregroundColor(CVZ.text)
                Spacer()
                Button(action: { dismiss() }) {
                    Text("KAPAT ✕")
                        .font(CVZ.mono(12, .semibold))
                        .foregroundColor(CVZ.accent)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .frame(height: 44)

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    fieldBlock(
                        label: "SUNUCU ADRESİ",
                        hint: "Watch Ceviz backend'inin HTTPS adresi (kurulum çıktısındaki URL).",
                        placeholder: "https://makine.tailnet.ts.net/ceviz"
                    ) {
                        TextField("", text: $urlText)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }

                    fieldBlock(
                        label: "ERİŞİM TOKEN'I",
                        hint: "Backend'in WATCH_CEVIZ_AUTH_TOKEN değeri.",
                        placeholder: "token"
                    ) {
                        SecureField("", text: $tokenText)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }

                    Button(action: runTest) {
                        Text(testState == .testing ? "TEST EDİLİYOR_" : "BAĞLANTIYI TEST ET")
                            .font(CVZ.mono(12, .semibold))
                            .foregroundColor(CVZ.text)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 11)
                            .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.line, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .disabled(testState == .testing)

                    switch testState {
                    case .success(let message):
                        Text("✓ \(message)")
                            .font(CVZ.mono(11))
                            .foregroundColor(CVZ.ok)
                    case .failure(let message):
                        Text("✕ \(message)")
                            .font(CVZ.mono(11))
                            .foregroundColor(CVZ.err)
                    default:
                        EmptyView()
                    }

                    Button(action: save) {
                        Text("KAYDET")
                            .font(CVZ.mono(12, .semibold))
                            .foregroundColor(CVZ.accent)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 11)
                            .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 6))
                            .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.accent, lineWidth: 1))
                    }
                    .buttonStyle(.plain)

                    Text("Boş bırakılan alanlar geliştirme varsayılanına döner. Token, backend systemd servisindeki WATCH_CEVIZ_AUTH_TOKEN değeriyle aynı olmalı.")
                        .font(.system(size: 12))
                        .foregroundColor(CVZ.textDim)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(16)
            }
        }
        .background(CVZ.bg.ignoresSafeArea())
    }

    private func fieldBlock<Field: View>(
        label: String,
        hint: String,
        placeholder: String,
        @ViewBuilder field: () -> Field
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(CVZ.mono(10, .semibold))
                .tracking(1.4)
                .foregroundColor(CVZ.accent)
            field()
                .font(CVZ.mono(13))
                .foregroundColor(CVZ.text)
                .padding(10)
                .background(CVZ.panel, in: RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.line, lineWidth: 1))
            Text(hint)
                .font(.system(size: 11.5))
                .foregroundColor(CVZ.textDim)
        }
    }

    private var candidateBaseURL: String {
        var base = urlText.trimmingCharacters(in: .whitespacesAndNewlines)
        if base.isEmpty { base = BackendConfig.developmentBaseURL }
        while base.hasSuffix("/") { base.removeLast() }
        return base
    }

    private func runTest() {
        guard let url = URL(string: candidateBaseURL + "/api/v1/jobs/active") else {
            testState = .failure("Geçersiz adres")
            return
        }
        testState = .testing
        var request = URLRequest(url: url)
        request.timeoutInterval = 8
        let token = tokenText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        URLSession.shared.dataTask(with: request) { _, response, error in
            DispatchQueue.main.async {
                if let error {
                    testState = .failure(error.localizedDescription)
                    return
                }
                guard let http = response as? HTTPURLResponse else {
                    testState = .failure("Yanıt alınamadı")
                    return
                }
                switch http.statusCode {
                case 200:
                    testState = .success("Bağlantı tamam")
                case 401:
                    testState = .failure("Token reddedildi (401)")
                default:
                    testState = .failure("Sunucu \(http.statusCode) döndü")
                }
            }
        }.resume()
    }

    private func save() {
        UserDefaults.standard.set(urlText.trimmingCharacters(in: .whitespacesAndNewlines), forKey: BackendConfig.urlDefaultsKey)
        UserDefaults.standard.set(tokenText.trimmingCharacters(in: .whitespacesAndNewlines), forKey: BackendConfig.tokenDefaultsKey)
        dismiss()
    }
}
