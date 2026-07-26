import SwiftUI
import VisionKit

/// QR okuyucu (VisionKit DataScannerViewController). ceviz://pair barkodunu
/// yakalayinca `onScan` ile ham metni doner ve durur.
struct QRScannerView: UIViewControllerRepresentable {
    let onScan: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onScan: onScan) }

    func makeUIViewController(context: Context) -> UIViewController {
        guard DataScannerViewController.isSupported, DataScannerViewController.isAvailable else {
            return UnavailableController()
        }
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.qr])],
            qualityLevel: .balanced,
            isHighlightingEnabled: true
        )
        scanner.delegate = context.coordinator
        context.coordinator.scanner = scanner
        try? scanner.startScanning()
        return scanner
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onScan: (String) -> Void
        weak var scanner: DataScannerViewController?
        private var handled = false

        init(onScan: @escaping (String) -> Void) { self.onScan = onScan }

        func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            handle(addedItems)
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didTapOn item: RecognizedItem) {
            handle([item])
        }

        private func handle(_ items: [RecognizedItem]) {
            guard !handled else { return }
            for item in items {
                if case let .barcode(barcode) = item, let value = barcode.payloadStringValue {
                    handled = true
                    scanner?.stopScanning()
                    onScan(value)
                    return
                }
            }
        }
    }

    /// VisionKit desteklenmiyorsa (nadir) bilgilendirici ekran.
    final class UnavailableController: UIViewController {
        override func viewDidLoad() {
            super.viewDidLoad()
            view.backgroundColor = .black
            let label = UILabel()
            label.text = "Bu cihazda QR tarama desteklenmiyor.\nAdres ve token'ı elle gir."
            label.numberOfLines = 0
            label.textAlignment = .center
            label.textColor = .white
            label.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(label)
            NSLayoutConstraint.activate([
                label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
                label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
                label.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 24),
                label.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -24),
            ])
        }
    }
}
