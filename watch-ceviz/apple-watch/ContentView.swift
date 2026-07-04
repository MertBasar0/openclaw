import SwiftUI
import WatchKit

struct ContentView: View {
    @StateObject private var sessionManager = WatchSessionManager()
    @StateObject private var recorder = AudioRecorderManager()
    @StateObject private var player = AudioPlayerManager()
    
    @State private var isRecording = false
    @State private var recordingSeconds = 0
    @State private var recordingTimer: Timer?
    
    var body: some View {
        TabView {
            // Tab 1: PTT Voice Interface
            VStack(spacing: 8) {
                // Connection Status Indicator
                HStack {
                    Circle()
                        .fill(sessionManager.isReachable ? Color.green : Color.orange)
                        .frame(width: 8, height: 8)
                    Text(sessionManager.transportStatus)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(sessionManager.isReachable ? .green : .orange)
                    Spacer()
                }
                .padding(.horizontal)

                ScrollView {
                    Text(sessionManager.responseText)
                        .font(.footnote)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxHeight: 60)
                
                if sessionManager.handoffUrl != nil {
                    HandoffOpenPanel(
                        buttonTitle: sessionManager.handoffTitle(),
                        subtitle: sessionManager.handoffSubtitle,
                        preview: sessionManager.handoffPreview,
                        isReachable: sessionManager.isReachable,
                        showsExpandedPreview: true,
                        action: {
                            sessionManager.openHandoff()
                        }
                    )
                }
                
                Spacer()
                
                Button(action: {
                    if isRecording {
                        stop()
                    } else {
                        start()
                    }
                }) {
                    Image(systemName: isRecording ? "mic.fill" : "mic")
                        .font(.system(size: 40))
                        .foregroundColor(isRecording ? .red : .white)
                        .padding()
                }
                .buttonStyle(PlainButtonStyle())
                .background(Circle().fill(isRecording ? Color.red.opacity(0.3) : Color.blue.opacity(0.3)))

                if isRecording {
                    Text("● Kayıt \(recordingSeconds) sn")
                        .font(.caption2)
                        .foregroundColor(.red)
                }

                Spacer()
                
                if !sessionManager.isReachable {
                    Text("iPhone disconnected")
                        .font(.caption2)
                        .foregroundColor(.red)
                }
            }
            .padding()
            .tabItem {
                Label("Voice", systemImage: "mic")
            }
            
            // Tab 2: Agent Monitoring
            NavigationView {
                JobsListView(sessionManager: sessionManager)
            }
            .tabItem {
                Label("Jobs", systemImage: "list.bullet")
            }
        }
        .onAppear {
            sessionManager.audioPlayerManager = player
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
            sessionManager.responseText = recorder.lastError ?? "Failed to capture audio"
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
