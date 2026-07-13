import SwiftUI
import UIKit

// Telefon tarafinda watch eriselebilirlik durumu (ust bar gostergesi icin).
final class WatchLinkStatus: ObservableObject {
    static let shared = WatchLinkStatus()
    @Published var isReachable = false
    private init() {}
}

// Notr meta cipi: ONEM:ORTA, sure vb.
struct CVZMetaChip: View {
    let text: String

    var body: some View {
        Text(text)
            .font(CVZ.mono(10.5, .semibold))
            .foregroundColor(CVZ.textDim)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 4))
    }
}

// Cizgi-ayracli rapor bolumu: ust 1px cizgi + eyebrow + govde. Kart yok.
struct CVZSectionView: View {
    let eyebrow: String
    let content: String
    var emphasized: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Rectangle().fill(CVZ.line).frame(height: 1)
            Text(eyebrow)
                .font(CVZ.mono(10, .semibold))
                .tracking(1.4)
                .foregroundColor(CVZ.accent)
                .padding(.top, 10)
            Text(content)
                .font(.system(size: 13.5))
                .lineSpacing(6)
                .foregroundColor(emphasized ? CVZ.text : CVZ.textSub)
                .frame(maxWidth: .infinity, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// Home devam karti
struct CVZContinuationCard: View {
    let metaText: String
    let title: String
    let summary: String?
    let buttonTitle: String
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text("WATCH → IPHONE")
                    .font(CVZ.mono(9.5, .semibold))
                    .foregroundColor(CVZ.accent)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 4))
                Text(metaText)
                    .font(CVZ.mono(10.5))
                    .foregroundColor(CVZ.textDim)
                    .lineLimit(1)
                Spacer()
            }

            Text(title)
                .font(.system(size: 17, weight: .bold))
                .foregroundColor(CVZ.text)

            if let summary, !summary.isEmpty {
                Text(summary)
                    .font(CVZ.mono(12))
                    .lineSpacing(5)
                    .foregroundColor(CVZ.textSub)
                    .lineLimit(4)
            }

            Button(action: action) {
                Text(buttonTitle)
                    .font(CVZ.mono(12, .semibold))
                    .foregroundColor(CVZ.accent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 11)
                    .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.accent, lineWidth: 1))
            }
            .buttonStyle(.plain)
        }
        .padding(14)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(CVZ.line, lineWidth: 1))
    }
}

// SONRAKI AKSIYONLAR — terminal aksiyon satirlari + toast geri bildirimi
struct CVZActionsView: View {
    let actions: [NextActionPayload]
    var jobId: String = ""
    @ObservedObject var router: AppRouter
    let onFeedback: (String) -> Void

    // "Open on Phone" deeplink'i zaten telefonda acik olan raporda anlamsiz.
    private var visibleActions: [NextActionPayload] {
        actions.filter { $0.id != "open-on-phone" }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Rectangle().fill(CVZ.line).frame(height: 1)
            Text("SONRAKİ AKSİYONLAR")
                .font(CVZ.mono(10, .semibold))
                .tracking(1.4)
                .foregroundColor(CVZ.textDim)
                .padding(.top, 10)

            ForEach(visibleActions) { action in
                Button(action: { handleAction(action) }) {
                    actionRow(action)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func isPrimary(_ action: NextActionPayload) -> Bool {
        action.kind == "api_call"
    }

    private func actionRow(_ action: NextActionPayload) -> some View {
        HStack {
            Text(action.label.uppercased())
                .font(CVZ.mono(12, .semibold))
                .foregroundColor(isPrimary(action) ? CVZ.accent : CVZ.text)
                .multilineTextAlignment(.leading)
            Spacer()
            Image(systemName: glyph(for: action.kind))
                .font(.system(size: 12))
                .foregroundColor(isPrimary(action) ? CVZ.accent : CVZ.textDim)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(
            isPrimary(action) ? CVZ.accentBg : Color.clear,
            in: RoundedRectangle(cornerRadius: 6)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(isPrimary(action) ? CVZ.accent : CVZ.line, lineWidth: 1)
        )
        .contentShape(Rectangle())
    }

    private func glyph(for kind: String) -> String {
        switch kind {
        case "deep_link", "deeplink", "open_url": return "arrow.up.right"
        case "copy": return "doc.on.doc"
        case "api_call": return "bolt.fill"
        case "hint": return "lightbulb"
        default: return "arrow.forward"
        }
    }

    private func handleAction(_ action: NextActionPayload) {
        switch action.kind {
        case "deep_link", "deeplink":
            if let target = action.target, let url = URL(string: target) {
                _ = router.open(url: url, source: .deepLink, presentImmediately: true)
            } else {
                onFeedback("✕ Geçersiz bağlantı")
            }
        case "open_url":
            if let target = action.target, let url = URL(string: target) {
                UIApplication.shared.open(url)
            } else {
                onFeedback("✕ Geçersiz URL")
            }
        case "copy":
            if let target = action.target, !target.isEmpty {
                UIPasteboard.general.string = target
                onFeedback("✓ Panoya kopyalandı")
            } else {
                onFeedback("✕ Kopyalanacak içerik yok")
            }
        case "api_call":
            performApiCall(action)
        case "hint":
            // Oneri metni tiklanabilir: dogrudan OpenClaw'a yeni komut olarak gider.
            sendSuggestionAsCommand(action.label)
        default:
            onFeedback("→ \(action.label)")
        }
    }

    private func sendSuggestionAsCommand(_ text: String) {
        var request = BackendConfig.request("/api/v1/shortcuts/command", method: "POST")
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        // continue_job_id: backend onceki isin baglamini prompt'a ekler;
        // oneri metni tek basina anlamsiz kalmasin.
        var body: [String: Any] = ["text": text]
        if !jobId.isEmpty { body["continue_job_id"] = jobId }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        onFeedback("→ OpenClaw'a gönderiliyor…")

        Task {
            do {
                let (_, response) = try await URLSession.shared.data(for: request)
                guard let http = response as? HTTPURLResponse,
                      (200...299).contains(http.statusCode) else {
                    throw URLError(.badServerResponse)
                }
                await MainActor.run {
                    onFeedback("✓ Öneri iş olarak başlatıldı — SON İŞLER'de görünecek")
                }
            } catch {
                await MainActor.run {
                    onFeedback("✕ Gönderilemedi: \(error.localizedDescription)")
                }
            }
        }
    }

    private func performApiCall(_ action: NextActionPayload) {
        guard let target = action.target, !target.isEmpty,
              let url = resolvedApiCallURL(from: target) else {
            onFeedback("✕ Eksik/geçersiz aksiyon hedefi")
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        BackendConfig.applyAuth(&request)

        Task {
            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse,
                      (200...299).contains(httpResponse.statusCode) else {
                    throw URLError(.badServerResponse)
                }

                let payload = (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]

                await MainActor.run {
                    if let deepLinkValue = payload["deep_link"] as? String,
                       let url = URL(string: deepLinkValue) {
                        _ = router.open(url: url, source: .deepLink, presentImmediately: true)
                    }

                    if let error = payload["error"] as? String, !error.isEmpty {
                        onFeedback("✕ \(error)")
                    } else if let summary = payload["summary"] as? String, !summary.isEmpty {
                        onFeedback("✓ \(summary)")
                    } else {
                        onFeedback("✓ \(action.label)")
                    }
                }
            } catch {
                await MainActor.run {
                    onFeedback("✕ Aksiyon başarısız: \(error.localizedDescription)")
                }
            }
        }
    }

    private func resolvedApiCallURL(from target: String) -> URL? {
        if target.hasPrefix("http://") || target.hasPrefix("https://") {
            return URL(string: target)
        }
        if target.hasPrefix("/") {
            return BackendConfig.url(target)
        }
        return URL(string: target)
    }
}
