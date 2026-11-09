import AppKit
import ApplicationServices
import Foundation

let screens = NSScreen.screens.map { screen -> [String: Any] in
    ["x": screen.frame.origin.x, "y": screen.frame.origin.y,
     "width": screen.frame.width, "height": screen.frame.height,
     "scale": screen.backingScaleFactor]
}
let report: [String: Any] = [
    "os": ProcessInfo.processInfo.operatingSystemVersionString,
    "accessibilityTrusted": AXIsProcessTrusted(),
    "screenCaptureAllowed": CGPreflightScreenCaptureAccess(),
    "eventPostingAllowed": CGPreflightPostEventAccess(),
    "eventListeningAllowed": CGPreflightListenEventAccess(),
    "screens": screens,
    "windowServerSessionAvailable": CGSessionCopyCurrentDictionary() != nil,
]
let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
