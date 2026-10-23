#!/usr/bin/env python3
"""Build a frozen Linux payload, .deb, portable tarball and AppImage."""
from pathlib import Path
import argparse
import importlib.metadata
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apkforge import __version__


def run(*command, **kwargs):
    subprocess.run(list(map(str, command)), check=True, **kwargs)


def write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)


def freeze(work):
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', work / 'payload', '--workpath', work / 'pyinstaller',
        ROOT / 'packaging/apkforge.spec', cwd=ROOT)
    payload = work / 'payload/apkforge'
    notices = payload / 'licenses'
    notices.mkdir()
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, notices)
    shutil.copy2(ROOT / 'packaging/BUNDLED_NOTICES.md', notices)
    python_license = Path(sys.base_prefix) / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt'
    if not python_license.exists():
        raise FileNotFoundError(f'Missing Python license: {python_license}')
    shutil.copy2(python_license, notices / 'PYTHON-LICENSE.txt')
    versions = [f'Python {platform.python_version()}']
    for name in ('PySide6', 'PySide6-Essentials', 'PySide6-Addons', 'shiboken6', 'pyinstaller'):
        distribution = importlib.metadata.distribution(name)
        versions.append(f'{name} {distribution.version}')
        for file in distribution.files or []:
            if any(word in str(file).lower() for word in ('license', 'copying', 'notice', 'copyright')):
                original = distribution.locate_file(file)
                if original.is_file():
                    destination = notices / name / str(file)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, destination)
    write(notices / 'BUILD-VERSIONS.txt', '\n'.join(versions) + '\n')
    return payload


def deb(payload, output, work):
    staging = work / 'deb-root'
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(payload, staging / 'opt/apkforge', symlinks=True)
    write(staging / 'usr/bin/apkforge', '#!/bin/sh\nexec /opt/apkforge/apkforge "$@"\n', 0o755)
    desktop(staging)
    docs = staging / 'usr/share/doc/apkforge'
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / 'LICENSE', docs / 'copyright')
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', docs)
    size = sum(p.stat().st_size for p in staging.rglob('*') if p.is_file() and not p.is_symlink()) // 1024
    control = (f'Package: apkforge\nVersion: {__version__}\nArchitecture: amd64\n'
               'Maintainer: AxelXrest <AxelXrest@users.noreply.github.com>\n'
               'Section: devel\nPriority: optional\n'
               f'Installed-Size: {size}\n'
               f'Depends: libc6 (>= {platform.libc_ver()[1]}), libstdc++6, libgcc-s1, libegl1, libgl1, '
               'libx11-6, libx11-xcb1, libxcb1, libxcb-cursor0, libxcb-icccm4, '
               'libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, '
               'libxcb-shape0, libxcb-shm0, libxcb-sync1, libxcb-xfixes0, '
               'libxcb-xinerama0, libxcb-xkb1, libxkbcommon0, libxkbcommon-x11-0, '
               'libfontconfig1, libfreetype6, libdbus-1-3, libglib2.0-0, xdg-utils\n'
               'Description: Native Linux interface for Android APK workflows\n'
               ' Decode, rebuild, inspect, align and sign APKs with local Android tools.\n')
    control_tar = work / 'control.tar.gz'
    with tarfile.open(control_tar, 'w:gz') as archive:
        info = tarfile.TarInfo('./control')
        info.size = len(control.encode())
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(control.encode()))
    data_tar = work / 'data.tar.gz'
    with tarfile.open(data_tar, 'w:gz', dereference=False) as archive:
        for path in sorted(staging.iterdir()):
            archive.add(path, arcname='./' + path.name)
    # Debian binary packages are ar archives; keeping this writer in Python also
    # allows building them on Linux distributions without dpkg installed.
    destination = output / f'apkforge_{__version__}_amd64.deb'
    with destination.open('wb') as stream:
        stream.write(b'!<arch>\n')
        for name, source in [('debian-binary', b'2.0\n'), ('control.tar.gz', control_tar), ('data.tar.gz', data_tar)]:
            size = len(source) if isinstance(source, bytes) else source.stat().st_size
            header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{size:<10}`\n'
            stream.write(header.encode('ascii'))
            if isinstance(source, bytes):
                stream.write(source)
            else:
                with source.open('rb') as reader:
                    shutil.copyfileobj(reader, stream)
            if size % 2:
                stream.write(b'\n')
    return destination


def desktop(staging):
    for source, relative in [('apkforge.desktop', 'usr/share/applications/apkforge.desktop'),
                             ('apkforge.svg', 'usr/share/icons/hicolor/scalable/apps/apkforge.svg'),
                             ('apkforge.metainfo.xml', 'usr/share/metainfo/io.github.AxelXrest.APKForge.metainfo.xml')]:
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ('apkforge/assets' if source.endswith('.svg') else 'packaging') / source, target)


def appimage(payload, output, work, tool, runtime):
    appdir = work / 'APKForge.AppDir'
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(payload, appdir / 'usr/lib/apkforge', symlinks=True)
    write(appdir / 'AppRun', '#!/bin/sh\nset -eu\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nunset QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH\nexec "$HERE/usr/lib/apkforge/apkforge" "$@"\n', 0o755)
    write(appdir / 'usr/bin/apkforge', '#!/bin/sh\nHERE=$(CDPATH= cd -- "$(dirname -- "$0")/../lib/apkforge" && pwd)\nexec "$HERE/apkforge" "$@"\n', 0o755)
    desktop(appdir)
    shutil.copy2(ROOT / 'packaging/apkforge.desktop', appdir)
    shutil.copy2(ROOT / 'apkforge/assets/apkforge.svg', appdir)
    (appdir / '.DirIcon').symlink_to('apkforge.svg')
    destination = output / f'APKForge-{__version__}-x86_64.AppImage'
    run(tool, '--appimage-extract-and-run', '--runtime-file', runtime, appdir, destination,
        env={**os.environ, 'ARCH': 'x86_64', 'VERSION': __version__})
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--formats', nargs='+', choices=('deb', 'appimage', 'portable'), default=['deb', 'appimage', 'portable'])
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--work', type=Path, default=ROOT / 'build/native')
    parser.add_argument('--appimagetool', type=Path)
    parser.add_argument('--appimage-runtime', type=Path)
    parser.add_argument('--skip-freeze', action='store_true')
    parser.add_argument('--notices', type=Path, help='Prepared Qt license/attribution directory; required for release builds')
    args = parser.parse_args()
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        parser.error('Native release builds currently target Linux x86_64')
    if 'appimage' in args.formats and (not args.appimagetool or not args.appimagetool.is_file()):
        parser.error('--appimagetool must point to the official executable AppImage tool')
    if 'appimage' in args.formats and (not args.appimage_runtime or not args.appimage_runtime.is_file()):
        parser.error('--appimage-runtime must point to the verified runtime prepared by packaging/prepare.py')
    args.work = args.work.resolve()
    args.output = args.output.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    payload = args.work / 'payload/apkforge' if args.skip_freeze else freeze(args.work)
    if args.notices:
        shutil.copytree(args.notices, payload / 'licenses/Qt', dirs_exist_ok=True)
    else:
        parser.error('--notices is required; run packaging/prepare.py before distributing bundled Qt')
    environment = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_QPA_PLATFORMTHEME': '', 'APKFORGE_OFFLINE': '1'}
    run(payload / 'apkforge', '--self-test', env=environment)
    artifacts = []
    if 'deb' in args.formats:
        artifacts.append(deb(payload, args.output, args.work))
    if 'portable' in args.formats:
        destination = args.output / f'APKForge-{__version__}-linux-x86_64.tar.gz'
        with tarfile.open(destination, 'w:gz', dereference=False) as archive:
            archive.add(payload, arcname='apkforge')
        artifacts.append(destination)
    if 'appimage' in args.formats:
        artifacts.append(appimage(payload, args.output, args.work, args.appimagetool.resolve(), args.appimage_runtime.resolve()))
    for artifact in artifacts:
        print(artifact)


if __name__ == '__main__':
    main()
