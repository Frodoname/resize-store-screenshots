# Resize Store Screenshots

A portable skill and skills-only plugin for **Codex, Claude Code, and ChatGPT environments with Python execution**. Resize original screenshot files or an uploaded ZIP into exact-size opaque sRGB PNGs without regenerating artwork.

## Features

- PNG/JPEG files, recursive folders, and ZIP inputs.
- Preserves subfolders; refuses filename collisions and overwrites.
- Proportional Lanczos resizing, explicit crop or padding, orientation correction, and transparency flattening.
- Converts embedded color profiles to sRGB and verifies every PNG.
- Optional ready-to-download ZIP export.

Use the accepted **screenshot** dimensions from the intended App Store Connect device slot. App preview video sizes are different. [Apple’s specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/)

## Requirements

Python 3.10+ and Pillow, on macOS, Windows, Linux, or a cloud execution runtime.

```sh
python -m pip install -r requirements.txt
```

Use a virtual environment where appropriate. On Windows, `py` may be the available launcher. No API key, image generation service, or external resizing server is required.

## Install user-wide for Codex and Claude Code

For a new installation on macOS/Linux:

```sh
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
git clone https://github.com/Frodoname/resize-store-screenshots.git \
  "$HOME/.agents/skills/resize-store-screenshots"
ln -s "$HOME/.agents/skills/resize-store-screenshots" \
  "$HOME/.claude/skills/resize-store-screenshots"
```

Do not overwrite an existing installation; update it deliberately. Codex discovers the root skill; Claude Code follows the shared symlink. Invoke `$resize-store-screenshots` in Codex or `/resize-store-screenshots` in Claude Code. Windows users can copy the root skill and its `scripts`, `requirements.txt`, and `agents` into their respective personal skill directories.

## ChatGPT cloud and plugin packaging

The repository has a portable `plugin.json` and a self-contained skill under `skills/resize-store-screenshots/`. A skills-only plugin can use the host’s existing execution tools; it does not supply its own execution runtime. [OpenAI plugin packaging documentation](https://developers.openai.com/plugins/build/plugins)

For a cloud chat, upload the original screenshots as files or a ZIP, specify the accepted target size, and use the installed plugin. The helper reads the uploaded ZIP directly and returns PNGs plus a ZIP. Your Mac’s filesystem paths are not accessible in a cloud session.

**Distribution status:** this repository and its release ZIPs are plugin packages, not a live public ChatGPT directory listing. Install through a supported local/workspace plugin flow or submit for directory publication. A GitHub repository URL or ZIP attached to a conversation does not automatically install a plugin. [Connection and testing](https://developers.openai.com/plugins/deploy/connect-chatgpt)

The chat must expose a Python/file execution environment with Pillow available or installable. In a chat without file execution, this skills-only package cannot resize files. A remotely hosted MCP resizing service would be needed to supply that capability; no such service is deployed by this project. The ChatGPT installation and cloud execution need an end-to-end test on the target account before being described as verified there.

## Run directly

```sh
python scripts/resize.py --input "/path/to/screenshots.zip"
python scripts/resize.py \
  --input "/path/to/screenshots.zip" \
  --output "/path/to/new screenshots" \
  --size 1206x2622 --zip "/path/to/screenshots-1206x2622.zip"
```

`auto` mode refuses cropping more than 0.5% of either dimension. Reviewed crops can use `--mode crop`. Preserve the full design with `--mode pad --background '#1936BE'`, choosing a background appropriate to the artwork. Transparency is flattened onto that background (white by default). Upscaling cannot recover missing source detail. Review the outputs before uploading to Apple.

ZIP inputs are checked for unsafe paths and symlinks, with image contents limited to 64 MiB per image and 512 MiB total. PNG/JPEG still images only; animated images and videos are excluded. Original inputs are left unchanged.

## Test and package

```sh
python -m unittest discover -s tests
python scripts/package_plugin.py --output "/path/to/resize-store-screenshots-plugin.zip"
```

The packager refreshes the bundled skill from the root skill before writing the plugin ZIP. Tests use synthetic images; no private screenshots are included.

See [SKILL.md](SKILL.md) for the agent workflow.
