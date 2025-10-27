import AVFoundation
import os.log

/// Core audio processing unit. For the prototype we bypass DSP and act as an asset-unlocker
/// that streams purchased stems into the host's buffer list once settlement succeeds.
public final class WaveMintAudioUnit: AUAudioUnit {
    private let logger = Logger(subsystem: "com.wavemint.plugin", category: "WaveMintAudioUnit")

    private var parameterTreeRef: AUParameterTree?
    private var unlockedAssets: [String: URL] = [:] // assetID -> local file URL
    private let assetGateway = WaveMintGateway()

    public override init(componentDescription: AudioComponentDescription, options: AudioComponentInstantiationOptions = []) throws {
        try super.init(componentDescription: componentDescription, options: options)
        setupParameters()
    }

    // MARK: - AU Setup

    private func setupParameters() {
        let gain = AUParameterTree.createParameter(withIdentifier: "gain",
                                                   name: "Gain",
                                                   address: 0,
                                                   min: 0.0,
                                                   max: 1.0,
                                                   unit: .linearGain,
                                                   unitName: nil,
                                                   flags: [.flag_IsReadable, .flag_IsWritable],
                                                   valueStrings: nil,
                                                   dependentParameters: nil)
        gain.value = 1.0
        parameterTreeRef = AUParameterTree(children: [gain])
    }

    public override var parameterTree: AUParameterTree? {
        return parameterTreeRef
    }

    // MARK: - Asset lifecycle

    /// Fetches and caches a preview asset for auditioning.
    public func loadPreviewAsset(assetID: String, completion: @escaping (Result<URL, Error>) -> Void) {
        Task {
            do {
                let url = try await assetGateway.fetchPreviewAsset(assetID: assetID)
                completion(.success(url))
            } catch {
                logger.error("Failed to fetch preview: \(error.localizedDescription)")
                completion(.failure(error))
            }
        }
    }

    /// Initiates payment and unlock flow for a full-resolution asset.
    public func unlockAsset(assetID: String, context: PurchaseContext) async throws -> URL {
        logger.log("Preparing settlement for asset: \(assetID, privacy: .public)")
        let prepared = try await assetGateway.preparePurchase(assetID: assetID, userID: context.userID)

        logger.log("Paying invoice on x402 testnet")
        try await assetGateway.settleInvoice(invoice: prepared.paymentRequest, walletSecret: context.walletSecret)

        logger.log("Confirming unlock")
        let assetURL = try await assetGateway.confirmPurchase(assetID: assetID, receiptToken: prepared.receiptToken)
        unlockedAssets[assetID] = assetURL
        return assetURL
    }

    /// In a production plug-in we would copy the audio into an AVAudioPCMBuffer.
    /// Here we simply notify the host that the asset is ready.
    public func assetURL(for assetID: String) -> URL? {
        return unlockedAssets[assetID]
    }
}

public struct PurchaseContext {
    public let userID: String
    public let walletSecret: String

    public init(userID: String, walletSecret: String) {
        self.userID = userID
        self.walletSecret = walletSecret
    }
}
