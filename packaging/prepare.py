#!/usr/bin/env python3
"""Download pinned AppImage tooling and upstream Qt sources/notices for a build."""
from pathlib import Path
import argparse
import hashlib
import shutil
import sys
import tarfile
import urllib.request

VERSION = '6.8.3'
TOOL_URL = 'https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage'
TOOL_SHA256 = 'ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0'
RUNTIME_URL = 'https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64'
RUNTIME_SHA256 = '617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46'
SOURCES = ('qt/qtbase', 'qt/qtsvg', 'qt/qtwayland', 'qt/qttranslations', 'pyside/pyside-setup')


def download(url, path, checksum=None):
    if path.exists() and (not checksum or hashlib.sha256(path.read_bytes()).hexdigest() == checksum):
        return
    temporary = path.with_suffix(path.suffix + '.part')
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'APKForge-release-build'})
        digest = hashlib.sha256()
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                digest.update(chunk)
        if checksum and digest.hexdigest() != checksum:
            raise ValueError(f'Checksum mismatch: {path.name}')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('dist'))
    parser.add_argument('--work', type=Path, default=Path('build/native'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    notices = args.work / 'notices'
    notices.mkdir(exist_ok=True)
    for repository in SOURCES:
        name = repository.split('/')[-1]
        archive = args.output / f'{name}-{VERSION}-source.tar.gz'
        print(f'Preparing {repository} {VERSION}', flush=True)
        download(f'https://codeload.github.com/{repository}/tar.gz/refs/tags/v{VERSION}', archive)
        with tarfile.open(archive) as source:
            count = 0
            for member in source:
                relative = Path(*Path(member.name).parts[1:])
                if not member.isfile() or '..' in relative.parts or relative.is_absolute():
                    continue
                lower = str(relative).lower()
                if not (any(word in lower for word in ('license', 'licence', 'copying', 'copyright', 'notice'))
                        or relative.name == 'qt_attribution.json'):
                    continue
                target = notices / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as reader, target.open('wb') as writer:
                    shutil.copyfileobj(reader, writer)
                count += 1
            if not count:
                raise RuntimeError(f'No license material found in {archive}')
    # Include distribution notices for native libraries PyInstaller may collect.
    system = Path('/usr/share/doc')
    for copyright_file in system.glob('*/copyright'):
        target = notices / 'system' / copyright_file.parent.name / 'copyright'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(copyright_file, target)
    tool = args.work / 'appimagetool-x86_64.AppImage'
    print('Preparing verified appimagetool 1.9.1', flush=True)
    download(TOOL_URL, tool, TOOL_SHA256)
    tool.chmod(0o755)
    runtime = args.work / 'runtime-x86_64'
    print('Preparing verified AppImage runtime', flush=True)
    download(RUNTIME_URL, runtime, RUNTIME_SHA256)
    print(f'Notices: {notices}\nAppImage tool: {tool}\nRuntime: {runtime}')


if __name__ == '__main__':
    main()
