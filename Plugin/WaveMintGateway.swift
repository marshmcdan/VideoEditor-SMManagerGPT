import Foundation

/// Shared HTTP client used by both the Audio Unit kernel and the SwiftUI front-end.
public final class WaveMintGateway {
    private let baseURL: URL
    private let session: URLSession
    private let cacheDirectory: URL

    public init(baseURL: URL = URL(string: "http://127.0.0.1:8000")!, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.cacheDirectory = FileManager.default.temporaryDirectory.appendingPathComponent("WaveMintAssets", isDirectory: true)
        try? FileManager.default.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
    }

    public func fetchCatalog() async throws -> [Asset] {
        let url = baseURL.appendingPathComponent("catalog")
        let (data, _) = try await session.data(from: url)
        let response = try JSONDecoder().decode(CatalogResponse.self, from: data)
        return response.items
    }

    public func fetchPreviewAsset(assetID: String) async throws -> URL {
        let requestURL = baseURL.appendingPathComponent("assets/\(assetID)/preview")
        let (data, _) = try await session.data(from: requestURL)
        let localURL = cacheDirectory.appendingPathComponent("\(assetID)-preview.wav")
        try data.write(to: localURL, options: .atomic)
        return localURL
    }

    public func preparePurchase(assetID: String, userID: String) async throws -> PreparedPurchase {
        var request = URLRequest(url: baseURL.appendingPathComponent("transactions/prepare"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["asset_id": assetID, "user_id": userID]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(PreparedPurchase.self, from: data)
    }

    public func settleInvoice(invoice: String, walletSecret: String) async throws {
        var request = URLRequest(url: baseURL.appendingPathComponent("transactions/settle"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["payment_request": invoice, "wallet_secret": walletSecret]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        _ = try await session.data(for: request)
    }

    public func confirmPurchase(assetID: String, receiptToken: String) async throws -> URL {
        var request = URLRequest(url: baseURL.appendingPathComponent("transactions/confirm"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["asset_id": assetID, "receipt_token": receiptToken]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)
        let response = try JSONDecoder().decode(ConfirmPurchaseResponse.self, from: data)
        guard let url = URL(string: response.downloadURL) else {
            throw NSError(domain: "WaveMintGateway", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid download URL"])
        }

        let (assetData, _) = try await session.data(from: url)
        let localURL = cacheDirectory.appendingPathComponent("\(assetID)-full.wav")
        try assetData.write(to: localURL, options: .atomic)
        return localURL
    }
}

struct CatalogResponse: Codable {
    let items: [Asset]
}

struct PreparedPurchase: Codable {
    let paymentRequest: String
    let receiptToken: String

    enum CodingKeys: String, CodingKey {
        case paymentRequest = "payment_request"
        case receiptToken = "receipt_token"
    }
}

struct ConfirmPurchaseResponse: Codable {
    let downloadURL: String

    enum CodingKeys: String, CodingKey {
        case downloadURL = "download_url"
    }
}
