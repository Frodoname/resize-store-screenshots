"""Deterministic screenshot resizing for local and cloud Python environments."""
import argparse
from dataclasses import dataclass
import io
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import warnings
import zipfile

try:
    from PIL import Image, ImageCms, ImageColor, ImageOps
except ImportError:
    sys.exit('Pillow is required. Install with: python -m pip install -r requirements.txt')

SUPPORTED = {'.png', '.jpg', '.jpeg'}
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
PROFILE = SRGB.tobytes()
warnings.simplefilter('error', Image.DecompressionBombWarning)


@dataclass
class Entry:
    name: Path
    path: Path | None = None
    archive: zipfile.ZipFile | None = None
    member: zipfile.ZipInfo | None = None

    def read(self):
        return self.path.read_bytes() if self.path else self.archive.read(self.member)


def inventory(source):
    if source.is_file() and source.suffix.lower() == '.zip':
        archive = zipfile.ZipFile(source)
        entries = []
        total = 0
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename or ':' in item.filename:
                raise ValueError(f'Unsafe ZIP entry: {item.filename}')
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError(f'Unsafe ZIP symlink: {item.filename}')
            if item.is_dir() or any(p.startswith('.') or p == '__MACOSX' for p in name.parts):
                continue
            if name.suffix.lower() not in SUPPORTED:
                print(f'SKIPPED unsupported file: {item.filename}')
                continue
            total += item.file_size
            if item.file_size > 64 * 1024 * 1024 or total > 512 * 1024 * 1024:
                raise ValueError('ZIP images exceed supported uncompressed size (64 MiB per image, 512 MiB total)')
            entries.append(Entry(Path(*name.parts), archive=archive, member=item))
        return sorted(entries, key=lambda e: e.name.as_posix()), archive
    if source.is_file():
        candidates = [source]
        root = source.parent
    else:
        root = source
        candidates = []
        for directory, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(directory)/d).is_symlink())
            candidates.extend(Path(directory)/f for f in files if not f.startswith('.'))
    entries = []
    for path in sorted(candidates):
        if path.is_symlink():
            continue
        if path.suffix.lower() in SUPPORTED:
            entries.append(Entry(path.relative_to(root), path=path))
        else:
            print(f'SKIPPED unsupported file: {path}')
    return entries, None


def load(entry):
    with Image.open(io.BytesIO(entry.read())) as source:
        if source.format not in {'PNG', 'JPEG'} or getattr(source, 'n_frames', 1) != 1:
            raise ValueError(f'Unsupported or animated image: {entry.name}')
        source.load()
        return ImageOps.exif_transpose(source).copy()


def opaque_srgb(image, background):
    alpha = image.convert('RGBA').getchannel('A')
    color = image.convert('RGB')
    if image.info.get('icc_profile'):
        profile = ImageCms.ImageCmsProfile(io.BytesIO(image.info['icc_profile']))
        # CMYK JPEGs need their original color model for ICC conversion.
        color_input = image if image.mode in {'RGB', 'CMYK', 'LAB'} else color
        color = ImageCms.profileToProfile(color_input, profile, SRGB, outputMode='RGB')
    base = Image.new('RGB', image.size, background)
    base.paste(color, mask=alpha)
    return base


def main():
    parser = argparse.ArgumentParser(description='Inspect or resize PNG/JPEG screenshots; accepts a file, folder, or uploaded ZIP.')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', help='New output folder')
    parser.add_argument('--size', help='Exact WIDTHxHEIGHT pixels')
    parser.add_argument('--mode', choices=['auto', 'crop', 'pad'], default='auto')
    parser.add_argument('--background', default='#FFFFFF', help='Opaque background as #RRGGBB')
    parser.add_argument('--zip', dest='zip_path', help='Also write an exclusive ZIP of the output PNGs')
    args = parser.parse_args()
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        raise ValueError(f'Input does not exist: {source}')
    if bool(args.output) != bool(args.size) or (args.zip_path and not args.output):
        raise ValueError('Export requires both --output and --size; --zip requires export')
    if len(args.background) != 7 or not args.background.startswith('#'):
        raise ValueError('Background must be #RRGGBB')
    background = ImageColor.getrgb(args.background)
    entries, archive = inventory(source)
    try:
        if not entries:
            raise ValueError('No PNG or JPEG images found')
        if not args.output:
            for entry in entries:
                with load(entry) as image:
                    alpha = 'A' in image.getbands() or 'transparency' in image.info
                    print(f'{entry.name}: {image.width}x{image.height}, alpha={alpha}')
            print(f'Inspected {len(entries)} images. No files written.')
            return
        pieces = args.size.lower().split('x')
        if len(pieces) != 2:
            raise ValueError('Size must be WIDTHxHEIGHT')
        width, height = map(int, pieces)
        if min(width, height) <= 0 or max(width, height) > 16384 or width * height > 100_000_000:
            raise ValueError('Invalid or excessive WIDTHxHEIGHT')
        output = Path(args.output).expanduser().resolve()
        if source.is_dir() and (output == source or source in output.parents):
            raise ValueError('Output must be outside the input directory')
        zip_path = Path(args.zip_path).expanduser().resolve() if args.zip_path else None
        if zip_path and zip_path.exists():
            raise ValueError(f'ZIP output exists: {zip_path}')
        if zip_path and source.is_dir() and (zip_path == source or source in zip_path.parents):
            raise ValueError('ZIP output must be outside the input directory')
        jobs = []
        seen = set()
        for entry in entries:
            target = output / entry.name.with_suffix('.png')
            key = target.as_posix().casefold()
            if key in seen:
                raise ValueError(f'Output filename collision: {entry.name}')
            seen.add(key)
            if target.exists() or target.is_symlink():
                raise ValueError(f'Output exists: {target}')
            if output not in target.resolve().parents:
                raise ValueError(f'Destination escapes output directory: {target}')
            if zip_path == target:
                raise ValueError('ZIP path collides with image output')
            with load(entry) as image:
                scale = max(width/image.width, height/image.height)
                loss = max(1-width/(image.width*scale), 1-height/(image.height*scale))
                if args.mode == 'auto' and loss > 0.005 + 1e-10:
                    raise ValueError(f'Aspect mismatch for {entry.name}: would crop {loss:.2%}. Review --mode crop or --mode pad.')
                # Validate color profiles before writing any batch outputs.
                opaque_srgb(image, background).close()
            jobs.append((entry, target))
        for entry, target in jobs:
            with load(entry) as original:
                image = opaque_srgb(original, background)
                if args.mode == 'pad':
                    scaled = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
                    result = Image.new('RGB', (width, height), background)
                    result.paste(scaled, ((width-scaled.width)//2, (height-scaled.height)//2))
                else:
                    result = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    result.save(stream, format='PNG', icc_profile=PROFILE)
                with Image.open(target) as checked:
                    checked.load()
                    if checked.size != (width, height) or checked.mode != 'RGB' or checked.format != 'PNG' or checked.info.get('icc_profile') != PROFILE or 'transparency' in checked.info:
                        raise ValueError(f'Output verification failed: {target}')
                scale = (min if args.mode == 'pad' else max)(width/original.width, height/original.height)
                dx, dy = abs(original.width*scale-width), abs(original.height*scale-height)
                print(f'VERIFIED {entry.name} -> {target}: {width}x{height}, sRGB PNG, no alpha, scale={scale:.4f}, {args.mode}, edge difference total x={dx:.2f} y={dy:.2f}px')
        if zip_path:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'x', zipfile.ZIP_DEFLATED) as package:
                for _, target in jobs:
                    package.write(target, target.relative_to(output).as_posix())
            print(f'ZIP: {zip_path}')
        print(f'Complete: {len(jobs)} verified images. Originals preserved.')
    finally:
        if archive:
            archive.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning, zipfile.BadZipFile) as error:
        sys.exit(f'Error: {error}')
