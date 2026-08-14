import Foundation
import WatchConnectivity
import Combine
import WatchKit

struct QueuedCommand: Codable, Identifiable { 
    let id: String 
    let audioData: String 
    let timestamp: Date 
    var retryCount: Int 
} 


class WatchSessionManager: NSObject, ObservableObject, WCSessionDelegate, WKExtendedRuntimeSessionDelegate {
    @Published var isReachable = false
    @Published var responseText = "Ready"
    @Published var handoffUrl: String? = nil
    @Published var handoffJobId: String? = nil
    @Published var activeJobs: [ActiveJob] = []
    @Published var pendingCommands: [QueuedCommand] = []
    @Published var transportStatus: String = "Disconnected"
    @Published var isProcessing = false
    /// Son sonucun geldigi an. Backend, 180 sn icindeki yeni komutu ayni
    /// konusmanin devami sayiyor; saat bunu rozetle gosterir.
    @Published var lastResultAt: Date?

    static let continuationWindow: TimeInterval = 180
    @Published var handoffState: HandoffState = .idle
    private var isDrainingCommandQueue = false
    @Published var handoffPreview: HandoffPreview? = nil

    private var extendedSession: WKExtendedRuntimeSession?
    private var resultPollTimer: Timer?
    private var resultPollDeadline: Date?
    private var pollingJobId: String?
    private var pollErrorCount = 0
    private var sendGeneration = 0
    private static let pendingJobDefaultsKey = "cvz.pendingJobId"
    private static let pendingJobAtDefaultsKey = "cvz.pendingJobAt"
    /// Bekleyen is kaydi bu sureden eskiyse anlamsizdir; diriltmeyiz.
    private static let pendingJobMaxAge: TimeInterval = 15 * 60

    enum HandoffState: Equatable {
        case idle
        case ready
        case pendingOnPhone
        case openedOnPhone
    }

    func startExtendedSession() {
        if extendedSession == nil || extendedSession?.state == .invalid {
            extendedSession = WKExtendedRuntimeSession()
            extendedSession?.delegate = self
            extendedSession?.start()
            print("Extended runtime session started for data transfer.")
        }
    }

    func stopExtendedSession() {
        extendedSession?.invalidate()
        extendedSession = nil
        print("Extended runtime session stopped.")
    }

    // WKExtendedRuntimeSessionDelegate methods
    func extendedRuntimeSession(_ extendedRuntimeSession: WKExtendedRuntimeSession, didInvalidateWith reason: WKExtendedRuntimeSessionInvalidationReason, error: Error?) {
        print("Extended session invalidated: \(reason)")
        extendedSession = nil
    }

    func extendedRuntimeSessionDidStart(_ extendedRuntimeSession: WKExtendedRuntimeSession) {
        print("Extended session did start")
    }

    func extendedRuntimeSessionWillExpire(_ extendedRuntimeSession: WKExtendedRuntimeSession) {
        print("Extended session will expire")
    }

    func handoffTitle(for handoffUrl: String? = nil) -> String {
        guard let url = handoffUrl ?? self.handoffUrl,
              let parsedUrl = URL(string: url),
              let route = parsedUrl.host,
              route == "job",
              parsedUrl.pathComponents.count > 1 else {
            return "Continue on Phone"
        }

        return "Open job \(parsedUrl.pathComponents[1]) on Phone"
    }

    var handoffSubtitle: String {
        switch handoffState {
        case .idle:
            return ""
        case .ready:
            return isReachable ? "Open the fuller phone view shown below." : "iPhone must be reachable first."
        case .pendingOnPhone:
            return "Queued on iPhone. Bring the app to the foreground to continue."
        case .openedOnPhone:
            return "The report is now open on iPhone."
        }
    }
    
    // Add reference to audio player to play tts immediately upon response
    var audioPlayerManager: AudioPlayerManager?

    private func reportMeta(from rawValue: Any?) -> ReportMeta? {
        guard let rawMeta = rawValue as? [String: Any],
              let data = try? JSONSerialization.data(withJSONObject: rawMeta),
              let decoded = try? JSONDecoder().decode(ReportMeta.self, from: data) else {
            return nil
        }
        return decoded
    }

    private func previewSections(from rawValue: Any?) -> [PreviewSectionPayload]? {
        guard let rawSections = rawValue as? [[String: Any]],
              let data = try? JSONSerialization.data(withJSONObject: rawSections),
              let decoded = try? JSONDecoder().decode([PreviewSectionPayload].self, from: data),
              !decoded.isEmpty else {
            return nil
        }
        return decoded
    }
    
    private func reportSections(from rawValue: Any?) -> [ReportBodySectionPayload]? {
        guard let rawSections = rawValue as? [[String: Any]],
              let data = try? JSONSerialization.data(withJSONObject: rawSections),
              let decoded = try? JSONDecoder().decode([ReportBodySectionPayload].self, from: data),
              !decoded.isEmpty else {
            return nil
        }
        return decoded
    }

    override init() {
        super.init()
        if WCSession.isSupported() {
            let session = WCSession.default
            session.delegate = self
            session.activate()
        }
    }

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        DispatchQueue.main.async {
            self.isReachable = session.isReachable
            self.updateTransportStatus(session)
            if session.isReachable { self.processQueue() }
        }
    }

    private func updateTransportStatus(_ session: WCSession) { 
        let stateText: String 
        switch session.activationState { 
        case .notActivated: stateText = "Not Activated" 
        case .inactive: stateText = "Inactive" 
        case .activated: stateText = session.isReachable ? "Connected" : "Reconnecting..." 
        @unknown default: stateText = "Unknown" 
        } 
        DispatchQueue.main.async { 
            self.transportStatus = stateText 
        } 
    } 

    func sessionReachabilityDidChange(_ session: WCSession) {
        DispatchQueue.main.async {
            self.isReachable = session.isReachable
            self.updateTransportStatus(session)
            if session.isReachable { self.processQueue() }
        }
    }

    func fetchJobs() {
        guard WCSession.default.isReachable else {
            print("Cannot fetch jobs: Session not reachable")
            return
        }
        
        WCSession.default.sendMessage(["action": "fetch_jobs"], replyHandler: { reply in
            if let jobsData = reply["jobs"] as? [[String: Any]] {
                do {
                    let data = try JSONSerialization.data(withJSONObject: jobsData)
                    let decodedJobs = try JSONDecoder().decode([ActiveJob].self, from: data)
                    DispatchQueue.main.async {
                        self.activeJobs = decodedJobs
                    }
                } catch {
                    print("Failed to decode jobs: \(error)")
                }
            }
        }, errorHandler: { error in
            print("Fetch jobs error: \(error.localizedDescription)")
        })
    }

    func cancelJob(jobId: String, completion: @escaping (String) -> Void) {
        guard WCSession.default.isReachable else {
            completion("Offline: Cannot cancel job")
            return
        }
        
        WCSession.default.sendMessage(["action": "cancel_job", "job_id": jobId], replyHandler: { reply in
            if let error = reply["error"] as? String {
                completion(error)
            } else {
                completion("Job cancelled")
                self.fetchJobs()
            }
        }, errorHandler: { error in
            completion(error.localizedDescription)
        })
    }

    func performNextAction(_ action: NextActionPayload, jobId: String, completion: @escaping (String) -> Void) {
        switch action.kind {
        case "api_call":
            if action.id == "summarize-progress" || action.target?.hasSuffix("/summarize") == true {
                summarizeJob(jobId: jobId, completion: completion)
                return
            }

            if action.id == "cancel-job" || action.target?.hasSuffix("/cancel") == true {
                cancelJob(jobId: jobId, completion: completion)
                return
            }

            completion("Unsupported action: \(action.label)")
        case "hint":
            completion(action.label)
        default:
            completion("Unsupported action: \(action.label)")
        }
    }

    func summarizeJob(jobId: String, completion: @escaping (String) -> Void) {
        guard WCSession.default.isReachable else {
            completion("Offline: Cannot summarize job")
            return
        }
        
        WCSession.default.sendMessage(["action": "summarize_job", "job_id": jobId], replyHandler: { reply in
            if let error = reply["error"] as? String {
                completion(error)
                return
            }

            let summary = self.applySummarizeReply(reply, jobId: jobId)
            completion(summary)
            self.fetchJobs()
        }, errorHandler: { error in
            completion(error.localizedDescription)
        })
    }

    @discardableResult
    private func applySummarizeReply(_ reply: [String: Any], jobId: String) -> String {
        let summary = reply["summary"] as? String ?? "Unknown response"
        let requiresPhoneHandoff = reply["requires_phone_handoff"] as? Bool ?? false
        let handoffUrl = reply["handoff_url"] as? String
        let transcript = reply["transcript"] as? String
        let phoneReport = reply["phone_report"] as? String
        let reportMeta = self.reportMeta(from: reply["report_meta"])
        let previewSections = self.previewSections(from: reply["preview_sections"])
        let reportSections = self.reportSections(from: reply["report_sections"])

        DispatchQueue.main.async {
            self.responseText = summary
            self.lastResultAt = Date()
            self.handoffUrl = requiresPhoneHandoff ? handoffUrl : nil
            self.handoffJobId = requiresPhoneHandoff ? jobId : nil
            self.handoffState = requiresPhoneHandoff && handoffUrl != nil ? .ready : .idle
            self.handoffPreview = requiresPhoneHandoff && handoffUrl != nil
                ? HandoffPreview(
                    transcript: transcript,
                    summaryText: reportMeta?.watchSummary ?? summary,
                    phoneReport: reportMeta?.phoneReport ?? phoneReport,
                    category: reportMeta?.category,
                    nextAction: reportMeta?.nextAction,
                    retryCount: reportMeta?.retryCount ?? 0,
                    failureCode: reportMeta?.failureCode,
                    failureMessage: reportMeta?.failureMessage,
                    reportSections: reportSections,
                    previewSections: previewSections
                )
                : nil
        }
        return summary
    }

    // MARK: - Result polling (PTT sonrasi is tamamlanana kadar)

    private func startResultPolling(jobId: String) {
        stopResultPolling()
        pollingJobId = jobId
        // watchOS uygulamayi tamamen oldurebilir; bekleyen isi diske yaz ki
        // yeniden acilista sonuc kurtarilabilsin.
        UserDefaults.standard.set(jobId, forKey: Self.pendingJobDefaultsKey)
        UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: Self.pendingJobAtDefaultsKey)
        pollErrorCount = 0
        resultPollDeadline = Date().addingTimeInterval(180)
        startExtendedSession()
        resultPollTimer = Timer.scheduledTimer(withTimeInterval: 4.0, repeats: true) { [weak self] _ in
            self?.pollJobResult(jobId: jobId)
        }
    }

    private func stopResultPolling() {
        resultPollTimer?.invalidate()
        resultPollTimer = nil
        resultPollDeadline = nil
        pollingJobId = nil
        pollErrorCount = 0
        // Diskteki kaydi da temizle. Aksi halde yarim kalan bir bekleme
        // sonraki her acilista "isleniyor" ekranini diriltiyor.
        clearPendingJob()
        stopExtendedSession()
    }

    private func clearPendingJob() {
        UserDefaults.standard.removeObject(forKey: Self.pendingJobDefaultsKey)
        UserDefaults.standard.removeObject(forKey: Self.pendingJobAtDefaultsKey)
    }

    /// watchOS bilek indiginde uygulamayi askiya alip poll timer'ini
    /// oldurebiliyor, hatta uygulamayi tamamen sonlandirabiliyor.
    /// Aktiflesince (soguk baslangic dahil) diske yazilmis bekleyen isi
    /// hatirla, sonucu hemen sor ve timer'i tazele.
    func resumeResultPollingIfNeeded() {
        let persisted = UserDefaults.standard.string(forKey: Self.pendingJobDefaultsKey)
        guard let jobId = pollingJobId ?? persisted else { return }

        // Diskten geliyorsa yasini kontrol et: eski bir kayit ekrani bos
        // yere "isleniyor"a dusurmesin.
        if pollingJobId == nil {
            let at = UserDefaults.standard.double(forKey: Self.pendingJobAtDefaultsKey)
            let age = at > 0 ? Date().timeIntervalSince1970 - at : .greatestFiniteMagnitude
            if age > Self.pendingJobMaxAge {
                clearPendingJob()
                return
            }
        }

        // A suspended timer keeps its old in-memory deadline. Refresh it before
        // the immediate recovery poll so wake-up never discards a finished job
        // merely because the device slept longer than the original window.
        resultPollDeadline = Date().addingTimeInterval(120)
        if !isProcessing {
            isProcessing = true
            responseText = NSLocalizedString("Working… (checking for a pending result)", comment: "")
        }
        pollingJobId = jobId

        if resultPollTimer == nil || !(resultPollTimer?.isValid ?? false) {
            resultPollDeadline = Date().addingTimeInterval(120)
            resultPollTimer = Timer.scheduledTimer(withTimeInterval: 4.0, repeats: true) { [weak self] _ in
                self?.pollJobResult(jobId: jobId)
            }
        }
        pollJobResult(jobId: jobId)
    }

    private func pollJobResult(jobId: String) {
        if let deadline = resultPollDeadline, Date() > deadline {
            stopResultPolling()
            DispatchQueue.main.async {
                self.isProcessing = false
                self.responseText += NSLocalizedString("\n(Still working — check the Jobs tab.)", comment: "")
            }
            return
        }

        guard WCSession.default.isReachable else { return }

        WCSession.default.sendMessage(["action": "summarize_job", "job_id": jobId], replyHandler: { reply in
            // Backend "boyle bir is yok" diyorsa (servis yeniden basladi,
            // is listeden dustu) sonsuza kadar yoklamanin anlami yok.
            if let message = reply["error"] as? String {
                DispatchQueue.main.async {
                    self.pollErrorCount += 1
                    if self.pollErrorCount >= 3 {
                        self.stopResultPolling()
                        self.isProcessing = false
                        self.responseText = String(
                            format: NSLocalizedString("Result unavailable: %@", comment: ""), message)
                    }
                }
                return
            }
            DispatchQueue.main.async { self.pollErrorCount = 0 }

            let reportMeta = self.reportMeta(from: reply["report_meta"])
            let jobStatus = reportMeta?.status ?? (reply["status"] as? String) ?? ""
            guard jobStatus == "completed" || jobStatus == "failed" else { return }

            DispatchQueue.main.async {
                self.stopResultPolling()
                self.isProcessing = false
                UserDefaults.standard.removeObject(forKey: Self.pendingJobDefaultsKey)
                WKInterfaceDevice.current().play(jobStatus == "completed" ? .success : .failure)
            }
            self.applySummarizeReply(reply, jobId: jobId)
            self.fetchJobs()
        }, errorHandler: { error in
            // Gecici baglanti hatasi olabilir; ama ust uste tekrarliyorsa
            // kullaniciya goster — sessiz sonsuz bekleme en kotu durum.
            DispatchQueue.main.async {
                self.pollErrorCount += 1
                if self.pollErrorCount >= 3 {
                    self.stopResultPolling()
                    self.isProcessing = false
                    self.responseText = String(format: NSLocalizedString("Cannot receive result: %@", comment: ""), error.localizedDescription)
                }
            }
        })
    }

    func openHandoff(url explicitUrl: String? = nil, jobId: String? = nil) {
        guard let url = explicitUrl ?? handoffUrl else { return }
        let resolvedJobId = jobId ?? handoffJobId
        let payload: [String: Any] = [
            "action": "open_handoff",
            "url": url,
            "job_id": resolvedJobId ?? "",
        ]

        guard WCSession.default.isReachable else {
            WCSession.default.transferUserInfo(payload)
            DispatchQueue.main.async {
                if let resolvedJobId { self.handoffJobId = resolvedJobId }
                self.handoffState = .pendingOnPhone
            }
            return
        }

        WCSession.default.sendMessage(payload) { reply in
            DispatchQueue.main.async {
                if let resolvedJobId {
                    self.handoffJobId = resolvedJobId
                }
                if let error = reply["error"] as? String {
                    self.handoffState = .ready
                    print("Handoff error: \(error)")
                    return
                }

                let status = reply["status"] as? String ?? "opened"
                switch status {
                case "pending":
                    self.handoffState = .pendingOnPhone
                default:
                    self.handoffState = .openedOnPhone
                }
            }
        } errorHandler: { error in
            WCSession.default.transferUserInfo(payload)
            DispatchQueue.main.async {
                self.handoffState = .pendingOnPhone
                print("Immediate handoff unavailable; queued: \(error.localizedDescription)")
            }
        }
    }

    func sendAudioCommand(audioBase64: String) {
        let request = WatchCommandRequest(
            audioData: audioBase64,
            format: "m4a",
            clientTimestamp: ISO8601DateFormatter().string(from: Date())
        )

        guard let data = try? JSONEncoder().encode(request) else {
            DispatchQueue.main.async {
                self.responseText = "Encoding Error"
            }
            return
        }

        // WCSession sendMessageData limiti ~65KB; asarsak gonderim sessizce
        // olur. Kullaniciya net soyle, kuyruga da alma.
        if data.count > 60_000 {
            DispatchQueue.main.async {
                self.isProcessing = false
                // Eski handoff paneli mesaji golgelemesin; hata tek basina gorunsun.
                self.handoffUrl = nil
                self.handoffJobId = nil
                self.handoffState = .idle
                self.handoffPreview = nil
                self.responseText = String(format: NSLocalizedString("✕ Recording too long to send (%dKB). Speak briefly and try again.", comment: ""), data.count / 1024)
                WKInterfaceDevice.current().play(.failure)
            }
            return
        }

        if !WCSession.default.isReachable { 
            self.queueCommand(audioBase64: audioBase64) 
            return 
        } 

        // Start extended session to keep watch awake during transfer
        self.startExtendedSession()

        DispatchQueue.main.async {
            self.responseText = "Sending..."
            self.isProcessing = true
            self.handoffUrl = nil
            self.handoffJobId = nil
            self.handoffState = .idle
            self.handoffPreview = nil
        }

        // WCSession bazen (ozellikle telefon uygulamasi elle kapatilmissa)
        // ne cevap ne hata dondurur; gonderim onayina zaman asimi koy ki
        // ekran sonsuza dek "yorumlaniyor"da kalmasin.
        DispatchQueue.main.async {
            self.sendGeneration += 1
            let generation = self.sendGeneration
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) { [weak self] in
                guard let self,
                      self.sendGeneration == generation,
                      self.isProcessing,
                      self.pollingJobId == nil else { return }
                self.isProcessing = false
                self.queueCommand(audioBase64: audioBase64)
                self.responseText = NSLocalizedString("No reply from iPhone; command queued. Open Ceviz on iPhone and try again.", comment: "")
            }
        }

        WCSession.default.sendMessageData(data, replyHandler: { replyData in
            // Stop extended session on success
            self.stopExtendedSession()
            DispatchQueue.main.async { self.sendGeneration += 1 }
            
            guard let response = try? JSONDecoder().decode(WatchCommandResponse.self, from: replyData) else {
                DispatchQueue.main.async {
                    self.responseText = "Invalid Response"
                    self.handoffState = .idle
                    self.handoffPreview = nil
                }
                return
            }

            DispatchQueue.main.async {
                self.responseText = response.summaryText
                if response.status != "processing" {
                    self.lastResultAt = Date()
                }
                let effectiveRequiresPhoneHandoff = response.reportMeta?.requiresPhoneHandoff ?? response.requiresPhoneHandoff
                self.handoffUrl = effectiveRequiresPhoneHandoff ? response.handoffUrl : nil
                self.handoffJobId = effectiveRequiresPhoneHandoff ? response.jobId : nil
                self.handoffState = effectiveRequiresPhoneHandoff && response.handoffUrl != nil ? .ready : .idle
                self.handoffPreview = effectiveRequiresPhoneHandoff && response.handoffUrl != nil
                    ? HandoffPreview(
                        transcript: response.transcript,
                        summaryText: response.reportMeta?.watchSummary ?? response.summaryText,
                        phoneReport: response.reportMeta?.phoneReport ?? response.phoneReport,
                        category: response.reportMeta?.category,
                        nextAction: response.reportMeta?.nextAction,
                        retryCount: response.reportMeta?.retryCount ?? 0,
                        failureCode: response.reportMeta?.failureCode,
                        failureMessage: response.reportMeta?.failureMessage,
                        reportSections: response.reportSections,
                        previewSections: response.previewSections
                    )
                    : nil

                if let ttsBase64 = response.ttsAudioData, let format = response.ttsFormat {
                    self.audioPlayerManager?.play(base64Data: ttsBase64, format: format)
                }

                // Backend "processing" ack'i ile hemen döner; iş OpenClaw'da
                // arkada tamamlanır ve sonucu kimse itmez. Tamamlanana kadar
                // summarize üzerinden yokla ki özet ve handoff bileğe düşsün.
                if response.status == "processing", let jobId = response.jobId {
                    self.startResultPolling(jobId: jobId)
                } else {
                    self.isProcessing = false
                }
            }
        }, errorHandler: { error in
            // Stop extended session on error
            self.stopExtendedSession()
            
            DispatchQueue.main.async {
                self.sendGeneration += 1
                self.isProcessing = false
                self.handoffJobId = nil
                self.handoffState = .idle
                self.handoffPreview = nil
                self.responseText = "Error: \(error.localizedDescription)"
                // Re-queue on failure if it was a connectivity error
                self.queueCommand(audioBase64: audioBase64)
            }
        })
    }
    
    private func queueCommand(audioBase64: String) { 
        // Ensure session is stopped if we fallback to queue
        self.stopExtendedSession()
        
        let newCommand = QueuedCommand( 
            id: UUID().uuidString, 
            audioData: audioBase64, 
            timestamp: Date(), 
            retryCount: 0 
        ) 
        DispatchQueue.main.async { 
            // Avoid duplicates in queue
            if !self.pendingCommands.contains(where: { $0.audioData == audioBase64 }) {
                self.pendingCommands.append(newCommand) 
            }
            self.responseText = "Offline. Command queued." 
            WKInterfaceDevice.current().play(.retry) 
        } 
    } 

    func processQueue() { 
        guard WCSession.default.isReachable, !pendingCommands.isEmpty,
              !isDrainingCommandQueue else { return }
        isDrainingCommandQueue = true
        
        let commandsToProcess = pendingCommands 
        DispatchQueue.main.async { 
            self.pendingCommands = [] 
            self.responseText = "Processing queued commands..." 
        } 
        
        // Process sequentially to avoid session flooding
        func sendNext(index: Int) {
            guard index < commandsToProcess.count else {
                DispatchQueue.main.async {
                    self.isDrainingCommandQueue = false
                    self.fetchJobs()
                }
                return
            }
            
            var command = commandsToProcess[index]
            command.retryCount += 1
            
            // Note: Since sendAudioCommand is async, we'd ideally wait for completion.
            // For now, we'll trigger them with a small delay to respect the radio.
            self.sendAudioCommand(audioBase64: command.audioData)
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                sendNext(index: index + 1)
            }
        }
        
        sendNext(index: 0)
    } 

    func updateJobStatus(jobId: String, newStatus: String) {
        // Geçici olarak job durumunu güncelle (optimistic update)
        if let index = activeJobs.firstIndex(where: { $0.id == jobId }) {
            var updatedJob = activeJobs[index]
            updatedJob.status = newStatus
            activeJobs[index] = updatedJob
        }
    }
}
