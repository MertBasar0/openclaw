import SwiftUI
import WatchKit
import UserNotifications
import WatchConnectivity

final class WatchAppDelegate: NSObject, WKExtensionDelegate, UNUserNotificationCenterDelegate {
    func applicationDidFinishLaunching() {
        UNUserNotificationCenter.current().delegate = self
        WKExtension.shared().registerForRemoteNotifications()
    }

    func didRegisterForRemoteNotifications(withDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        let payload: [String: Any] = [
            "action": "register_watch_push",
            "apns_token": token,
            "bundle_id": Bundle.main.bundleIdentifier ?? "com.mertbasar.cevizwatch.watchkitapp",
        ]
        let session = WCSession.default
        if session.activationState != .activated {
            session.activate()
        }
        session.transferUserInfo(payload)
    }

    func didFailToRegisterForRemoteNotificationsWithError(_ error: Error) {
        print("Watch APNs registration failed: \(error.localizedDescription)")
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        WatchSessionManager.shared.consumeTerminalNotification(
            response.notification.request.content.userInfo
        )
        completionHandler()
    }
}

@main
struct WatchCeviz_Watch_AppApp: App {
    @WKExtensionDelegateAdaptor(WatchAppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
