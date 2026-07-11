import SwiftUI

// Terminal (1c) tasarim dili token'lari — bkz. design handoff README.
enum CVZ {
    static let bg      = Color(red: 0.051, green: 0.059, blue: 0.055)  // #0D0F0E
    static let panel   = Color(red: 0.075, green: 0.090, blue: 0.082)  // #131715
    static let line    = Color.white.opacity(0.12)
    static let lineSoft = Color.white.opacity(0.10)
    static let text    = Color(red: 0.863, green: 0.898, blue: 0.878)  // #DCE5E0
    static let textSub = Color(red: 0.624, green: 0.667, blue: 0.643)  // #9FAAA4
    static let textDim = Color(red: 0.431, green: 0.478, blue: 0.455)  // #6E7A74
    static let accent  = Color(red: 0.275, green: 0.714, blue: 0.580)  // #46B694
    static let accentBg = Color(red: 0.275, green: 0.714, blue: 0.580).opacity(0.11)
    static let ok      = Color(red: 0.333, green: 0.690, blue: 0.471)  // #55B078
    static let okBg    = Color(red: 0.333, green: 0.690, blue: 0.471).opacity(0.15)
    static let warn    = Color(red: 0.878, green: 0.639, blue: 0.231)  // #E0A33B
    static let warnBg  = Color(red: 0.878, green: 0.639, blue: 0.231).opacity(0.15)
    static let err     = Color(red: 0.886, green: 0.341, blue: 0.298)  // #E2574C
    static let errBg   = Color(red: 0.886, green: 0.341, blue: 0.298).opacity(0.15)

    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }

    static func statusColor(_ status: String) -> Color {
        switch status {
        case "completed": return ok
        case "failed": return err
        case "running", "queued", "processing": return warn
        default: return textDim
        }
    }

    static func statusBg(_ status: String) -> Color {
        switch status {
        case "completed": return okBg
        case "failed": return errBg
        case "running", "queued", "processing": return warnBg
        default: return Color.white.opacity(0.06)
        }
    }

    static func statusTag(_ status: String) -> String {
        switch status {
        case "completed": return "[TAMAM]"
        case "failed": return "[HATA]"
        case "running": return "[ÇALIŞIYOR]"
        case "queued": return "[SIRADA]"
        default: return "[\(status.uppercased())]"
        }
    }
}

// Durum cipi: [TAMAM] / [HATA] / [ÇALIŞIYOR]
struct CVZStatusChip: View {
    let status: String
    var size: CGFloat = 8.5

    var body: some View {
        Text(CVZ.statusTag(status))
            .font(CVZ.mono(size, .semibold))
            .foregroundColor(CVZ.statusColor(status))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(CVZ.statusBg(status), in: RoundedRectangle(cornerRadius: 4))
    }
}
