import Foundation
import AVFoundation

class AudioRecorderManager: NSObject, ObservableObject, AVAudioRecorderDelegate {
    var audioRecorder: AVAudioRecorder?
    var recordingURL: URL?
    @Published var lastError: String?

    func startRecording() {
        lastError = nil
        let session = AVAudioSession.sharedInstance()
        switch session.recordPermission {
        case .granted:
            beginRecording(session: session)
        case .denied:
            lastError = NSLocalizedString("Microphone access denied. Allow it in Watch settings.", comment: "")
        case .undetermined:
            session.requestRecordPermission { granted in
                DispatchQueue.main.async {
                    if granted {
                        self.beginRecording(session: session)
                    } else {
                        self.lastError = NSLocalizedString("Microphone permission was not granted.", comment: "")
                    }
                }
            }
        @unknown default:
            lastError = NSLocalizedString("Unknown microphone permission state.", comment: "")
        }
    }

    private func beginRecording(session: AVAudioSession) {
        do {
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)

            let tempDir = FileManager.default.temporaryDirectory
            recordingURL = tempDir.appendingPathComponent("command.m4a")

            // Dusuk bitrate sart: WCSession mesaj limiti 65KB. 16kbps'de
            // 15 sn kayit ~30KB ham → ~40KB base64: her kosulda sigar,
            // "kayit cok uzun" reddi fiilen imkansizlasir.
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 16000,
                AVNumberOfChannelsKey: 1,
                AVEncoderBitRateKey: 16000,
                AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
            ]

            if let url = recordingURL {
                let recorder = try AVAudioRecorder(url: url, settings: settings)
                recorder.delegate = self
                if recorder.record() {
                    audioRecorder = recorder
                } else {
                    lastError = NSLocalizedString("Could not start recording.", comment: "")
                }
            }
        } catch {
            lastError = String(format: NSLocalizedString("Recording setup failed: %@", comment: ""), error.localizedDescription)
        }
    }

    func stopRecording() -> String? {
        guard let recorder = audioRecorder else {
            if lastError == nil {
                lastError = NSLocalizedString("Recording never started (it may have been stopped during the permission prompt). Try again.", comment: "")
            }
            return nil
        }
        recorder.stop()
        audioRecorder = nil

        guard let url = recordingURL,
              let data = try? Data(contentsOf: url),
              !data.isEmpty else {
            if lastError == nil {
                lastError = NSLocalizedString("The audio file is empty or unreadable.", comment: "")
            }
            return nil
        }

        return data.base64EncodedString()
    }
}
