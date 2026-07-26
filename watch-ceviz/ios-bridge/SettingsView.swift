import SwiftUI

/// Backend baglanti ayarlari: sunucu adresi + erisim token'i.
/// Kurulum scripti bu degerleri uretir; kullanici QR ile eslesir ya da girer.
struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var urlText: String = UserDefaults.standard.string(forKey: BackendConfig.urlDefaultsKey) ?? ""
    @State private var tokenText: String = BackendConfig.token
    @State private var testState: TestState = .idle
    @State private var showScanner = false

    private enum TestState: Equatable {
        case idle, testing
        case success(String)
        case failure(String)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("SETTINGS")
                    .font(CVZ.mono(12, .semibold))
                    .tracking(1.5)
                    .foregroundColor(CVZ.text)
                Spacer()
                Button(action: { dismiss() }) {
                    Text("CLOSE ✕")
                        .font(CVZ.mono(12, .semibold))
                        .foregroundColor(CVZ.accent)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .frame(height: 44)

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Button(action: { showScanner = true }) {
                        HStack {
                            Image(systemName: "qrcode.viewfinder")
                                .font(.system(size: 15))
                            Text("PAIR WITH QR")
                                .font(CVZ.mono(12, .semibold))
                            Spacer()
                        }
                        .foregroundColor(CVZ.accent)
                        .padding(.vertical, 12)
                        .padding(.horizontal, 12)
                        .frame(maxWidth: .infinity)
                        .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 6))
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.accent, lineWidth: 1))
                    }
                    .buttonStyle(.plain)

                    Text("Scan the QR printed by the install script — URL and token fill in automatically.")
                        .font(.system(size: 11.5))
                        .foregroundColor(CVZ.textDim)

                    fieldBlock(
                        label: "SERVER URL",
                        hint: "HTTPS address of the Watch Ceviz backend (from the install output).",
                        placeholder: "https://makine.tailnet.ts.net/ceviz"
                    ) {
                        TextField("", text: $urlText)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }

                    fieldBlock(
                        label: "ACCESS TOKEN",
                        hint: "The backend WATCH_CEVIZ_AUTH_TOKEN value.",
                        placeholder: "token"
                    ) {
                        SecureField("", text: $tokenText)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }

                    Button(action: runTest) {
                        Text(testState == .testing ? "TESTING_" : "TEST CONNECTION")
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
                        Text("SAVE")
                            .font(CVZ.mono(12, .semibold))
                            .foregroundColor(CVZ.accent)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 11)
                            .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 6))
                            .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.accent, lineWidth: 1))
                    }
                    .buttonStyle(.plain)

                    Text(NSLocalizedString("Empty fields fall back to the development default. The token must match WATCH_CEVIZ_AUTH_TOKEN in the backend service.", comment: ""))
                        .font(.system(size: 12))
                        .foregroundColor(CVZ.textDim)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(16)
            }
        }
        .background(CVZ.bg.ignoresSafeArea())
        .sheet(isPresented: $showScanner) {
            QRScannerView { scanned in
                showScanner = false
                if let url = URL(string: scanned), let pair = BackendConfig.applyPairing(url) {
                    urlText = pair.url
                    tokenText = pair.token
                    testState = .success(NSLocalizedString("QR scanned — remember to save", comment: ""))
                } else {
                    testState = .failure(NSLocalizedString("Invalid QR (expected ceviz://pair)", comment: ""))
                }
            }
        }
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
            testState = .failure(NSLocalizedString("Invalid URL", comment: ""))
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
                    testState = .failure(NSLocalizedString("No response", comment: ""))
                    return
                }
                switch http.statusCode {
                case 200:
                    testState = .success(NSLocalizedString("Connection OK", comment: ""))
                case 401:
                    testState = .failure(NSLocalizedString("Token rejected (401)", comment: ""))
                default:
                    testState = .failure(String(format: NSLocalizedString("Server returned %d", comment: ""), http.statusCode))
                }
            }
        }.resume()
    }

    private func save() {
        BackendConfig.setBaseURL(urlText)
        BackendConfig.setToken(tokenText)
        dismiss()
    }
}
