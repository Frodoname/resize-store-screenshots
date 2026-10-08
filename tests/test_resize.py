import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageCms

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/resize.py'


class ResizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.output = self.root / 'output'
        for folder in ('01', '02'):
            directory = self.source / folder
            directory.mkdir()
            image = Image.new('RGBA', (660, 1434), (25, 54, 190, 255))
            image.putpixel((0, 0), (0, 0, 0, 0))
            image.save(directory / 'same.png')
        self.before = self.hashes()

    def tearDown(self):
        self.temp.cleanup()

    def hashes(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.rglob('*.png')}

    def run_tool(self, *extra, source=None):
        return subprocess.run([sys.executable, str(SCRIPT), '--input', str(source or self.source), *extra], text=True, capture_output=True)

    def export(self, size='1206x2622', *extra, source=None):
        return self.run_tool('--output', str(self.output), '--size', size, *extra, source=source)

    def test_batch_integrity_and_exclusive_creation(self):
        result = self.export()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('01/same.png', '02/same.png'):
            with Image.open(self.output / name) as image:
                self.assertEqual(image.size, (1206, 2622))
                self.assertEqual(image.mode, 'RGB')
                self.assertEqual(image.format, 'PNG')
                profile = ImageCms.ImageCmsProfile(io.BytesIO(image.info['icc_profile']))
                self.assertIn('sRGB', ImageCms.getProfileDescription(profile))
        self.assertEqual(self.before, self.hashes())
        old = (self.output / '01/same.png').read_bytes()
        self.assertNotEqual(self.export().returncode, 0)
        self.assertEqual(old, (self.output / '01/same.png').read_bytes())

    def test_big_mismatch_refused_before_export(self):
        result = self.export('1000x1000')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('aspect', result.stderr.lower())
        self.assertFalse(self.output.exists())

    def test_padding_background_and_transparency(self):
        result = self.export('1000x1000', '--mode', 'pad', '--background', '#FF0000')
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(self.output / '01/same.png') as image:
            self.assertEqual(image.getpixel((0, 500)), (255, 0, 0))
            self.assertEqual(image.getpixel((500, 500)), (25, 54, 190))

    def test_zip_input_and_zip_output(self):
        archive = self.root / 'input.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for p in self.source.rglob('*.png'):
                z.write(p, p.relative_to(self.source).as_posix())
        package = self.root / 'output.zip'
        result = self.export('1206x2622', '--zip', str(package), source=archive)
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(package) as z:
            self.assertEqual(sorted(z.namelist()), ['01/same.png', '02/same.png'])

    def test_unsafe_zip_refused(self):
        archive = self.root / 'input.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('../escape.png', (self.source / '01/same.png').read_bytes())
        result = self.export(source=archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsafe', result.stderr.lower())
        self.assertFalse(self.output.exists())

    def test_collisions_and_nested_outputs_refused(self):
        result = self.run_tool('--size', '1206x2622', '--output', str(self.source / 'out'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.source / 'out').exists())
        Image.new('RGB', (660, 1434)).save(self.source / '01/same.jpg')
        result = self.export()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('collision', result.stderr.lower())
        self.assertFalse(self.output.exists())

    def test_orientation_and_hidden_files(self):
        for p in self.source.rglob('*.png'):
            p.unlink()
        image = Image.new('RGB', (40, 20), 'blue')
        exif = Image.Exif()
        exif[274] = 6
        image.save(self.source / 'rotated.jpg', exif=exif)
        image.save(self.source / '.hidden.jpg')
        result = self.export('20x40')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.output.rglob('*.png'))), 1)
        with Image.open(self.output / 'rotated.png') as result_image:
            self.assertEqual(result_image.size, (20, 40))

    def test_alpha_flattened_on_exact_size(self):
        result = self.export('660x1434')
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(self.output / '01/same.png') as image:
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(image.getpixel((330, 717)), (25, 54, 190))

    def test_plugin_package_is_self_contained(self):
        archive = self.root / 'plugin.zip'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/package_plugin.py'), '--output', str(archive)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(set(package.namelist()), {
                'plugin.json', 'README.md', 'skills/resize-store-screenshots/SKILL.md',
                'skills/resize-store-screenshots/requirements.txt',
                'skills/resize-store-screenshots/agents/openai.yaml',
                'skills/resize-store-screenshots/scripts/resize.py',
            })
            self.assertEqual(package.read('skills/resize-store-screenshots/scripts/resize.py'), SCRIPT.read_bytes())


if __name__ == '__main__':
    unittest.main()
