import SwiftUI

/// Konusma zinciri gezinme cubugu.
///
/// Ayni `conversation_id`'yi paylasan isler bir zincir olusturur (sesli
/// devam komutlari, onay uzerine baslatilan isler, telefondan yazilan
/// devam komutlari). Bu cubuk isin zincirdeki sirasini gosterir ve
/// onceki/sonraki ise gecmeyi, ya da listeden secmeyi saglar.
struct ChainNavigator: View {
    let currentJobId: String
    let conversationId: String
    @ObservedObject var router: AppRouter

    @State private var chain: [ActiveJob] = []

    private var index: Int? {
        chain.firstIndex { $0.id == currentJobId }
    }

    var body: some View {
        if chain.count > 1, let index {
            VStack(alignment: .leading, spacing: 8) {
                Rectangle().fill(CVZ.line).frame(height: 1)
                Text("CHAIN")
                    .font(CVZ.mono(10, .semibold))
                    .tracking(1.4)
                    .foregroundColor(CVZ.textDim)
                    .padding(.top, 10)

                HStack(spacing: 10) {
                    navButton(systemName: "chevron.left", enabled: index > 0) {
                        open(chain[index - 1])
                    }

                    Menu {
                        ForEach(Array(chain.enumerated()), id: \.element.id) { position, job in
                            Button {
                                open(job)
                            } label: {
                                Label(
                                    "\(position + 1). \(job.name)",
                                    systemImage: job.id == currentJobId ? "checkmark.circle.fill" : "circle"
                                )
                            }
                        }
                    } label: {
                        HStack(spacing: 6) {
                            Text("\(index + 1)/\(chain.count)")
                                .font(CVZ.mono(12, .semibold))
                                .foregroundColor(CVZ.accent)
                            Text(chain[index].name)
                                .font(CVZ.mono(11))
                                .foregroundColor(CVZ.textSub)
                                .lineLimit(1)
                            Image(systemName: "chevron.down")
                                .font(.system(size: 9))
                                .foregroundColor(CVZ.textDim)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.line, lineWidth: 1))
                    }

                    navButton(systemName: "chevron.right", enabled: index < chain.count - 1) {
                        open(chain[index + 1])
                    }
                }
            }
            .onAppear(perform: load)
        } else {
            EmptyView().onAppear(perform: load)
        }
    }

    private func navButton(systemName: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(enabled ? CVZ.accent : CVZ.textDim.opacity(0.4))
                .frame(width: 34, height: 34)
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(enabled ? CVZ.accent.opacity(0.6) : CVZ.line, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }

    private func open(_ job: ActiveJob) {
        guard job.id != currentJobId,
              let url = URL(string: job.deepLink ?? "ceviz://job/\(job.id)") else { return }
        _ = router.open(url: url, source: .deepLink, presentImmediately: true)
    }

    private func load() {
        guard !conversationId.isEmpty else { return }
        if DemoMode.isActive {
            chain = DemoMode.jobs.filter { ($0.conversationId ?? "") == conversationId }
            return
        }
        URLSession.shared.dataTask(with: BackendConfig.request("/api/v1/jobs/active")) { data, _, _ in
            guard let data,
                  let decoded = try? JSONDecoder().decode(ActiveJobsResponse.self, from: data) else { return }
            // Backend olusma sirasina gore donuyor; zincir sirasi bu.
            let siblings = decoded.jobs.filter { ($0.conversationId ?? "") == conversationId }
            DispatchQueue.main.async {
                chain = siblings
            }
        }.resume()
    }
}
