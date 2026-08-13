import SwiftUI
import WatchKit

struct ContentView: View {
    @StateObject private var sessionManager = WatchSessionManager()
    @StateObject private var recorder = AudioRecorderManager()
    @StateObject private var player = AudioPlayerManager()

    @Environment(\.scenePhase) private var scenePhase

    @State private var isRecording = false
    @State private var recordingSeconds = 0
    @State private var recordingTimer: Timer?
    @State private var pulse = false
    @State private var recordingWasCancelled = false

    private enum VoiceStage {
        case idle, recording, processing, result
    }

    private var stage: VoiceStage {
        if isRecording { return .recording }
        if sessionManager.isProcessing { return .processing }
        if sessionManager.responseText == "Ready" || sessionManager.responseText.isEmpty { return .idle }
        return .result
    }

    var body: some View {
        TabView {
            voiceTab
                .tabItem { Label("Voice", systemImage: "mic") }

            NavigationView {
                JobsListView(sessionManager: sessionManager)
            }
            .tabItem { Label("Jobs", systemImage: "list.bullet") }
        }
        .background(CVZ.bg)
        .onAppear {
            sessionManager.audioPlayerManager = player
            sessionManager.resumeResultPollingIfNeeded()
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active {
                sessionManager.resumeResultPollingIfNeeded()
            }
        }
    }

    private var voiceTab: some View {
        VStack(spacing: 6) {
            statusRow

            switch stage {
            case .recording:
                recordingArea
            case .processing:
                processingArea
            default:
                lastAnswerSection
                if sessionManager.handoffUrl != nil {
                    handoffPanel
                }
            }

            Spacer(minLength: 2)

            micButton

            // Devam penceresi acikken rozet goster; süre dolunca kendiliginden söner.
            TimelineView(.periodic(from: .now, by: 10)) { context in
                if stage != .recording, stage != .processing,
                   let last = sessionManager.lastResultAt,
                   context.date.timeIntervalSince(last) < WatchSessionManager.continuationWindow {
                    Text("↩ follow-up")
                        .font(CVZ.mono(9, .semibold))
                        .foregroundColor(CVZ.accent)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 3))
                } else {
                    Text(hintText)
                        .font(CVZ.mono(9))
                        .foregroundColor(CVZ.textDim)
                }
            }
        }
        .padding(.horizontal, 4)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(CVZ.bg.ignoresSafeArea())
    }

    private var statusRow: some View {
        HStack {
            if isRecording {
                Text("● REC")
                    .font(CVZ.mono(9.5, .semibold))
                    .foregroundColor(CVZ.err)
            } else {
                Text(sessionManager.isReachable ? "▮ LINKED" : "▮ NO LINK")
                    .font(CVZ.mono(9.5, .semibold))
                    .foregroundColor(sessionManager.isReachable ? CVZ.accent : CVZ.err)
            }
            Spacer()
            Text("JOBS →")
                .font(CVZ.mono(9.5, .semibold))
                .foregroundColor(CVZ.textDim)
        }
        .padding(.top, 2)
    }

    private var lastAnswerSection: some View {
        VStack(alignment: .leading, spacing: 3) {
            Rectangle().fill(CVZ.line).frame(height: 1)
            Text("LAST REPLY")
                .font(CVZ.mono(8.5, .semibold))
                .tracking(1)
                .foregroundColor(CVZ.accent)
            ScrollView {
                Text(stage == .idle ? NSLocalizedString("No commands yet — tap the mic and speak.", comment: "") : sessionManager.responseText)
                    .font(CVZ.mono(11))
                    .lineSpacing(3)
                    .foregroundColor(stage == .idle ? CVZ.textDim : CVZ.text)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(minHeight: 54, maxHeight: 92)
        }
    }

    private var handoffPanel: some View {
        Button(action: { sessionManager.openHandoff() }) {
            HStack(spacing: 5) {
                Image(systemName: sessionManager.handoffState == .ready ? "iphone.and.arrow.forward" : "checkmark")
                Text(sessionManager.handoffState == .ready
                     ? NSLocalizedString("OPEN DETAILS", comment: "")
                     : NSLocalizedString("SENT TO IPHONE", comment: ""))
                Spacer()
                Image(systemName: "chevron.right")
            }
            .font(CVZ.mono(9.5, .semibold))
            .foregroundColor(CVZ.accent)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 5))
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(CVZ.accent, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .disabled(sessionManager.handoffState != .ready)
    }

    private var recordingArea: some View {
        VStack(spacing: 8) {
            Spacer(minLength: 4)
            HStack(spacing: 4) {
                ForEach(0..<5, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 2)
                        .fill(CVZ.err)
                        .frame(width: 5, height: 30)
                        .scaleEffect(y: pulse ? 1.0 : 0.35, anchor: .center)
                        .animation(
                            .easeInOut(duration: 1.0).repeatForever(autoreverses: true).delay(Double(i) * 0.15),
                            value: pulse
                        )
                }
            }
            Text(String(format: "%d:%02d", recordingSeconds / 60, recordingSeconds % 60))
                .font(CVZ.mono(22, .bold))
                .foregroundColor(CVZ.err)
            Spacer(minLength: 0)
        }
        .onAppear { pulse = true }
        .onDisappear { pulse = false }
    }

    private var processingArea: some View {
        VStack(spacing: 8) {
            Spacer(minLength: 6)
            ProgressView()
                .tint(CVZ.accent)
                .scaleEffect(1.2)
            Text("THINKING_")
                .font(CVZ.mono(10.5, .semibold))
                .foregroundColor(CVZ.accent)
                .opacity(pulse ? 1 : 0.35)
                .animation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true), value: pulse)
            Spacer(minLength: 0)
        }
        .onAppear { pulse = true }
        .onDisappear { pulse = false }
    }

    private var micButton: some View {
        HStack(spacing: 18) {
            if isRecording {
                Button(action: cancelRecording) {
                    Image(systemName: "xmark")
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundColor(CVZ.err)
                        .frame(width: 50, height: 50)
                        .background(Circle().fill(CVZ.err.opacity(0.12)))
                        .overlay(Circle().stroke(CVZ.err, lineWidth: 1.5))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("Discard recording"))
            }

            Button(action: { isRecording ? stop() : start() }) {
                Image(systemName: isRecording ? "arrow.up" : "mic")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundColor(CVZ.accent)
                    .frame(width: 58, height: 58)
                    .background(Circle().fill(CVZ.panel))
                    .overlay(Circle().stroke(CVZ.accent, lineWidth: 1.5))
            }
            .buttonStyle(.plain)
            .accessibilityLabel(
                Text(NSLocalizedString(
                    isRecording ? "Send recording" : "Start recording", comment: ""
                ))
            )
        }
        .disabled(stage == .processing)
        .opacity(stage == .processing ? 0.35 : 1)
    }

    private var hintText: String {
        if recordingWasCancelled { return NSLocalizedString("Recording discarded", comment: "") }
        switch stage {
        case .recording: return NSLocalizedString("tap to finish", comment: "")
        case .processing: return NSLocalizedString("working…", comment: "")
        default: return NSLocalizedString("PTT · tap, speak", comment: "")
        }
    }

    private func start() {
        recordingWasCancelled = false
        isRecording = true
        // Bilek indiginde watchOS uygulamayi askiya alip kaydi ~1 sn'de
        // kesiyor; kayit boyunca extended runtime ile uyanik tut.
        sessionManager.startExtendedSession()
        WKInterfaceDevice.current().play(.start)
        recorder.startRecording()
        recordingSeconds = 0
        recordingTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            recordingSeconds += 1
            // WCSession 65KB mesaj limiti: kayit uzarsa otomatik bitir
            // (16kbps'te 15 sn her kosulda limite sigar).
            if recordingSeconds >= 15 {
                stop()
            }
        }
    }

    private func stop() {
        isRecording = false
        recordingTimer?.invalidate()
        recordingTimer = nil
        WKInterfaceDevice.current().play(.stop)
        if let base64Audio = recorder.stopRecording() {
            sessionManager.sendAudioCommand(audioBase64: base64Audio)
        } else {
            sessionManager.responseText = recorder.lastError ?? NSLocalizedString("Could not capture audio", comment: "")
        }
    }

    private func cancelRecording() {
        isRecording = false
        recordingTimer?.invalidate()
        recordingTimer = nil
        recordingSeconds = 0
        recorder.cancelRecording()
        sessionManager.stopExtendedSession()
        recordingWasCancelled = true
        WKInterfaceDevice.current().play(.click)
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
