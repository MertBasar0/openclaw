import SwiftUI
import WatchKit

struct ContentView: View {
    @StateObject private var sessionManager = WatchSessionManager()
    @StateObject private var recorder = AudioRecorderManager()
    @StateObject private var player = AudioPlayerManager()

    @State private var isRecording = false
    @State private var recordingSeconds = 0
    @State private var recordingTimer: Timer?
    @State private var pulse = false

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
                .tabItem { Label("Ses", systemImage: "mic") }

            NavigationView {
                JobsListView(sessionManager: sessionManager)
            }
            .tabItem { Label("İşler", systemImage: "list.bullet") }
        }
        .background(CVZ.bg)
        .onAppear {
            sessionManager.audioPlayerManager = player
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

            Text(hintText)
                .font(CVZ.mono(9))
                .foregroundColor(CVZ.textDim)
        }
        .padding(.horizontal, 4)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(CVZ.bg.ignoresSafeArea())
    }

    private var statusRow: some View {
        HStack {
            if isRecording {
                Text("● KAYIT")
                    .font(CVZ.mono(9.5, .semibold))
                    .foregroundColor(CVZ.err)
            } else {
                Text(sessionManager.isReachable ? "▮ BAĞLI" : "▮ BAĞLI DEĞİL")
                    .font(CVZ.mono(9.5, .semibold))
                    .foregroundColor(sessionManager.isReachable ? CVZ.accent : CVZ.err)
            }
            Spacer()
            Text("İŞLER →")
                .font(CVZ.mono(9.5, .semibold))
                .foregroundColor(CVZ.textDim)
        }
        .padding(.top, 2)
    }

    private var lastAnswerSection: some View {
        VStack(alignment: .leading, spacing: 3) {
            Rectangle().fill(CVZ.line).frame(height: 1)
            Text("SON CEVAP")
                .font(CVZ.mono(8.5, .semibold))
                .tracking(1)
                .foregroundColor(CVZ.accent)
            ScrollView {
                Text(stage == .idle ? "Henüz komut yok — mikrofona dokunup konuşun." : sessionManager.responseText)
                    .font(CVZ.mono(11))
                    .lineSpacing(3)
                    .foregroundColor(stage == .idle ? CVZ.textDim : CVZ.text)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxHeight: 62)
        }
    }

    private var handoffPanel: some View {
        VStack(spacing: 3) {
            Button(action: { sessionManager.openHandoff() }) {
                HStack {
                    Text("→ IPHONE'DA AÇ")
                        .font(CVZ.mono(10.5, .semibold))
                        .foregroundColor(CVZ.accent)
                    Spacer()
                    Text("rapor hazır")
                        .font(CVZ.mono(9))
                        .foregroundColor(CVZ.textDim)
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 8)
                .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.accent, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .disabled(!sessionManager.isReachable)

            Text(sessionManager.isReachable ? "✓ bilek titreşimi gönderildi" : "iPhone erişilebilir olmalı")
                .font(CVZ.mono(9))
                .foregroundColor(CVZ.textDim)
        }
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
            Text("YORUMLANIYOR_")
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
        Button(action: {
            if isRecording { stop() } else { start() }
        }) {
            Image(systemName: isRecording ? "mic.fill" : "mic")
                .font(.system(size: 24))
                .foregroundColor(isRecording ? CVZ.err : CVZ.accent)
                .frame(width: 58, height: 58)
                .background(
                    Circle().fill(isRecording ? CVZ.err.opacity(0.16) : CVZ.panel)
                )
                .overlay(
                    Circle().stroke(isRecording ? CVZ.err : CVZ.accent, lineWidth: 1.5)
                )
        }
        .buttonStyle(.plain)
        .disabled(stage == .processing)
        .opacity(stage == .processing ? 0.35 : 1)
    }

    private var hintText: String {
        switch stage {
        case .recording: return "bitirmek için dokun"
        case .processing: return "işleniyor…"
        default: return "PTT · dokun, konuş"
        }
    }

    private func start() {
        isRecording = true
        // Bilek indiginde watchOS uygulamayi askiya alip kaydi ~1 sn'de
        // kesiyor; kayit boyunca extended runtime ile uyanik tut.
        sessionManager.startExtendedSession()
        WKInterfaceDevice.current().play(.start)
        recorder.startRecording()
        recordingSeconds = 0
        recordingTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            recordingSeconds += 1
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
            sessionManager.responseText = recorder.lastError ?? "Ses yakalanamadı"
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
