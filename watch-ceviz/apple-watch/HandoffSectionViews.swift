import SwiftUI

struct HandoffSectionContainer<Content: View>: View {
    let title: String
    let systemImage: String
    var compact: Bool = false
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 4 : 8) {
            Label(title, systemImage: systemImage)
                .font(compact ? .caption2 : .caption)
                .fontWeight(.semibold)
                .foregroundColor(.green)

            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(compact ? 6 : 8)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.green.opacity(0.12))
        )
    }
}

struct HandoffSectionCard: View {
    let section: HandoffPreviewSection
    var lineLimit: Int = 2
    var compact: Bool = false

    var body: some View {
        HandoffMessageCard(
            eyebrow: section.eyebrow,
            title: section.title,
            systemImage: section.icon,
            message: section.content,
            lineLimit: lineLimit,
            compact: compact
        )
    }
}

struct HandoffMessageCard: View {
    let eyebrow: String
    let title: String
    let systemImage: String
    let message: String
    var lineLimit: Int = 2
    var compact: Bool = false

    var body: some View {
        Group {
            if compact {
                cardBody
            } else {
                cardBody
                    .padding(6)
                    .background(Color.white.opacity(0.72), in: RoundedRectangle(cornerRadius: 8))
            }
        }
    }

    private var cardBody: some View {
        VStack(alignment: .leading, spacing: compact ? 2 : 3) {
            Text(eyebrow)
                .font(.system(size: 9, weight: .semibold))
                .foregroundColor(.green)

            Label(title, systemImage: systemImage)
                .font(.caption2)
                .fontWeight(.semibold)
                .foregroundColor(.primary)

            Text(message)
                .font(.caption2)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.leading)
                .lineLimit(lineLimit)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct HandoffOpenPanel: View {
    let buttonTitle: String
    let subtitle: String
    let preview: HandoffPreview?
    let isReachable: Bool
    var showsExpandedPreview: Bool = false
    let action: () -> Void

    var body: some View {
        VStack(spacing: 3) {
            Button(action: action) {
                HStack {
                    Text("→ IPHONE'DA AÇ")
                        .font(CVZ.mono(10.5, .semibold))
                        .foregroundColor(CVZ.accent)
                    Spacer()
                    Text("rapor hazır")
                        .font(CVZ.mono(9))
                        .foregroundColor(CVZ.textDim)
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 8)
                .background(CVZ.accentBg, in: RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(CVZ.accent, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .disabled(!isReachable)

            if !isReachable {
                Text("iPhone erişilebilir olmalı")
                    .font(CVZ.mono(9))
                    .foregroundColor(CVZ.textDim)
            } else if !subtitle.isEmpty {
                Text(subtitle)
                    .font(CVZ.mono(9))
                    .foregroundColor(CVZ.textDim)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct JobContinuationBadge: View {
    let preview: HandoffPreview?
    var compact: Bool = false

    var body: some View {
        HandoffSectionContainer(title: "iPhone'da devamı var", systemImage: "iphone", compact: compact) {
            if let firstSection = preview?.sectionSnippets.first {
                HandoffSectionCard(section: firstSection, lineLimit: compact ? 1 : 2, compact: true)
            } else {
                HandoffMessageCard(
                    eyebrow: "IPHONE",
                    title: "Devam hazır",
                    systemImage: "arrow.triangle.branch",
                    message: "Tam raporu telefonda açın.",
                    lineLimit: 2,
                    compact: true
                )
            }
        }
    }
}

struct ReportSectionCard: View {
    let section: ReportBodySectionPayload

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: section.icon)
                    .foregroundColor(.blue)
                    .font(.system(size: 12))
                Text(section.eyebrow.uppercased())
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(.blue)
            }
            
            Text(section.title)
                .font(.caption)
                .fontWeight(.bold)
            
            Text(section.content)
                .font(.caption2)
                .foregroundColor(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.blue.opacity(0.1)))
    }
}


