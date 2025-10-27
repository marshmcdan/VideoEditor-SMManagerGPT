import SwiftUI
import AVFoundation

/// SwiftUI wrapper to display the unlock workflow inside the AU extension view.
public final class WaveMintViewController: UIViewController {
    private let audioUnit: WaveMintAudioUnit

    public init(audioUnit: WaveMintAudioUnit) {
        self.audioUnit = audioUnit
        super.init(nibName: nil, bundle: nil)
    }

    @MainActor required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    public override func viewDidLoad() {
        super.viewDidLoad()
        let hosting = UIHostingController(rootView: ContentView(viewModel: ViewModel(audioUnit: audioUnit)))
        addChild(hosting)
        hosting.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(hosting.view)
        NSLayoutConstraint.activate([
            hosting.view.topAnchor.constraint(equalTo: view.topAnchor),
            hosting.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            hosting.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            hosting.view.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
        hosting.didMove(toParent: self)
    }
}

// MARK: - SwiftUI front-end

struct ContentView: View {
    @ObservedObject var viewModel: ViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("WaveMint Sample Vault")
                .font(.title2)
                .bold()

            if let asset = viewModel.selectedAsset {
                VStack(alignment: .leading, spacing: 8) {
                    Text(asset.title)
                        .font(.headline)
                    Text("Price: $\(String(format: "%.2f", asset.priceUSD))")
                        .font(.subheadline)
                    Text("Split: \(asset.royaltySplit)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if let message = viewModel.statusMessage {
                Text(message)
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }

            HStack {
                Button(action: { viewModel.fetchPreview() }) {
                    Label("Preview", systemImage: "play.circle")
                }
                .buttonStyle(.borderedProminent)

                Button(action: { viewModel.unlockFullQuality() }) {
                    Label("Unlock", systemImage: "lock.open")
                }
                .buttonStyle(.bordered)
                .disabled(viewModel.isUnlocking)
            }

            if viewModel.isUnlocking {
                ProgressView("Processing x402 payment…")
            }

            List(viewModel.assets) { asset in
                Button(action: { viewModel.select(asset: asset) }) {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(asset.title)
                            Text("$\(String(format: "%.2f", asset.priceUSD)) • \(asset.royaltySplit)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        if viewModel.unlockedAssetIDs.contains(asset.id) {
                            Image(systemName: "checkmark.seal.fill").foregroundColor(.green)
                        }
                    }
                }
            }
        }
        .padding()
        .task { await viewModel.loadAssets() }
    }
}

// MARK: - View Model

extension ContentView {
    final class ViewModel: ObservableObject {
        @Published var assets: [Asset] = []
        @Published var selectedAsset: Asset?
        @Published var statusMessage: String?
        @Published var isUnlocking = false
        @Published var unlockedAssetIDs: Set<String> = []

        private let audioUnit: WaveMintAudioUnit
        private let api = WaveMintGateway()
        private let player = AVAudioPlayerNode()
        private let engine = AVAudioEngine()

        init(audioUnit: WaveMintAudioUnit) {
            self.audioUnit = audioUnit
            engine.attach(player)
            engine.connect(player, to: engine.mainMixerNode, format: nil)
            try? engine.start()
        }

        @MainActor
        func loadAssets() async {
            do {
                assets = try await api.fetchCatalog()
                selectedAsset = assets.first
            } catch {
                statusMessage = "Failed to load catalog: \(error.localizedDescription)"
            }
        }

        func select(asset: Asset) {
            selectedAsset = asset
        }

        func fetchPreview() {
            guard let asset = selectedAsset else { return }
            statusMessage = "Fetching preview…"
            audioUnit.loadPreviewAsset(assetID: asset.id) { [weak self] result in
                DispatchQueue.main.async {
                    switch result {
                    case .success(let url):
                        self?.statusMessage = "Preview ready"
                        self?.play(url: url)
                    case .failure(let error):
                        self?.statusMessage = "Preview failed: \(error.localizedDescription)"
                    }
                }
            }
        }

        func unlockFullQuality() {
            guard let asset = selectedAsset else { return }
            Task {
                await MainActor.run {
                    self.isUnlocking = true
                    self.statusMessage = "Settling payment…"
                }

                do {
                    let context = PurchaseContext(userID: "demo-user", walletSecret: "local-test-secret")
                    let url = try await audioUnit.unlockAsset(assetID: asset.id, context: context)
                    await MainActor.run {
                        self.unlockedAssetIDs.insert(asset.id)
                        self.statusMessage = "Unlocked: \(url.lastPathComponent)"
                        self.play(url: url)
                    }
                } catch {
                    await MainActor.run {
                        self.statusMessage = "Unlock failed: \(error.localizedDescription)"
                    }
                }

                await MainActor.run {
                    self.isUnlocking = false
                }
            }
        }

        private func play(url: URL) {
            do {
                let file = try AVAudioFile(forReading: url)
                player.stop()
                player.scheduleFile(file, at: nil)
                player.play()
            } catch {
                statusMessage = "Playback failed: \(error.localizedDescription)"
            }
        }
    }
}

// MARK: - Models

struct Asset: Identifiable, Codable {
    let id: String
    let title: String
    let priceUSD: Double
    let royaltySplit: String

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case priceUSD = "price_usd"
        case royaltySplit = "royalty_split"
    }
}
