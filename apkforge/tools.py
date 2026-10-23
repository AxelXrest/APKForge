"""Fetch stable upstream tools into private, versioned directories."""
from pathlib import Path
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from . import core


def read_url(url):
    if not url.startswith('https://'):
        raise ValueError('Tool downloads require HTTPS')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'APKForge'}), timeout=30) as response:
        return response.read()


def fetch(url, destination, checksum='', algorithm='sha256'):
    if not url.startswith('https://'):
        raise ValueError('Tool downloads require HTTPS')
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.new(algorithm)
    temporary = None
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'APKForge'})
        with urllib.request.urlopen(request, timeout=30) as response, \
                tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                stream.write(chunk)
        if checksum and digest.hexdigest().lower() != checksum.lower():
            raise ValueError('Download checksum mismatch')
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                target = (destination / entry.filename).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError('Unsafe archive path')
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError('Archive symlinks are not supported')
                package.extract(entry, destination)
                if entry.external_attr >> 16 & 0o111:
                    target.chmod(0o755)
    else:
        with tarfile.open(archive) as package:
            for entry in package.getmembers():
                target = (destination / entry.name).resolve()
                if not target.is_relative_to(destination.resolve()) or not (entry.isfile() or entry.isdir()):
                    # JDK archives may include symlinks; avoid extracting them.
                    if entry.issym() or entry.islnk():
                        continue
                    raise ValueError('Unsafe archive entry')
                package.extract(entry, destination)


def github(root, repo, names):
    release = json.loads(read_url(f'https://api.github.com/repos/{repo}/releases/latest'))
    result = {}
    for name in names:
        assets = [a for a in release['assets'] if a['name'].lower().endswith('.jar')
                  and a['name'].lower().startswith(name.lower())
                  and 'sources' not in a['name'] and 'javadoc' not in a['name']]
        if not assets:
            raise ValueError(f'No runnable {name} JAR in {repo} latest release')
        asset = next((a for a in assets if 'fat' in a['name']), assets[0])
        dest = root / repo.split('/')[-1] / release['tag_name'] / Path(asset['name']).name
        if not dest.is_file():
            digest = asset.get('digest') or ''
            fetch(asset['browser_download_url'], dest, digest.removeprefix('sha256:'))
        result[name] = str(dest)
    return result


def android(root, requested=None):
    if platform.machine() != 'x86_64':
        raise ValueError('Android native tool downloads require Linux x86_64; configure native tools manually')
    tree = ET.fromstring(read_url('https://dl.google.com/android/repository/repository2-1.xml'))
    # Strip namespaces so repository schema revisions remain compatible.
    for node in tree.iter():
        node.tag = node.tag.split('}')[-1]
    result = {}
    for prefix, names in [('build-tools;', ('aapt', 'zipalign', 'apksigner')), ('platform-tools', ('adb',))]:
        if requested is not None and not set(names).intersection(requested):
            continue
        candidates = []
        for package in tree.findall('remotePackage'):
            path = package.get('path', '')
            if not path.startswith(prefix) or package.find('revision/preview') is not None:
                continue
            revision = tuple(int(package.findtext(f'revision/{part}', '0')) for part in ('major', 'minor', 'micro'))
            for archive in package.findall('archives/archive'):
                if archive.findtext('host-os') == 'linux':
                    candidates.append((revision, path, archive))
        if not candidates:
            raise ValueError(f'No stable Linux {prefix} package')
        revision, path, archive = max(candidates, key=lambda item: item[0])
        dest = root / path.replace(';', '-') / '.'.join(map(str, revision))
        if not (dest / '.complete').exists():
            with tempfile.TemporaryDirectory(dir=root) as staging:
                staging = Path(staging)
                download = staging / 'archive.zip'
                checksum = archive.find('complete/checksum')
                fetch('https://dl.google.com/android/repository/' + archive.findtext('complete/url'), download,
                      checksum.text if checksum is not None else '',
                      checksum.get('type', 'sha1') if checksum is not None else 'sha1')
                extracted = staging / 'extracted'
                unpack(download, extracted)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(extracted), dest)
                (dest / '.complete').touch()
        for name in names:
            matches = list(dest.rglob(name))
            executable = next((p for p in matches if p.is_file()), None)
            if executable is None:
                raise ValueError(f'{name} missing from Android package')
            executable.chmod(executable.stat().st_mode | 0o111)
            result[name] = str(executable)
    return result


def java(root):
    arch = {'x86_64': 'x64', 'aarch64': 'aarch64'}.get(platform.machine())
    if not arch:
        raise ValueError('Unsupported Java architecture')
    releases = json.loads(read_url('https://api.adoptium.net/v3/info/available_releases'))
    version = max(releases['available_lts_releases'])
    assets = json.loads(read_url(f'https://api.adoptium.net/v3/assets/latest/{version}/hotspot?architecture={arch}&image_type=jdk&os=linux'))
    asset = assets[0]['binary']['package']
    dest = root / 'java' / assets[0]['release_name']
    if not dest.exists():
        with tempfile.TemporaryDirectory(dir=root) as staging:
            staging = Path(staging)
            download = staging / 'jdk.tar.gz'
            fetch(asset['link'], download, asset['checksum'])
            unpack(download, staging / 'jdk')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging / 'jdk'), dest)
    return {name: str(next(dest.rglob('bin/' + name))) for name in ('java', 'keytool')}


def install_root(settings):
    if settings.tool_install_dir.strip():
        return Path(settings.tool_install_dir).expanduser().absolute()
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return data / 'apkforge' / 'tools'


def available(settings, name):
    if settings.tool(name).lower().endswith('.jar'):
        # Java is detected separately; an absent runtime does not make the JAR missing.
        return Path(settings.tool(name)).expanduser().is_file()
    try:
        settings.command(name)
        return True
    except (ValueError, OSError):
        return False


def discover(settings, name, root):
    """Reuse configured tools, PATH, SDK/JDK locations and local JARs before downloading."""
    if available(settings, name):
        return True
    candidates = []
    command = shutil.which(name)
    if command:
        candidates.append(command)
    if name in ('java', 'keytool') and os.environ.get('JAVA_HOME'):
        candidates.append(str(Path(os.environ['JAVA_HOME']) / 'bin' / name))
    if name in ('aapt', 'zipalign', 'apksigner', 'adb'):
        sdk_roots = [Path(value).expanduser() for key in ('ANDROID_HOME', 'ANDROID_SDK_ROOT')
                     if (value := os.environ.get(key))]
        sdk_roots.append(Path.home() / 'Android' / 'Sdk')
        for sdk in sdk_roots:
            if name == 'adb':
                candidates.append(str(sdk / 'platform-tools' / name))
            else:
                candidates.extend(str(p / name) for p in sorted((sdk / 'build-tools').glob('*'),
                                  key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.name)), reverse=True))
    if name in ('apktool', 'apkeditor', 'baksmali', 'smali'):
        for directory in (Path.cwd(), root):
            candidates.extend(str(p.absolute()) for p in sorted(directory.rglob('*.jar'), reverse=True)
                              if p.name.lower().startswith(name) and 'sources' not in p.name and 'javadoc' not in p.name)
    if name in ('java', 'keytool', 'adb', 'aapt', 'zipalign', 'apksigner'):
        candidates.extend(str(p.absolute()) for p in root.rglob(name) if p.is_file())
    original = settings.tool(name)
    for candidate in candidates:
        setattr(settings, name, candidate)
        if available(settings, name):
            return True
    setattr(settings, name, original)
    return False


def update(*, upgrade=False):
    settings = core.Settings.load()
    root = install_root(settings)
    offline = os.environ.get('APKFORGE_OFFLINE') == '1'
    if offline and upgrade:
        print('Offline mode: tool updates are disabled.', flush=True)
        return
    needed = set(core.TOOLS) if upgrade else set()
    if not upgrade:
        for name in core.TOOLS:
            if discover(settings, name, root):
                print(f'{name}: using existing {settings.tool(name)}', flush=True)
            else:
                needed.add(name)
    providers = [(('java', 'keytool'), lambda names: java(root)),
                 (('apktool',), lambda names: github(root, 'iBotPeaches/Apktool', names)),
                 (('apkeditor',), lambda names: github(root, 'REAndroid/APKEditor', names)),
                 (('baksmali', 'smali'), lambda names: github(root, 'baksmali/smali', names)),
                 (('aapt', 'zipalign', 'apksigner', 'adb'), lambda names: android(root, names))]
    settings.save()
    if offline:
        for name in sorted(needed):
            print(f'{name}: unavailable offline; configure an installed tool in Settings.', flush=True)
        return
    for group, provider in providers:
        names = [name for name in group if name in needed]
        if not names:
            continue
        try:
            root.mkdir(parents=True, exist_ok=True)
            for name, path in provider(names).items():
                if name in names:
                    setattr(settings, name, path)
                    print(f'{name}: {path}', flush=True)
            settings.save()
        except Exception as error:
            print(f'Tool installation unavailable; keeping existing tools: {error}', flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update', action='store_true', help='Fetch latest releases even for available tools')
    update(upgrade=parser.parse_args().update)
