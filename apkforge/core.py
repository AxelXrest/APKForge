"""Validated Android tool commands. Commands are argument lists, never shell scripts."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field, fields
from pathlib import Path
import json
import os
import re
import shlex
import shutil

CONFIG = Path.home() / '.config' / 'apkforge' / 'settings.json'
TOOLS = ('java', 'apktool', 'apkeditor', 'adb', 'aapt', 'zipalign', 'apksigner', 'keytool', 'baksmali', 'smali')
PACKAGES = {'.apk', '.apks', '.xapk', '.apkm', '.zip'}


@dataclass
class Settings:
    java: str = 'java'
    apktool: str = 'apktool'
    apkeditor: str = ''
    adb: str = 'adb'
    aapt: str = 'aapt'
    zipalign: str = 'zipalign'
    apksigner: str = 'apksigner'
    keytool: str = 'keytool'
    baksmali: str = 'baksmali'
    smali: str = 'smali'
    tool_install_dir: str = ''
    jvm_args: str = '-Dfile.encoding=UTF8'
    theme: str = 'Dark'
    language: str = 'en'
    temp_dir: str = ''
    clear_log: bool = False
    play_sound: bool = False
    open_output: bool = False
    preferences: dict = field(default_factory=dict)

    @classmethod
    def load(cls):
        try:
            data = json.loads(CONFIG.read_text())
            valid = {f.name for f in fields(cls)}
            values = {k: v for k, v in data.items() if k in valid}
            defaults = cls()
            values = {k: v for k, v in values.items() if isinstance(v, type(getattr(defaults, k)))}
            return cls(**values)
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        temporary = CONFIG.with_suffix('.tmp')
        # Create with restricted permissions before writing, including when replacing old configs.
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(asdict(self), stream, indent=2)
        os.chmod(temporary, 0o600)
        temporary.replace(CONFIG)

    def tool(self, name):
        return getattr(self, name).strip()

    def command(self, name):
        item = self.tool(name)
        if not item:
            raise ValueError(f'{name} is not configured. Open Settings → Tool paths.')
        if item.lower().endswith('.jar'):
            jar = require_file(item)
            java = self._executable(self.java.strip(), 'java')
            return [java, *shlex.split(self.jvm_args), '-jar', jar]
        return [self._executable(item, name)]

    @staticmethod
    def _executable(item, name):
        if '/' in item or item.startswith('~'):
            path = require_file(item)
            if not os.access(path, os.X_OK):
                raise ValueError(f'{name} is not executable: {path}')
            return path
        if not item or not shutil.which(item):
            raise FileNotFoundError(f'{name} not installed/in PATH: {item}')
        return item


def nonempty(path):
    if not str(path).strip():
        raise ValueError('Choose a file or folder first.')
    return Path(path).expanduser().absolute()


def require_file(path, ext=None):
    p = nonempty(path)
    if not p.is_file():
        raise FileNotFoundError(f'File not found: {p}')
    if ext and p.suffix.lower() not in ext:
        raise ValueError(f'Expected {", ".join(sorted(ext))}, got {p.suffix}')
    return str(p)


def require_dir(path):
    p = nonempty(path)
    if not p.is_dir():
        raise NotADirectoryError(f'Folder not found: {p}')
    return str(p)


def output(path, suffix=None):
    p = nonempty(path)
    if suffix and p.suffix.lower() != suffix:
        raise ValueError(f'Output path must end with {suffix}')
    if not p.parent.is_dir():
        raise NotADirectoryError(f'Output parent does not exist: {p.parent}')
    if p.is_dir():
        raise ValueError(f'Output is a directory: {p}')
    return str(p)


def output_dir(path):
    p = nonempty(path)
    if not p.parent.is_dir() or p == p.parent or p.is_file():
        raise ValueError(f'Invalid output directory: {p}')
    return str(p)


def default_decode(path):
    return str(nonempty(path).with_suffix(''))


def default_apk(path, suffix):
    p = nonempty(path)
    return str(p.with_name(p.stem + suffix + '.apk'))


def project_engine(directory):
    p = Path(require_dir(directory))
    if (p / 'apktool.yml').is_file():
        return 'Apktool'
    if (p / 'path-map.json').is_file() or (p / 'uncompressed-files.json').is_file():
        return 'APKEditor'
    raise ValueError('Unrecognized project: expected apktool.yml or APKEditor path-map.json.')


def _input(path, ext=None, check=True):
    return require_file(path, ext) if check else str(nonempty(path))


def _different(source, dest):
    if Path(source).resolve() == Path(dest).resolve():
        raise ValueError('Input and output must be different paths.')


def _number(cmd, flag, value):
    if value:
        if int(value) < 1:
            raise ValueError(f'{flag} must be positive')
        cmd += [flag, str(int(value))]


def _extra(cmd, extra):
    args = shlex.split(extra) if isinstance(extra, str) else list(extra or [])
    # Paths are controlled by the UI so pipeline stages cannot silently disagree.
    if any(a.split('=')[0] in ('-o', '--output', '-i', '--input') for a in args):
        raise ValueError('Set input and output paths in the path fields, not extra arguments.')
    return cmd + args


def decode(s, apk, dest='', *, resources=True, sources=True, force=False, framework=None,
           no_debug=False, keep_broken=False, match_original=False, only_main=False,
           api=0, jobs=0, frame_tag='', extra='', major=2, check_input=True):
    source = _input(apk, {'.apk'}, check_input)
    dest = output_dir(dest or default_decode(source))
    _different(source, dest)
    # Prevent force-decode from deleting a folder containing the input APK.
    if Path(dest).resolve() in Path(source).resolve().parents:
        raise ValueError('Decode output cannot contain the input APK.')
    cmd = s.command('apktool') + ['d', source, '-o', dest]
    for enabled, flag in ((not resources, '-r'), (not sources, '-s'), (force, '-f'),
                          (no_debug, '--no-debug-info'), (keep_broken, '--keep-broken-res'),
                          (match_original, '--match-original')):
        if enabled:
            cmd.append(flag)
    if only_main and sources and major < 3:
        cmd.append('--only-main-classes')
    if api and major >= 3:
        raise ValueError('Apktool 3 removed the API override. Set API level to Auto.')
    _number(cmd, '--api-level', api)
    _number(cmd, '-j', jobs)
    if framework:
        cmd += ['-p', require_dir(framework)]
    if frame_tag:
        cmd += ['-t', frame_tag]
    return _extra(cmd, extra)


def build(s, directory, dest, *, framework=None, force=False, copy_original=False,
          no_crunch=False, aapt='', use_aapt2=False, net_sec=False, api=0, jobs=0,
          extra='', major=2):
    source = require_dir(directory)
    destination = output(dest, '.apk')
    cmd = s.command('apktool') + ['b', source, '-o', destination]
    for enabled, flag in ((force, '-f'), (copy_original, '--copy-original'),
                          (no_crunch, '--no-crunch'), (net_sec, '--net-sec-conf')):
        if enabled:
            cmd.append(flag)
    if use_aapt2 and major < 3:
        cmd.append('--use-aapt2')
    if api and major >= 3:
        raise ValueError('Apktool 3 removed the API override. Set API level to Auto.')
    _number(cmd, '--api-level', api)
    _number(cmd, '-j', jobs)
    if aapt:
        cmd += ['--aapt' if major >= 3 else '-a', require_file(aapt)]
    if framework:
        cmd += ['-p', require_dir(framework)]
    return _extra(cmd, extra)


def editor(s, action, source, dest, *, force=False, extra='', check_input=True):
    if action not in ('d', 'b', 'm'):
        raise ValueError('Unsupported APKEditor action')
    if action == 'b':
        source = require_dir(source)
    else:
        source = _input(source, PACKAGES, check_input)
    dest = output_dir(dest) if action == 'd' else output(dest, '.apk')
    _different(source, dest)
    if action == 'd' and Path(dest).resolve() in Path(source).resolve().parents:
        raise ValueError('Decode output cannot contain the input package.')
    cmd = s.command('apkeditor') + [action, '-i', source, '-o', dest]
    if force:
        cmd.append('-f')
    return _extra(cmd, extra)


def align(s, source, dest='', *, alignment=4, check=False, verbose=False, recompress=False,
          force=True, page_size=4, check_input=True):
    source = _input(source, {'.apk'}, check_input)
    if alignment not in (1, 2, 4, 8, 16, 32, 64):
        raise ValueError('Alignment must be a power of two between 1 and 64.')
    cmd = s.command('zipalign')
    if check:
        cmd.append('-c')
    elif force:
        cmd.append('-f')
    if verbose:
        cmd.append('-v')
    if recompress and not check:
        cmd.append('-z')
    if page_size == 4:
        cmd.append('-p')  # Also supported by older Android build tools.
    elif page_size in (16, 64):
        cmd += ['-P', str(page_size)]
    elif page_size:
        raise ValueError('Page size must be 0, 4, 16 or 64 KiB.')
    cmd += [str(alignment), source]
    if not check:
        dest = output(dest, '.apk')
        _different(source, dest)
        cmd.append(dest)
    return cmd


def sign(s, source, keystore, alias, dest, *, v1=True, v2=True, v3=True, v4=None,
         key='', cert='', check_input=True, check_identity=True):
    cmd = s.command('apksigner') + ['sign']
    if keystore:
        cmd += ['--ks', require_file(keystore) if check_identity else str(nonempty(keystore))]
        if alias.strip():
            cmd += ['--ks-key-alias', alias.strip()]
    else:
        cmd += ['--key', require_file(key), '--cert', require_file(cert)]
    for version, value in enumerate((v1, v2, v3, v4), 1):
        if value is not None:
            cmd += [f'--v{version}-signing-enabled', str(value).lower()]
    return cmd + ['--out', output(dest, '.apk'), _input(source, {'.apk'}, check_input)]


def info(s, source, kind='badging'):
    if kind not in ('badging', 'permissions', 'configurations', 'xmltree'):
        raise ValueError('Unsupported AAPT dump')
    cmd = s.command('aapt') + ['dump', kind, require_file(source, {'.apk'})]
    if kind == 'xmltree':
        cmd.append('AndroidManifest.xml')
    return cmd


def parse_badging(text):
    values = {}
    package = re.search(r"^package: (.*)$", text, re.M)
    if package:
        attrs = dict(re.findall(r"(\w+)='([^']*)'", package[1]))
        values.update({'Package': attrs.get('name', ''), 'Version name': attrs.get('versionName', ''),
                       'Version code': attrs.get('versionCode', '')})
    for label, key in (('App name', 'application-label'), ('Minimum SDK', 'sdkVersion'),
                       ('Target SDK', 'targetSdkVersion'), ('Native code', 'native-code')):
        match = re.search(r'^' + re.escape(key) + r":\s*(.*)$", text, re.M)
        if match:
            values[label] = match[1].replace("'", '')
    match = re.search(r"launchable-activity: name='([^']*)'", text)
    if match:
        values['Main activity'] = match[1]
    for label, key in (('Locales', 'locales'), ('Densities', 'densities'),
                       ('Screen sizes', 'supports-screens')):
        match = re.search(r'^' + key + r':\s*(.*)$', text, re.M)
        if match:
            values[label] = match[1].replace("'", '')
    permissions = re.findall(r"^uses-permission(?:-sdk-\d+)?: name='([^']*)'", text, re.M)
    if permissions:
        values['Permissions'] = '\n  ' + '\n  '.join(permissions)
    icons = re.findall(r"application-icon-(\d+):'([^']*)'", text)
    if icons:
        values['Icon path'] = max(icons, key=lambda i: int(i[0]))[1]
    return values


def framework_install(s, source, directory='', tag=''):
    cmd = s.command('apktool') + ['if', require_file(source, {'.apk'})]
    if directory:
        cmd += ['-p', require_dir(directory)]
    if tag:
        cmd += ['-t', tag]
    return cmd


def framework_clear(s, directory, *, version=(3, 0, 1)):
    cmd = s.command('apktool')
    cmd += ['clean-frameworks', '-a'] if tuple(version) >= (3, 0, 1) else ['empty-framework-dir', '-f']
    return cmd + ['-p', require_dir(directory)]


def smali(s, source, dest, *, assemble=False, api=0, jobs=0, extra=''):
    cmd = s.command('smali' if assemble else 'baksmali')
    if assemble:
        cmd += ['assemble', require_dir(source), '-o', output(dest, '.dex')]
    else:
        cmd += ['disassemble', require_file(source, {'.dex', '.odex', '.oat', '.apk'}), '-o', output_dir(dest)]
    _number(cmd, '-a', api)
    _number(cmd, '-j', jobs)
    return _extra(cmd, extra)


def devices(s):
    return s.command('adb') + ['devices', '-l']


def parse_devices(text):
    result = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ('device', 'offline', 'unauthorized', 'recovery', 'sideload'):
            result.append((parts[0], parts[1], ' '.join(parts[2:])))
    return result


def install(s, source, serial='', *, vendor=False, abi='', replace=True, check_input=True):
    cmd = s.command('adb') + (['-s', serial.strip()] if serial.strip() else []) + ['install']
    if replace:
        cmd.append('-r')
    if vendor:
        cmd += ['-i', 'com.android.vending']
    if abi:
        if abi not in ('arm64-v8a', 'armeabi-v7a', 'x86', 'x86_64'):
            raise ValueError('Unsupported ABI')
        cmd += ['--abi', abi]
    return cmd + [_input(source, {'.apk'}, check_input)]


def verify(s, source):
    return s.command('apksigner') + ['verify', '--verbose', '--print-certs', require_file(source, {'.apk'})]


def diagnose(s):
    results = []
    for name in TOOLS:
        try:
            cmd = s.command(name)
            status = 'READY'
        except (ValueError, FileNotFoundError) as e:
            cmd, status = [], str(e)
        results.append((name, status, shlex.join(cmd)))
    return results


def desktop_entry(python, directory):
    # Desktop Exec has its own quoting rules and is not a shell command.
    def quote(value):
        value = str(value)
        if '\n' in value or '\r' in value:
            raise ValueError('Desktop entry paths cannot contain newlines.')
        for old, new in (('\\', '\\\\'), ('"', '\\"'), ('`', '\\`'), ('$', '\\$'), ('%', '%%')):
            value = value.replace(old, new)
        return '"' + value + '"'
    folder = str(directory)
    if '\n' in folder or '\r' in folder:
        raise ValueError('Desktop entry paths cannot contain newlines.')
    folder = folder.replace('\\', '\\\\')
    return ('[Desktop Entry]\nType=Application\nName=APKForge\n'
            'Comment=APK Tool GUI for Linux\n'
            f'Exec={quote(python)} -m apkforge.app %f\nPath={folder}\n'
            'Icon=application-x-executable\nTerminal=false\nCategories=Development;\n'
            'MimeType=application/vnd.android.package-archive;application/zip;\n')
