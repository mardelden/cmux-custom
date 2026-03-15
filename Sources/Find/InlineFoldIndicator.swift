import SwiftUI

/// Inline fold indicator bar that scrolls with terminal content.
/// Shows a thin horizontal bar at the fold boundary indicating how many lines are folded.
/// Click handling is done at the NSView level (FoldIndicatorHostingView) to
/// distinguish clicks (expand) from drags (selection passthrough).
struct InlineFoldIndicator: View {
    let foldedLines: Int

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "chevron.right")
                .font(.system(size: 9, weight: .semibold, design: .monospaced))
                .foregroundStyle(.tertiary)

            Text(String(
                localized: "fold.inline.linesFolded",
                defaultValue: "\(foldedLines) lines folded"
            ))
            .font(.system(size: 11, weight: .medium, design: .monospaced))
            .foregroundStyle(.tertiary)

            // Horizontal rule extending to the right
            Rectangle()
                .fill(.separator)
                .frame(height: 1)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.5))
        .contentShape(Rectangle())
    }
}
