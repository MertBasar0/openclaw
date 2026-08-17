import Foundation
import UIKit
import UserNotifications
import os

final class CevizAppDelegate: NSObject, UIApplicationDelegate {
    private let logger = Logger(subsystem: "com.mertbasar.ceviz.ios", category: "PushRegistration")
    private let apnsTokenKey = "cvz.apnsToken"
    private var retryAttempt = 0
    private var retryWorkItem: DispatchWorkItem?
    private var registrationInFlight = false

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(connectionConfigurationDidChange),
            name: BackendConfig.connectionDidChange,
            object: nil
        )
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

    func applicationDidBecomeActive(_ application: UIApplication) {
        application.registerForRemoteNotifications()
        if let token = UserDefaults.standard.string(forKey: apnsTokenKey), !token.isEmpty {
            registerWithBackend(apnsToken: token)
        }
    }

    @objc private func connectionConfigurationDidChange() {
        retryWorkItem?.cancel()
        retryAttempt = 0
        if let token = UserDefaults.standard.string(forKey: apnsTokenKey), !token.isEmpty {
            registerWithBackend(apnsToken: token)
        } else {
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        UserDefaults.standard.set(token, forKey: apnsTokenKey)
        registerWithBackend(apnsToken: token)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        logger.error("APNs registration failed: \(error.localizedDescription)")
    }

    private func registerWithBackend(apnsToken: String) {
        guard !registrationInFlight else { return }
        registrationInFlight = true
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
        request.timeoutInterval = 20
        BackendTransport.shared.dataTask(with: request) { _, response, error in
            if let error {
                self.logger.error("Backend push registration failed: \(error.localizedDescription)")
                DispatchQueue.main.async {
                    self.registrationInFlight = false
                    self.scheduleRetry(apnsToken: apnsToken)
                }
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            if !(200...299).contains(status) {
                self.logger.error("Backend push registration returned HTTP \(status)")
                DispatchQueue.main.async {
                    self.registrationInFlight = false
                    self.scheduleRetry(apnsToken: apnsToken)
                }
                return
            }
            DispatchQueue.main.async {
                self.registrationInFlight = false
                self.retryWorkItem?.cancel()
                self.retryWorkItem = nil
                self.retryAttempt = 0
                self.logger.info("Push registration completed")
            }
        }.resume()
    }

    private func scheduleRetry(apnsToken: String) {
        DispatchQueue.main.async {
            self.retryWorkItem?.cancel()
            let delays: [TimeInterval] = [5, 15, 30, 60, 120, 300]
            let delay = delays[min(self.retryAttempt, delays.count - 1)]
            self.retryAttempt += 1

            let workItem = DispatchWorkItem { [weak self] in
                guard let self else { return }
                self.registerWithBackend(apnsToken: apnsToken)
            }
            self.retryWorkItem = workItem
            self.logger.info("Push registration retry scheduled in \(Int(delay)) seconds")
            DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: workItem)
        }
    }
}
