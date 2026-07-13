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
            lastError = "Mikrofon izni reddedilmiş. Watch ayarlarından izin ver."
        case .undetermined:
            session.requestRecordPermission { granted in
                DispatchQueue.main.async {
                    if granted {
                        self.beginRecording(session: session)
                    } else {
                        self.lastError = "Mikrofon izni verilmedi."
                    }
                }
            }
        @unknown default:
            lastError = "Bilinmeyen mikrofon izin durumu."
        }
    }

    private func beginRecording(session: AVAudioSession) {
        do {
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)

            let tempDir = FileManager.default.temporaryDirectory
            recordingURL = tempDir.appendingPathComponent("command.m4a")

            // Dusuk bitrate sart: WCSession mesaj limiti 65KB; 24kbps'de
            // ~20 sn konusma base64 ile limitin altinda kalir.
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 16000,
                AVNumberOfChannelsKey: 1,
                AVEncoderBitRateKey: 24000,
                AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
            ]

            if let url = recordingURL {
                let recorder = try AVAudioRecorder(url: url, settings: settings)
                recorder.delegate = self
                if recorder.record() {
                    audioRecorder = recorder
                } else {
                    lastError = "Kayıt başlatılamadı (recorder.record() false döndü)."
                }
            }
        } catch {
            lastError = "Kayıt kurulumu başarısız: \(error.localizedDescription)"
        }
    }

    func stopRecording() -> String? {
        guard let recorder = audioRecorder else {
            if lastError == nil {
                lastError = "Kayıt hiç başlamamıştı (izin diyaloğu sırasında durdurulmuş olabilir). Tekrar dene."
            }
            return nil
        }
        recorder.stop()
        audioRecorder = nil

        guard let url = recordingURL,
              let data = try? Data(contentsOf: url),
              !data.isEmpty else {
            if lastError == nil {
                lastError = "Ses dosyası boş ya da okunamadı."
            }
            return nil
        }

        return data.base64EncodedString()
    }
}
