"""Synchronize the root skill and produce a self-contained portable plugin ZIP."""
import argparse
from pathlib import Path
import shutil
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args = parser.parse_args()
bundle = root / 'skills/resize-store-screenshots'
bundle.mkdir(parents=True, exist_ok=True)
paths = ['SKILL.md', 'requirements.txt', 'agents/openai.yaml', 'scripts/resize.py']
for relative in paths:
    target = bundle / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / relative, target)
output = Path(args.output).expanduser().resolve()
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as package:
    for relative in ['plugin.json', 'README.md']:
        package.write(root / relative, relative)
    for relative in paths:
        path = bundle / relative
        package.write(path, path.relative_to(root).as_posix())
print(f'Plugin ZIP: {output}')
