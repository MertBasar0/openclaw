import SwiftUI

struct JobsListView: View {
    @ObservedObject var sessionManager: WatchSessionManager

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text("İŞLER")
                        .font(CVZ.mono(9.5, .semibold))
                        .tracking(1)
                        .foregroundColor(CVZ.accent)
                    Spacer()
                }
                .padding(.bottom, 4)

                if sessionManager.activeJobs.isEmpty {
                    Text("Aktif iş yok")
                        .font(CVZ.mono(10.5))
                        .foregroundColor(CVZ.textDim)
                        .padding(.top, 12)
                } else {
                    ForEach(sessionManager.activeJobs) { job in
                        NavigationLink(destination: JobDetailView(job: job, sessionManager: sessionManager)) {
                            jobRow(job)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(.horizontal, 2)
        }
        .background(CVZ.bg.ignoresSafeArea())
        .onAppear {
            sessionManager.fetchJobs()
        }
    }

    private func jobRow(_ job: ActiveJob) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Rectangle().fill(CVZ.lineSoft).frame(height: 1)

            Text(job.name)
                .font(CVZ.mono(11, .semibold))
                .foregroundColor(CVZ.text)
                .lineLimit(2)
                .multilineTextAlignment(.leading)

            HStack {
                CVZStatusChip(status: job.status)
                Spacer()
                Text(String(format: "%02d:%02d", job.elapsedSeconds / 60, job.elapsedSeconds % 60))
                    .font(CVZ.mono(9))
                    .foregroundColor(CVZ.textDim)
            }
        }
        .padding(.vertical, 5)
        .contentShape(Rectangle())
    }
}
