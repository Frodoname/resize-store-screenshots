# Resize Store Screenshots

A reusable macOS skill for **Codex and Claude Code** that prepares App Store Connect screenshots with exact pixel dimensions, opaque sRGB PNG output, and preserved artwork.

## Features

- Processes a single image or a recursive folder of PNG/JPEG images.
- Preserves subfolders and filenames, preventing duplicate-name collisions.
- Scales proportionally and removes alpha channels.
- Refuses overwrites and output directories inside the input tree.
- Allows only tiny crops by default; explicit crop and padding modes handle larger aspect differences.
- Verifies dimensions, PNG format, sRGB color space, and absence of transparency.

App Store screenshot sizes depend on the device slot. Supply the accepted dimensions from App Store Connect or consult [Apple’s current specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/). Still screenshots and app preview videos use different requirements.

## Requirements

macOS with a working `swift` command. No API key, image generation service, or third-party package is needed. If Swift is unavailable, install Apple’s Command Line Tools with `xcode-select --install`.

## Install user-wide

These commands assume the destination does not already exist:

```sh
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
git clone https://github.com/Frodoname/resize-store-screenshots.git \
  "$HOME/.agents/skills/resize-store-screenshots"
ln -s "$HOME/.agents/skills/resize-store-screenshots" \
  "$HOME/.claude/skills/resize-store-screenshots"
```

Codex discovers the skill in `~/.agents/skills`. Claude Code uses the symlink in `~/.claude/skills`. Both share one copy. Start a new session if it is not listed yet.

- Codex: invoke `$resize-store-screenshots` and provide the input path and target size.
- Claude Code: invoke `/resize-store-screenshots` with the same information.

## Run the helper directly

Inspect without writing:

```sh
swift scripts/resize.swift --input "/path/to/source screenshots"
```

Export an example size accepted for the selected screenshot slot:

```sh
swift scripts/resize.swift \
  --input "/path/to/source screenshots" \
  --output "/path/to/exported screenshots" \
  --size 1206x2622
```

Default `auto` mode refuses cropping more than 0.5% of either dimension. For a reviewed crop, add `--mode crop`. To preserve the whole image with padding, add `--mode pad --background '#RRGGBB'`, replacing the hex value with the intended background color. White is the default background for flattening transparency.

Enlargement cannot recover missing detail from a low-resolution export. Visually review outputs before upload. The skill does not upload files to App Store Connect.

See [SKILL.md](SKILL.md) for the complete agent workflow and `swift scripts/resize.swift --help` for options.
