import AppKit
import ApplicationServices
import Foundation

// External proof driver: only AX reads, OS mouse/keyboard input, and screenshots.
// It never links the app module, instantiates a menu, or invokes an AXPress action.
struct DriverFailure: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

struct Options {
    let pid: pid_t
    let session: String
    let preference: String
    let expected: String
    let output: String
    let selection: String?
    let dumpOnly: Bool

    init() throws {
        var values: [String: String] = [:]
        var flags = Set<String>()
        let arguments = Array(CommandLine.arguments.dropFirst())
        var index = 0
        while index < arguments.count {
            let key = arguments[index]
            if key == "--dump-only" {
                flags.insert(key)
                index += 1
            } else {
                guard ["--pid", "--session-label", "--preference", "--expected", "--out", "--select"].contains(key),
                      index + 1 < arguments.count, values[key] == nil
                else { throw DriverFailure("Unknown, repeated, or incomplete argument: \(key)") }
                values[key] = arguments[index + 1]
                index += 2
            }
        }
        guard let rawPID = values["--pid"], let pid = Int32(rawPID), pid > 1,
              let session = values["--session-label"], !session.isEmpty,
              let preference = values["--preference"], ["Thinking", "Verbose"].contains(preference),
              let expected = values["--expected"], ["none", "off", "high", "on"].contains(expected),
              let output = values["--out"], output.hasPrefix("/")
        else {
            throw DriverFailure("Required: --pid PID --session-label LABEL --preference Thinking|Verbose --expected none|off|high|on --out /absolute/PREFIX [--select Off|High|On] [--dump-only]")
        }
        if let selection = values["--select"], !["Off", "High", "On"].contains(selection) {
            throw DriverFailure("--select must be Off, High, or On")
        }
        self.pid = pid
        self.session = session
        self.preference = preference
        self.expected = expected
        self.output = output
        self.selection = values["--select"]
        self.dumpOnly = flags.contains("--dump-only")
    }
}

final class MenuDriver {
    let options: Options
    let application: AXUIElement
    let system = AXUIElementCreateSystemWide()
    var actions: [[String: Any]] = []
    var observations: [[String: Any]] = []
    var phase = "initialization"
    var openedMenu = false
    var lastPosition: CGPoint?
    let started = Date()

    init(_ options: Options) {
        self.options = options
        self.application = AXUIElementCreateApplication(options.pid)
        AXUIElementSetMessagingTimeout(self.application, 1.0)
    }

    func sanitize(_ text: String) -> String {
        var result = String(text.prefix(320))
        for (pattern, replacement) in [
            (#"(?i)\b(?:https?|wss?)://[^\s]+"#, "[URL]"),
            (#"(?i)(?:bearer\s+|(?:token|password|secret)\s*[:=]\s*)[^\s,;]+"#, "[credential]"),
            (#"/(?:Users|home)/[^\s/]+"#, "/[user]"),
        ] {
            result = result.replacingOccurrences(of: pattern, with: replacement, options: .regularExpression)
        }
        return result
    }

    func record(_ action: String, _ details: [String: Any] = [:]) {
        var entry = details
        entry["action"] = action
        entry["seconds"] = Date().timeIntervalSince(self.started)
        entry["phase"] = self.phase
        self.actions.append(entry)
    }

    func attribute(_ element: AXUIElement, _ name: String) -> (CFTypeRef?, AXError) {
        var value: CFTypeRef?
        let error = AXUIElementCopyAttributeValue(element, name as CFString, &value)
        return (value, error)
    }

    func string(_ element: AXUIElement, _ name: String) -> String {
        self.attribute(element, name).0 as? String ?? ""
    }

    func element(_ value: CFTypeRef?) -> AXUIElement? {
        guard let value, CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
        return (value as! AXUIElement)
    }

    func list(_ value: CFTypeRef?) -> [AXUIElement] {
        if let single = self.element(value) { return [single] }
        return value as? [AXUIElement] ?? []
    }

    func rect(_ element: AXUIElement) -> CGRect? {
        guard let position = self.attribute(element, kAXPositionAttribute).0,
              let size = self.attribute(element, kAXSizeAttribute).0,
              CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID()
        else { return nil }
        var point = CGPoint.zero
        var dimensions = CGSize.zero
        guard AXValueGetValue(position as! AXValue, .cgPoint, &point),
              AXValueGetValue(size as! AXValue, .cgSize, &dimensions),
              point.x.isFinite, point.y.isFinite,
              dimensions.width > 0, dimensions.height > 0
        else { return nil }
        return CGRect(origin: point, size: dimensions)
    }

    func onScreen(_ element: AXUIElement) -> Bool {
        if self.attribute(element, "AXHidden").0 as? Bool == true { return false }
        guard let rect = self.rect(element) else { return false }
        return CGDisplayBounds(CGMainDisplayID()).intersects(rect)
    }

    func children(_ element: AXUIElement) -> [AXUIElement] {
        var result: [AXUIElement] = []
        for name in [kAXChildrenAttribute, "AXVisibleChildren", "AXMenu"] {
            for child in self.list(self.attribute(element, name).0)
                where !result.contains(where: { CFEqual($0, child) }) {
                result.append(child)
            }
        }
        return result
    }

    func roots() -> [AXUIElement] {
        var roots = [self.application]
        for name in [kAXExtrasMenuBarAttribute, kAXMenuBarAttribute, kAXWindowsAttribute] {
            roots += self.list(self.attribute(self.application, name).0)
        }
        if let focused = self.element(self.attribute(self.system, kAXFocusedUIElementAttribute).0) {
            var owner: pid_t = 0
            if AXUIElementGetPid(focused, &owner) == .success, owner == self.options.pid { roots.append(focused) }
        }
        return roots
    }

    func walk(_ roots: [AXUIElement], limit: Int = 500) -> [(AXUIElement, Int)] {
        var queue = roots.map { ($0, 0) }
        var seen: [AXUIElement] = []
        var output: [(AXUIElement, Int)] = []
        var index = 0
        while index < queue.count, output.count < limit {
            let (element, depth) = queue[index]
            index += 1
            if seen.contains(where: { CFEqual($0, element) }) { continue }
            seen.append(element)
            output.append((element, depth))
            if depth < 10 { queue += self.children(element).map { ($0, depth + 1) } }
        }
        return output
    }

    func title(_ element: AXUIElement) -> String {
        let title = self.string(element, kAXTitleAttribute)
        if !title.isEmpty { return title }
        let description = self.string(element, kAXDescriptionAttribute)
        if !description.isEmpty { return description }
        return self.children(element).prefix(8).compactMap { child -> String? in
            let title = self.string(child, kAXTitleAttribute)
            if !title.isEmpty { return title }
            return self.attribute(child, kAXValueAttribute).0 as? String
        }.joined(separator: " ")
    }

    func snapshot(_ element: AXUIElement, depth: Int = 0) -> [String: Any] {
        var result: [String: Any] = [
            "role": self.string(element, kAXRoleAttribute),
            "title": self.sanitize(self.title(element)), "depth": depth,
        ]
        if let rect = self.rect(element) {
            result["rect"] = ["x": rect.minX, "y": rect.minY, "width": rect.width, "height": rect.height]
        }
        for name in ["AXMenuItemMarkChar", kAXValueAttribute, kAXEnabledAttribute, "AXSelected"] {
            let (value, error) = self.attribute(element, name)
            if let text = value as? String { result[name] = self.sanitize(text) }
            else if let number = value as? NSNumber { result[name] = number }
            result[name + "ReadResult"] = error.rawValue
        }
        return result
    }

    func pause(_ seconds: TimeInterval) {
        RunLoop.current.run(until: Date().addingTimeInterval(seconds))
    }

    func wait<T>(_ purpose: String, seconds: TimeInterval = 12, operation: () -> T?) throws -> T {
        let deadline = Date().addingTimeInterval(seconds)
        repeat {
            if let value = operation() { return value }
            self.pause(0.2)
        } while Date() < deadline
        throw DriverFailure("Timed out waiting for \(purpose); inspect the retained AX diagnostic JSON")
    }

    func statusItem() throws -> AXUIElement {
        try self.wait("target app's status-bar item") {
            let extras = self.list(self.attribute(self.application, kAXExtrasMenuBarAttribute).0)
            let nodes = self.walk(extras.isEmpty ? self.roots() : extras)
            let candidates = nodes.map(\.0).filter { element in
                let role = self.string(element, kAXRoleAttribute)
                guard [kAXMenuBarItemRole, kAXButtonRole].contains(role),
                      let frame = self.rect(element), frame.minY < 80, frame.height <= 48,
                      self.onScreen(element)
                else { return false }
                return true
            }
            let menuBarItems = candidates.filter { self.string($0, kAXRoleAttribute) == kAXMenuBarItemRole }
            let preferred = menuBarItems.isEmpty ? candidates : menuBarItems
            let named = preferred.filter { self.title($0).localizedCaseInsensitiveContains("OpenClaw") }
            if named.count == 1 { return named[0] }
            // Only a unique item inside this process's AXExtrasMenuBar is safe to click unnamed.
            if !extras.isEmpty, preferred.count == 1 { return preferred[0] }
            return nil
        }
    }

    func mouse(_ type: CGEventType, _ point: CGPoint, button: CGMouseButton = .left) throws {
        guard let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: button)
        else { throw DriverFailure("Could not create external mouse input") }
        event.post(tap: .cghidEventTap)
        self.lastPosition = point
    }

    func hover(_ element: AXUIElement, purpose: String) throws {
        guard let frame = self.rect(element) else { throw DriverFailure("No AX position for \(purpose)") }
        let destination = CGPoint(x: frame.midX, y: frame.midY)
        if let previous = self.lastPosition, previous.y > 50, abs(destination.x - previous.x) > 35 {
            // Enter the adjacent submenu horizontally before moving to its target row.
            try self.mouse(.mouseMoved, CGPoint(x: destination.x, y: previous.y))
            self.pause(0.12)
        }
        try self.mouse(.mouseMoved, destination)
        self.record("hover", ["target": purpose, "x": destination.x, "y": destination.y])
        self.pause(0.8)
    }

    func menuItem(_ title: String, under roots: [AXUIElement]? = nil, contains: Bool = false) -> AXUIElement? {
        let candidates = self.walk(roots ?? self.roots()).map(\.0).filter { element in
            guard self.string(element, kAXRoleAttribute) == kAXMenuItemRole, self.onScreen(element) else { return false }
            let text = self.title(element)
            return text == title || (contains && text.contains(title))
        }
        return candidates.count == 1 ? candidates[0] : nil
    }

    func checked(_ element: AXUIElement) -> Bool {
        let mark = self.string(element, "AXMenuItemMarkChar").trimmingCharacters(in: .whitespacesAndNewlines)
        if !mark.isEmpty { return true }
        let (value, _) = self.attribute(element, kAXValueAttribute)
        if let number = value as? NSNumber { return number.intValue != 0 }
        if let text = value as? String { return ["1", "true", "on", "checked", "✓", "✔", "√"].contains(text.lowercased()) }
        return false
    }

    func screenshot(_ suffix: String) throws {
        let path = self.options.output + suffix + ".png"
        guard !FileManager.default.fileExists(atPath: path) else { throw DriverFailure("Refusing to overwrite existing screenshot") }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
        process.arguments = ["-x", "-m", path]
        try process.run()
        process.waitUntilExit()
        guard process.terminationStatus == 0, FileManager.default.fileExists(atPath: path)
        else { throw DriverFailure("Full-desktop screencapture failed with status \(process.terminationStatus)") }
        self.record("fullDesktopScreenshot", ["file": URL(fileURLWithPath: path).lastPathComponent])
    }

    func escape() {
        guard self.openedMenu else { return }
        for _ in 0..<4 {
            for down in [true, false] {
                CGEvent(keyboardEventSource: nil, virtualKey: 53, keyDown: down)?.post(tap: .cghidEventTap)
            }
            self.pause(0.1)
        }
        self.record("escapeMenus")
        self.openedMenu = false
    }

    func writeResult(_ status: String, error: String? = nil) throws {
        var result: [String: Any] = [
            "schema": 1, "status": status, "pid": self.options.pid,
            "sessionLabel": self.sanitize(self.options.session), "preference": self.options.preference,
            "expected": self.options.expected, "dumpOnly": self.options.dumpOnly,
            "interaction": "external AX-read + CGEvent right-click/hover; no AXPress or injected app code",
            "startedUTC": ISO8601DateFormatter().string(from: self.started),
            "actions": self.actions, "observations": self.observations,
        ]
        if let error { result["error"] = self.sanitize(error) }
        let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: URL(fileURLWithPath: self.options.output + ".json"), options: .withoutOverwriting)
    }

    func run() throws {
        guard AXIsProcessTrusted(), CGPreflightPostEventAccess(), CGPreflightScreenCaptureAccess()
        else { throw DriverFailure("AX, event-posting, and screen-capture permissions must already be granted") }
        guard NSRunningApplication(processIdentifier: self.options.pid) != nil
        else { throw DriverFailure("Target PID is not a running application") }
        self.phase = "status-entry"
        let item = try self.statusItem()
        guard let frame = self.rect(item) else { throw DriverFailure("Status item lost its AX position") }
        self.observations.append(["stage": "statusItem", "element": self.snapshot(item)])
        let point = CGPoint(x: frame.midX, y: frame.midY)
        try self.mouse(.mouseMoved, point)
        self.pause(0.1)
        try self.mouse(.rightMouseDown, point, button: .right)
        try self.mouse(.rightMouseUp, point, button: .right)
        self.openedMenu = true
        self.record("rightClickStatusItem", ["x": point.x, "y": point.y])

        self.phase = "session-submenu"
        let session = try self.wait("session \(self.sanitize(self.options.session)) in the real status menu") {
            self.menuItem(self.options.session) ?? self.menuItem(self.options.session, contains: true)
        }
        try self.hover(session, purpose: "session:" + self.sanitize(self.options.session))
        self.phase = "preference-submenu"
        let preference = try self.wait("the real \(self.options.preference) submenu") {
            self.menuItem(self.options.preference, under: [session]) ?? self.menuItem(self.options.preference)
        }
        try self.hover(preference, purpose: self.options.preference)
        let names = self.options.preference == "Thinking" ? ["Off", "Minimal", "Low", "Medium", "High"] : ["On", "Off"]
        let expected = self.options.expected == "none" ? [] : [self.options.expected]
        let entries: [AXUIElement] = try self.wait("visible preference choices with refreshed checkmarks") {
            let currentPreference = self.menuItem(self.options.preference) ?? preference
            let found = names.compactMap { self.menuItem($0, under: [currentPreference]) ?? self.menuItem($0) }
            guard found.count == names.count else { return nil }
            let observed = zip(names, found).filter { self.checked($0.1) }.map { $0.0.lowercased() }
            self.record("checkmarkRefresh", ["checked": observed])
            return self.options.dumpOnly || observed == expected ? found : nil
        }
        self.pause(0.25)
        // Unsupported mark and value attributes are missing proof, not an unchecked state.
        for entry in entries {
            let mark = self.attribute(entry, "AXMenuItemMarkChar")
            let value = self.attribute(entry, kAXValueAttribute)
            guard mark.1 == .success || mark.1 == .noValue || value.1 == .success else {
                throw DriverFailure("The visible preference item exposes neither a readable mark nor a value")
            }
        }
        let selected = zip(names, entries).filter { self.checked($0.1) }.map { $0.0.lowercased() }
        self.observations.append([
            "stage": "preferenceChoices", "checked": selected,
            "items": zip(names, entries).map { name, element -> [String: Any] in
                var value = self.snapshot(element)
                value["choice"] = name
                value["checked"] = self.checked(element)
                return value
            },
        ])
        self.observations.append(["stage": "visibleMenuTree", "elements": self.walk(self.roots()).map { self.snapshot($0.0, depth: $0.1) }])
        try self.screenshot("")
        if !self.options.dumpOnly, selected != expected {
            throw DriverFailure("Checkmark mismatch: expected \(expected), observed \(selected)")
        }
        if let choice = self.options.selection {
            guard let index = names.firstIndex(of: choice), let frame = self.rect(entries[index])
            else { throw DriverFailure("Requested selection is unavailable for this preference") }
            self.phase = "select-preference"
            try self.hover(entries[index], purpose: choice)
            let point = CGPoint(x: frame.midX, y: frame.midY)
            try self.mouse(.leftMouseDown, point)
            try self.mouse(.leftMouseUp, point)
            self.record("leftClickPreference", ["choice": choice, "x": point.x, "y": point.y])
            self.pause(0.6)
            // Gateway RPC/readback is the caller's independent check, not inferred from this click.
        }
        self.escape()
        try self.writeResult(self.options.dumpOnly ? "observed-not-asserted" : "passed")
    }

    func failure(_ error: Error) {
        self.observations.append([
            "stage": "AXRootAccess",
            "attributes": [kAXExtrasMenuBarAttribute, kAXMenuBarAttribute, kAXChildrenAttribute, kAXWindowsAttribute].map {
                ["attribute": $0, "readResult": self.attribute(self.application, $0).1.rawValue] as [String: Any]
            },
        ])
        self.observations.append(["stage": "failureAXTree", "elements": self.walk(self.roots()).map { self.snapshot($0.0, depth: $0.1) }])
        try? self.screenshot("-failure")
        self.escape()
        try? self.writeResult("failed", error: String(describing: error))
    }
}

do {
    let options = try Options()
    try FileManager.default.createDirectory(
        at: URL(fileURLWithPath: options.output).deletingLastPathComponent(),
        withIntermediateDirectories: true)
    let driver = MenuDriver(options)
    do {
        try driver.run()
        print("\(options.dumpOnly ? "Observed" : "Passed"): \(options.preference), \(options.expected); evidence \(options.output).json")
    } catch {
        driver.failure(error)
        throw error
    }
} catch {
    FileHandle.standardError.write(Data(("RealAppMenuDriver: \(error)\n").utf8))
    exit(1)
}
