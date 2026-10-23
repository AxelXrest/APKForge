"""Local file operations run as child jobs to keep the GUI responsive."""
from __future__ import annotations
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from . import core
from .runtime import external_environment


def fix_project(directory):
    root = Path(core.require_dir(directory))
    changed = []
    for path in (root / 'res').glob('values*/*.xml'):
        if path.is_symlink():
            continue
        text = path.read_text(encoding='utf-8')
        if not re.search(r'APKTOOL_DUMMY|DUMMY_APKTOOL', text):
            continue
        tree = ET.fromstring(text)
        # Remove resource entries, preserving the surrounding XML document.
        for parent in tree.iter():
            for child in list(parent):
                if re.search(r'APKTOOL_DUMMY|DUMMY_APKTOOL', child.get('name', '')):
                    parent.remove(child)
        backup(path)
        path.write_bytes(ET.tostring(tree, encoding='utf-8', xml_declaration=True))
        changed.append(str(path.relative_to(root)))
    yml = root / 'apktool.yml'
    if yml.is_file() and not yml.is_symlink():
        text = yml.read_text(encoding='utf-8')
        updated = text.replace('sparseResources: true', 'sparseResources: false')
        if updated != text:
            backup(yml)
            yml.write_text(updated, encoding='utf-8')
            changed.append('apktool.yml')
    manifest = root / 'AndroidManifest.xml'
    if manifest.is_file() and not manifest.is_symlink():
        text = manifest.read_text(encoding='utf-8')
        updated = text
        for attribute, value in (('isSplitRequired', 'true'), ('extractNativeLibs', 'false'),
                                 ('useEmbeddedDex', 'true'), ('manageSpace', 'true'),
                                 ('localeConfig', '@xml/locales_config')):
            updated = updated.replace(f'android:{attribute}="{value}"', '')
        updated = re.sub(r'\s*android:(?:requiredSplitTypes|splitTypes)="[^"]*"', '', updated)
        updated = updated.replace('STAMP_TYPE_DISTRIBUTION_APK', 'STAMP_TYPE_STANDALONE_APK')
        if updated != text:
            ET.fromstring(updated)  # Never replace the manifest with invalid XML.
            backup(manifest)
            manifest.write_text(updated, encoding='utf-8')
            changed.append('AndroidManifest.xml')
    print('Project fixes: ' + (', '.join(changed) if changed else 'no changes needed'))
    if changed:
        print('Original files retained as .apkforge.bak backups.')


def backup(path):
    dest = path.with_name(path.name + '.apkforge.bak')
    if not dest.exists():
        shutil.copy2(path, dest)


def unsigned(original_project, built, dest):
    root = Path(core.require_dir(original_project)) / 'original'
    meta = root / 'META-INF'
    if not meta.is_dir():
        raise ValueError('Project has no original/META-INF. Original signature metadata is required.')
    files = {p.relative_to(root).as_posix(): p for p in meta.rglob('*') if p.is_file() and not p.is_symlink()}
    if (root / 'stamp-cert-sha256').is_file():
        files['stamp-cert-sha256'] = root / 'stamp-cert-sha256'
    destination = Path(core.output(dest, '.apk'))
    core._different(built, destination)
    handle, temporary = tempfile.mkstemp(prefix='.apkforge-', suffix='.apk', dir=destination.parent)
    import os
    os.close(handle)
    try:
        with zipfile.ZipFile(core.require_file(built)) as src, zipfile.ZipFile(temporary, 'w') as out:
            for entry in src.infolist():
                if not entry.filename.upper().startswith('META-INF/') and entry.filename != 'stamp-cert-sha256':
                    with src.open(entry) as reader, out.open(entry, 'w') as writer:
                        shutil.copyfileobj(reader, writer)
            for name, path in files.items():
                out.write(path, name)
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(f'Unsigned APK with original signature metadata: {destination}')
    print('This preserves metadata only; it does not produce a valid signature for a modified APK.')


def main():
    action, *args = sys.argv[1:]
    if action == 'fix':
        fix_project(*args)
    elif action == 'unsigned':
        unsigned(*args)
    elif action == 'default-key':
        import os
        import subprocess
        key = Path(args[0])
        if not key.exists():
            key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.TemporaryDirectory(dir=key.parent) as staging:
                temporary = Path(staging) / 'development.jks'
                command = core.Settings.load().command('keytool') + [
                    '-genkeypair', '-keystore', str(temporary), '-storetype', 'JKS',
                    '-storepass:env', 'APKFORGE_DEFAULT_PASS', '-keypass:env', 'APKFORGE_DEFAULT_PASS',
                    '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048',
                    '-validity', '10000', '-dname', 'CN=Android Debug,O=Android,C=US', '-noprompt']
                subprocess.run(command, env={**external_environment(), 'APKFORGE_DEFAULT_PASS': 'android'}, check=True)
                temporary.chmod(0o600)
                # Do not replace an identity created by another app instance.
                try:
                    os.link(temporary, key)
                except FileExistsError:
                    pass
        print(f'Default development key ready: {key}')
    elif action == 'delete-idsig':
        Path(args[0] + '.idsig').unlink(missing_ok=True)
    else:
        raise ValueError(f'Unknown file operation: {action}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
