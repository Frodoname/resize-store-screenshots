---
name: resize-store-screenshots
description: Use when App Store Connect screenshots or designer-exported store images have the wrong pixel dimensions, aspect ratio, format, or transparency and need resizing on macOS. Applies to still screenshots, not app preview videos or creative redesigns.
---

# Resize Store Screenshots

Prepare exact-size opaque sRGB PNGs while preserving the supplied artwork and originals. This is deterministic file processing: use the bundled resizer rather than regenerating UI, text, or graphics with an image model. No API key or third-party library is needed; requires macOS and a working `swift` command.

## Choose the target

- Use the user's App Store Connect screenshot, required dimensions, device slot, and orientation as the authoritative target for this job. Apple's “app preview” dimensions apply to videos; use the “app screenshots” dimensions for still images.
- When multiple sizes are accepted, choose the one closest to the sources' aspect ratio. For example, 660 × 1434 sources match 1206 × 2622 more closely than 1179 × 2556.
- When the slot or sizes are missing, ask for the needed device/slot information while inspecting inputs. Verify current sizes against [Apple's screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/); do not assume the example sizes are universal.

## Inspect and export

Resolve `scripts/resize.swift` relative to this SKILL.md location. Quote all filesystem paths. In Claude Code, `${CLAUDE_SKILL_DIR}` is available; in Codex, use the absolute path of the loaded skill directory.

Inspect a file or recursive folder without writing:

```sh
swift "<skill-directory>/scripts/resize.swift" --input "<source-folder>"
```

View representative source images, especially differing dimensions, orientations, or visible transparency. Separate screenshots intended for different slots; unexpected square assets require classification rather than blindly resizing everything.

Export to a new directory outside the input tree:

```sh
swift "<skill-directory>/scripts/resize.swift" \
  --input "<source-folder>" --output "<deliverables-folder>/screenshots-1206x2622" \
  --size 1206x2622
```

Default `auto` mode scales proportionally and center-crops only if no dimension loses more than 0.5%. The script refuses larger mismatches before writing. Explain tiny edge trims and any upscaling. Enlarging pixels cannot restore missing source detail.

For a substantial mismatch, present the concrete crop or padding choice before proceeding. `--mode crop` authorizes a centered crop. `--mode pad --background '#RRGGBB'` preserves the complete image and adds the specified background. Use a background consistent with the design and inspect the result. The same background also flattens source transparency; default is white. Never stretch the artwork to force the aspect ratio.

The helper preserves relative subfolders and file order, rejects existing destination files, ignores hidden files and symlinks, applies image orientation, and verifies PNG dimensions, sRGB, and absence of alpha after export. It prints every source/output mapping and crop/padding amounts. Unsupported files are listed as skipped. A failed batch is incomplete: report it and inspect any partial outputs before retrying into a fresh directory.

## Verify and deliver

Compare source and output visually for intact text, layout, crops, and background edges. For varied designs, inspect each output or a contact sheet. Confirm the count matches the selected source set and review the helper's verification output.

Return links to the output folder and a ZIP containing the PNGs, preserving nested paths. Tell the user to unzip and upload the images. State exact dimensions, format, transparency removal, and material quality limitations. Keep originals untouched and use the environment's user-facing deliverables directory. Do not upload to App Store Connect unless requested.
