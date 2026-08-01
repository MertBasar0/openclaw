import Foundation

/// Demo modu — backend olmadan gercekci bir deneyim.
///
/// Iki nedenle var:
///  1. App Review: inceleyicinin kullanicinin tailnet'ine erisimi yok;
///     demo modu olmasa uygulama bos/hatali gorunur ve reddedilir.
///  2. Ilk acilis: eslesme yapilmadan once urunun ne yaptigi gorulebilsin.
///
/// Hic yapilandirma yoksa (token ve sunucu adresi bos) kendiliginden
/// devreye girer; Ayarlar'dan elle de acilip kapatilabilir.
enum DemoMode {
    static let defaultsKey = "cvz.demoMode"

    /// Kullanicinin Ayarlar'dan actigi acik demo modu.
    static var isExplicit: Bool {
        UserDefaults.standard.bool(forKey: defaultsKey)
    }

    static func setExplicit(_ on: Bool) {
        UserDefaults.standard.set(on, forKey: defaultsKey)
    }

    /// Yapilandirma yoksa demo; boylece taze kurulumda (App Review) calisir.
    static var isUnconfigured: Bool {
        let url = UserDefaults.standard.string(forKey: BackendConfig.urlDefaultsKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return url.isEmpty && BackendConfig.token.isEmpty
    }

    static var isActive: Bool { isExplicit || isUnconfigured }

    // MARK: - Veri

    private static func decode<T: Decodable>(_ json: String, as type: T.Type) -> T? {
        guard let data = json.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }

    private static func t(_ key: String) -> String {
        NSLocalizedString(key, comment: "demo content")
    }

    private static func esc(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
    }

    /// Vitrin akislari: deploy kontrolu (zincirli), PR ozeti, incident triage.
    private static var jobsJSON: String {
        let deployName = esc(t("demo.deploy.name"))
        let deploySummary = esc(t("demo.deploy.summary"))
        let deployReport = esc(t("demo.deploy.report"))
        let rollbackName = esc(t("demo.rollback.name"))
        let rollbackSummary = esc(t("demo.rollback.summary"))
        let rollbackReport = esc(t("demo.rollback.report"))
        let prName = esc(t("demo.pr.name"))
        let prSummary = esc(t("demo.pr.summary"))
        let prReport = esc(t("demo.pr.report"))
        let incidentName = esc(t("demo.incident.name"))
        let incidentSummary = esc(t("demo.incident.summary"))
        let incidentReport = esc(t("demo.incident.report"))
        let secWatch = esc(t("demo.section.watch"))
        let secAnalysis = esc(t("demo.section.analysis"))
        let secAgents = esc(t("demo.section.agents"))
        let agentsBody = esc(t("demo.agents.body"))
        let actGrafana = esc(t("demo.action.grafana"))
        let actRollback = esc(t("demo.action.rollback"))
        let actOpenPR = esc(t("demo.action.openpr"))
        let actLogs = esc(t("demo.action.logs"))

        func job(
            id: String, conv: String, name: String, status: String, elapsed: Int,
            summary: String, report: String, severity: String, category: String,
            outcome: String, actions: String
        ) -> String {
            """
            {
              "id": "\(id)",
              "conversation_id": "\(conv)",
              "name": "\(name)",
              "status": "\(status)",
              "elapsed_seconds": \(elapsed),
              "summary_text": "\(summary)",
              "requires_phone_handoff": true,
              "transcript": "\(name)",
              "phone_report": "\(report)",
              "deep_link": "ceviz://job/\(id)",
              "report_meta": {
                "title": "\(name)",
                "status": "\(status)",
                "severity": "\(severity)",
                "category": "\(category)",
                "watch_summary": "\(summary)",
                "requires_phone_handoff": true,
                "handoff_reason": "long_detail",
                "phone_report": "\(report)",
                "next_action": null,
                "retry_count": 0,
                "failure_code": null,
                "failure_message": null,
                "outcome": "\(outcome)"
              },
              "report_sections": [
                {"id": "watch-summary", "title": "\(secWatch)", "eyebrow": "WATCH", "icon": "applewatch", "content": "\(summary)"},
                {"id": "expanded-analysis", "title": "\(secAnalysis)", "eyebrow": "ANALYSIS", "icon": "doc.text", "content": "\(report)"},
                {"id": "background-activity", "title": "\(secAgents)", "eyebrow": "AGENTS", "icon": "person.3", "content": "\(agentsBody)"}
              ],
              "preview_sections": [
                {"id": "watch-summary", "title": "\(secWatch)", "eyebrow": "WATCH", "icon": "applewatch", "content": "\(summary)"}
              ],
              "next_actions": \(actions)
            }
            """
        }

        let deployActions = """
        [
          {"id": "open-grafana", "label": "\(actGrafana)", "kind": "open_url", "target": "https://grafana.example.com/d/deploy"},
          {"id": "suggested-next-action", "label": "\(actRollback)", "kind": "agent_command", "target": null}
        ]
        """
        let prActions = """
        [{"id": "open-pr", "label": "\(actOpenPR)", "kind": "open_url", "target": "https://github.com/example/repo/pull/128"}]
        """
        let incidentActions = """
        [{"id": "open-logs", "label": "\(actLogs)", "kind": "open_url", "target": "https://logs.example.com/incident/4412"}]
        """

        return """
        {"jobs": [
        \(job(id: "job-demo-01", conv: "demo-chain-a", name: deployName, status: "completed", elapsed: 192,
              summary: deploySummary, report: deployReport, severity: "medium",
              category: "deploy_check", outcome: "done", actions: deployActions)),
        \(job(id: "job-demo-02", conv: "demo-chain-a", name: rollbackName, status: "completed", elapsed: 96,
              summary: rollbackSummary, report: rollbackReport, severity: "low",
              category: "deploy_check", outcome: "done", actions: "[]")),
        \(job(id: "job-demo-03", conv: "demo-chain-b", name: prName, status: "completed", elapsed: 74,
              summary: prSummary, report: prReport, severity: "low",
              category: "pr_review", outcome: "done", actions: prActions)),
        \(job(id: "job-demo-04", conv: "demo-chain-c", name: incidentName, status: "running", elapsed: 38,
              summary: incidentSummary, report: incidentReport, severity: "high",
              category: "incident", outcome: "needs_input", actions: incidentActions))
        ]}
        """
    }

    static var jobs: [ActiveJob] {
        decode(jobsJSON, as: ActiveJobsResponse.self)?.jobs ?? []
    }

    static func job(id: String) -> ActiveJob? {
        jobs.first { $0.id == id } ?? jobs.first
    }

    /// Rapor ekrani icin: demo isini rapor cevabina cevir.
    static func report(for id: String) -> JobReportResponse? {
        guard let j = job(id: id) else { return nil }
        let payload: [String: Any] = [
            "job_id": j.id,
            "conversation_id": j.conversationId ?? "",
            "status": j.status,
            "report_title": j.name,
            "report_content": j.phoneReport,
            "watch_summary": j.summaryText,
            "requires_phone_handoff": j.requiresPhoneHandoff,
            "deep_link": j.deepLink ?? "",
        ]
        guard let base = try? JSONSerialization.data(withJSONObject: payload),
              var dict = try? JSONSerialization.jsonObject(with: base) as? [String: Any] else { return nil }
        // Codable alt yapilarini yeniden kodlayarak ekle.
        if let meta = j.reportMeta, let d = try? JSONEncoder().encode(meta),
           let o = try? JSONSerialization.jsonObject(with: d) { dict["report_meta"] = o }
        if let secs = j.reportSections, let d = try? JSONEncoder().encode(secs),
           let o = try? JSONSerialization.jsonObject(with: d) { dict["report_sections"] = o }
        if let secs = j.previewSections, let d = try? JSONEncoder().encode(secs),
           let o = try? JSONSerialization.jsonObject(with: d) { dict["preview_sections"] = o }
        if let acts = j.nextActions, let d = try? JSONEncoder().encode(acts),
           let o = try? JSONSerialization.jsonObject(with: d) { dict["next_actions"] = o }

        guard let data = try? JSONSerialization.data(withJSONObject: dict) else { return nil }
        return try? JSONDecoder().decode(JobReportResponse.self, from: data)
    }

    /// Saat koprusunun demo cevabi (WCSession reply sozlugu).
    static func watchReply(for id: String?) -> [String: Any] {
        guard let j = job(id: id ?? "") else { return ["error": "demo"] }
        var reply: [String: Any] = [
            "summary": j.summaryText,
            "status": j.status,
            "requires_phone_handoff": j.requiresPhoneHandoff,
            "transcript": j.transcript,
            "phone_report": j.phoneReport,
            "handoff_url": j.deepLink ?? "",
            "deep_link": j.deepLink ?? "",
            "job_id": j.id,
        ]
        if let meta = j.reportMeta, let d = try? JSONEncoder().encode(meta),
           let o = try? JSONSerialization.jsonObject(with: d) { reply["report_meta"] = o }
        if let secs = j.previewSections, let d = try? JSONEncoder().encode(secs),
           let o = try? JSONSerialization.jsonObject(with: d) { reply["preview_sections"] = o }
        if let acts = j.nextActions, let d = try? JSONEncoder().encode(acts),
           let o = try? JSONSerialization.jsonObject(with: d) { reply["next_actions"] = o }
        return reply
    }

    static var jobsReplyForWatch: [String: Any] {
        var out: [[String: Any]] = []
        for j in jobs {
            if let d = try? JSONEncoder().encode(j),
               let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                out.append(o)
            }
        }
        return ["jobs": out]
    }
}
