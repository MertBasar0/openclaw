import SwiftUI
import WatchKit
import UserNotifications

final class WatchAppDelegate: NSObject, WKExtensionDelegate, UNUserNotificationCenterDelegate {
    func applicationDidFinishLaunching() {
        UNUserNotificationCenter.current().delegate = self
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
