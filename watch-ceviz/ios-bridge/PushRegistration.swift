import Foundation
import UIKit
import UserNotifications
import os

final class CevizAppDelegate: NSObject, UIApplicationDelegate {
    private let logger = Logger(subsystem: "com.mertbasar.ceviz.ios", category: "PushRegistration")

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            if let error {
                self.logger.error("Notification authorization failed: \(error.localizedDescription)")
                return
            }
            guard granted else {
                self.logger.info("Notification authorization denied")
                return
            }
            DispatchQueue.main.async { application.registerForRemoteNotifications() }
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        registerWithBackend(apnsToken: token)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        logger.error("APNs registration failed: \(error.localizedDescription)")
    }

    private func registerWithBackend(apnsToken: String) {
        let installationKey = "cvz.pushInstallationId"
        let defaults = UserDefaults.standard
        let installationId: String
        if let existing = defaults.string(forKey: installationKey), !existing.isEmpty {
            installationId = existing
        } else {
            installationId = UUID().uuidString
            defaults.set(installationId, forKey: installationKey)
        }
        let payload: [String: String] = [
            "apns_token": apnsToken,
            "bundle_id": Bundle.main.bundleIdentifier ?? "com.mertbasar.cevizwatch",
            "installation_id": installationId,
            "environment": "production",
        ]
        var request = BackendConfig.request("/api/v1/push/register", method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: payload)
        URLSession.shared.dataTask(with: request) { _, response, error in
            if let error {
                self.logger.error("Backend push registration failed: \(error.localizedDescription)")
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            if !(200...299).contains(status) {
                self.logger.error("Backend push registration returned HTTP \(status)")
                return
            }
            self.logger.info("Push registration completed")
        }.resume()
    }
}
