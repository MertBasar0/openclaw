import SwiftUI

/// Backend baglanti ayarlari: sunucu adresi + erisim token'i.
/// Kurulum scripti bu degerleri uretir; kullanici QR ile eslesir ya da girer.
struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var urlText: String = UserDefaults.standard.string(forKey: BackendConfig.urlDefaultsKey) ?? ""
    @State private var tokenText: String = BackendConfig.token
    @State private var testState: TestState = .idle
    @State private var showScanner = false
    @State private var demoOn: Bool = DemoMode.isExplicit
    @State private var connectionMethod = ConnectionMethod(rawValue: UserDefaults.standard.string(forKey: BackendConfig.connectionMethodKey) ?? "tailscale") ?? .tailscale

    private enum ConnectionMethod: String, CaseIterable {
        case tailscale, relay, manual
        var title: LocalizedStringKey { switch self { case .tailscale: "TAILSCALE"; case .relay: "SAME WI-FI"; case .manual: "MANUAL" } }
        var icon: String { switch self { case .tailscale: "lock.shield"; case .relay: "wifi"; case .manual: "slider.horizontal.3" } }
        var help: LocalizedStringKey { switch self {
        case .tailscale: "Recommended. Securely reach your OpenClaw machine from any network. Install Tailscale on the computer and phone, then run the installer in Tailscale mode."
        case .relay: "For WSL2 on the same Wi-Fi. The installer adds a Windows relay; both devices must remain on the same local network."
        case .manual: "For your own VPN, tunnel or reverse proxy. Enter its HTTPS URL and the token printed by the installer."
        } }
    }

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
                    VStack(alignment: .leading, spacing: 9) {
                        Text("HOW WILL YOU CONNECT?").font(CVZ.mono(10, .semibold)).tracking(1.4).foregroundColor(CVZ.accent)
                        HStack(spacing: 6) {
                            ForEach(ConnectionMethod.allCases, id: \.rawValue) { method in
                                Button { connectionMethod = method } label: {
                                    VStack(spacing: 5) {
                                        Image(systemName: method.icon)
                                        Text(method.title).font(CVZ.mono(9, .semibold)).lineLimit(1).minimumScaleFactor(0.7)
                                    }.foregroundColor(connectionMethod == method ? CVZ.accent : CVZ.textDim)
                                    .frame(maxWidth: .infinity).padding(.vertical, 9)
                                    .background(connectionMethod == method ? CVZ.accentBg : CVZ.panel, in: RoundedRectangle(cornerRadius: 6))
                                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(connectionMethod == method ? CVZ.accent : CVZ.line, lineWidth: 1))
                                }.buttonStyle(.plain)
                            }
                        }
                        Text(connectionMethod.help).font(.system(size: 11.5)).foregroundColor(CVZ.textDim).fixedSize(horizontal: false, vertical: true)
                        Text(connectionMethod == .tailscale ? "Run: WATCH_CEVIZ_NETWORK_MODE=tailscale bash deploy/install.sh" : connectionMethod == .relay ? "Run in WSL2: WATCH_CEVIZ_NETWORK_MODE=relay bash deploy/install.sh" : "Run: WATCH_CEVIZ_NETWORK_MODE=manual bash deploy/install.sh")
                            .font(CVZ.mono(10)).foregroundColor(CVZ.text)
                    }
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

                    VStack(alignment: .leading, spacing: 6) {
                        Toggle(isOn: $demoOn) {
                            Text("DEMO MODE")
                                .font(CVZ.mono(10, .semibold))
                                .tracking(1.4)
                                .foregroundColor(CVZ.accent)
                        }
                        .tint(CVZ.accent)
                        .onChange(of: demoOn) { newValue in
                            DemoMode.setExplicit(newValue)
                        }
                        Text("Show sample data without a backend. Useful before pairing, and required for app review.")
                            .font(.system(size: 11.5))
                            .foregroundColor(CVZ.textDim)
                            .fixedSize(horizontal: false, vertical: true)
                    }

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
                    if let method = BackendConfig.pairingMethod(url), let parsed = ConnectionMethod(rawValue: method) {
                        connectionMethod = parsed
                    }
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
        if demoOn {
            testState = .success(NSLocalizedString("Demo mode — sample data", comment: ""))
            return
        }
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
        UserDefaults.standard.set(connectionMethod.rawValue, forKey: BackendConfig.connectionMethodKey)
        dismiss()
    }
}
