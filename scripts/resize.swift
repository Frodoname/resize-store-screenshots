import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let fm = FileManager.default
func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data(("Error: " + message + "\n").utf8))
    exit(1)
}
let help = """
Inspect: swift resize.swift --input PATH
Export:  swift resize.swift --input PATH --output DIRECTORY --size WIDTHxHEIGHT
Options: --mode auto|crop|pad (default auto), --background '#RRGGBB' (default white)
Input: PNG, JPG, JPEG; recursive folders, excluding hidden files and symlinks.
Auto refuses cropping more than 0.5% of either dimension. Existing outputs are never overwritten.
"""
var opts: [String: String] = [:]
let args = Array(CommandLine.arguments.dropFirst())
if args.contains("--help") { print(help); exit(0) }
var index = 0
while index < args.count {
    let key = args[index]
    guard ["--input", "--output", "--size", "--mode", "--background"].contains(key), index + 1 < args.count, opts[key] == nil else { fail(help) }
    opts[key] = args[index + 1]
    index += 2
}
guard let inputPath = opts["--input"] else { fail(help) }
func url(_ path: String) -> URL {
    URL(fileURLWithPath: (path as NSString).expandingTildeInPath).standardizedFileURL.resolvingSymlinksInPath()
}
let input = url(inputPath)
var isDir: ObjCBool = false
guard fm.fileExists(atPath: input.path, isDirectory: &isDir) else { fail("Input does not exist: \(input.path)") }
let root = isDir.boolValue ? input : input.deletingLastPathComponent()
let mode = opts["--mode"] ?? "auto"
guard ["auto", "crop", "pad"].contains(mode) else { fail("Unknown mode: \(mode)") }
let colorText = (opts["--background"] ?? "#FFFFFF").replacingOccurrences(of: "#", with: "")
guard colorText.count == 6, let rgb = UInt32(colorText, radix: 16) else { fail("Background must be #RRGGBB") }
let space = CGColorSpace(name: CGColorSpace.sRGB)!
let bg = CGColor(colorSpace: space, components: [CGFloat((rgb >> 16) & 255)/255, CGFloat((rgb >> 8) & 255)/255, CGFloat(rgb & 255)/255, 1])!
var files: [URL] = []
let keys: [URLResourceKey] = [.isRegularFileKey, .isSymbolicLinkKey]
if isDir.boolValue {
    guard let walk = fm.enumerator(at: input, includingPropertiesForKeys: keys, options: [.skipsHiddenFiles]) else { fail("Cannot enumerate input") }
    while let file = walk.nextObject() as? URL {
        let values = try file.resourceValues(forKeys: Set(keys))
        // FileManager's directory enumerator does not descend into symbolic links.
        if values.isSymbolicLink == true { continue }
        if values.isRegularFile == true { files.append(file.resolvingSymlinksInPath()) }
    }
} else { files = [input] }
files.sort { $0.path < $1.path }
let supported = Set(["png", "jpg", "jpeg"])
let skipped = files.filter { !supported.contains($0.pathExtension.lowercased()) }
for file in skipped { print("SKIPPED unsupported file: \(file.path)") }
files = files.filter { supported.contains($0.pathExtension.lowercased()) }
guard !files.isEmpty else { fail("No PNG or JPEG images found") }

func load(_ file: URL) -> CGImage {
    guard let source = CGImageSourceCreateWithURL(file as CFURL, nil), CGImageSourceGetCount(source) == 1,
          let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
          let w = properties[kCGImagePropertyPixelWidth] as? Int,
          let h = properties[kCGImagePropertyPixelHeight] as? Int else { fail("Unreadable or animated image: \(file.path)") }
    let settings: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceCreateThumbnailWithTransform: true, kCGImageSourceThumbnailMaxPixelSize: max(w, h)]
    guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, settings as CFDictionary) else { fail("Cannot decode: \(file.path)") }
    return image
}
func hasAlpha(_ image: CGImage) -> Bool {
    [.first, .last, .premultipliedFirst, .premultipliedLast, .alphaOnly].contains(image.alphaInfo)
}
func relative(_ file: URL) -> String { file.pathComponents.dropFirst(root.pathComponents.count).joined(separator: "/") }
let exporting = opts["--output"] != nil || opts["--size"] != nil
if !exporting {
    for file in files {
        let img = load(file)
        print("\(relative(file)): \(img.width)x\(img.height), alpha=\(hasAlpha(img))")
    }
    print("Inspected \(files.count) images. No files written.")
    exit(0)
}
guard let outputPath = opts["--output"], let size = opts["--size"] else { fail("Export requires both --output and --size") }
let parts = size.lowercased().split(separator: "x")
guard parts.count == 2, let width = Int(parts[0]), let height = Int(parts[1]), width > 0, height > 0,
      width <= 16384, height <= 16384, width * height <= 100_000_000 else { fail("Invalid or excessive WIDTHxHEIGHT") }
let output = url(outputPath)
guard output != root, !output.path.hasPrefix(root.path + "/") else { fail("Output must be outside the input directory") }
struct Job { let input: URL; let output: URL }
var jobs: [Job] = []
var seen = Set<String>()
// Preflight the entire batch before creating any output files.
for file in files {
    let rel = (relative(file) as NSString).deletingPathExtension + ".png"
    let target = output.appendingPathComponent(rel)
    guard seen.insert(target.path.lowercased()).inserted else { fail("Output filename collision: \(rel)") }
    guard !fm.fileExists(atPath: target.path) else { fail("Output exists: \(target.path)") }
    let resolved = target.resolvingSymlinksInPath()
    guard resolved.path.hasPrefix(output.path + "/") else { fail("Destination escapes output directory: \(rel)") }
    let image = load(file)
    let scale = max(Double(width) / Double(image.width), Double(height) / Double(image.height))
    let dw = Double(image.width) * scale, dh = Double(image.height) * scale
    let loss = max(1 - Double(width)/dw, 1 - Double(height)/dh)
    guard mode != "auto" || loss <= 0.005 + 1e-10 else { fail("Aspect mismatch for \(relative(file)): would crop \(String(format: "%.2f", loss * 100))%. Choose --mode crop or --mode pad with an appropriate background after reviewing the design.") }
    jobs.append(Job(input: file, output: target))
}
for job in jobs {
    let image = load(job.input)
    guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: width * 4, space: space, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { fail("Cannot allocate output image") }
    ctx.setFillColor(bg)
    ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
    ctx.interpolationQuality = .high
    let sx = Double(width)/Double(image.width), sy = Double(height)/Double(image.height)
    let scale = mode == "pad" ? min(sx, sy) : max(sx, sy)
    let dw = Double(image.width)*scale, dh = Double(image.height)*scale
    ctx.draw(image, in: CGRect(x: (Double(width)-dw)/2, y: (Double(height)-dh)/2, width: dw, height: dh))
    guard let rendered = ctx.makeImage() else { fail("Cannot create PNG renderer") }
    // Encode into memory, then use exclusive creation to protect existing files.
    let data = NSMutableData()
    guard let encoder = CGImageDestinationCreateWithData(data as CFMutableData, UTType.png.identifier as CFString, 1, nil) else { fail("Cannot create PNG encoder") }
    CGImageDestinationAddImage(encoder, rendered, nil)
    guard CGImageDestinationFinalize(encoder) else { fail("Cannot encode PNG") }
    try fm.createDirectory(at: job.output.deletingLastPathComponent(), withIntermediateDirectories: true)
    try (data as Data).write(to: job.output, options: .withoutOverwriting)
    guard let check = CGImageSourceCreateWithURL(job.output as CFURL, nil), CGImageSourceGetType(check) as String? == UTType.png.identifier,
          let verified = CGImageSourceCreateImageAtIndex(check, 0, nil), verified.width == width, verified.height == height,
          !hasAlpha(verified), verified.colorSpace?.name == CGColorSpace.sRGB else { fail("Output verification failed: \(job.output.path)") }
    print("VERIFIED \(relative(job.input)) -> \(job.output.path): \(width)x\(height), sRGB PNG, no alpha, scale=\(String(format: "%.4f", scale)), \(mode == "pad" ? "padding" : "crop") total x=\(String(format: "%.2f", abs(dw-Double(width)))) y=\(String(format: "%.2f", abs(dh-Double(height)))) pixels")
}
print("Complete: \(jobs.count) verified images. Originals preserved.")
