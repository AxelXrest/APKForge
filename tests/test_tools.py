import json
import io
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from apkforge import tools


class ToolTests(unittest.TestCase):
    def test_checksum_failure_does_not_replace_cached_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tool.jar'
            path.write_bytes(b'cached')
            with patch.object(tools.urllib.request, 'urlopen', return_value=io.BytesIO(b'corrupt')):
                with self.assertRaises(ValueError):
                    tools.fetch('https://example.com/tool', path, '0' * 64)
            self.assertEqual(path.read_bytes(), b'cached')

    def test_download_streams_in_bounded_chunks(self):
        payload = b'x' * (2 * 1024 * 1024 + 7)
        class Response(io.BytesIO):
            def read(self, size=-1):
                if not 0 < size <= 1024 * 1024:
                    raise AssertionError('Download must use bounded reads')
                return super().read(size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tool.jar'
            with patch.object(tools.urllib.request, 'urlopen', return_value=Response(payload)):
                tools.fetch('https://example.com/tool', path, hashlib.sha256(payload).hexdigest())
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_interrupted_download_cleans_up_and_preserves_cache(self):
        class Response(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise OSError('Connection lost')
                return super().read(size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tool.jar'
            path.write_bytes(b'cached')
            with patch.object(tools.urllib.request, 'urlopen', return_value=Response(b'partial')):
                with self.assertRaises(OSError):
                    tools.fetch('https://example.com/tool', path)
            self.assertEqual(path.read_bytes(), b'cached')
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_offline_missing_tools_never_contact_providers(self):
        from apkforge import core
        with tempfile.TemporaryDirectory() as directory:
            settings = core.Settings(**{name: '/missing/' + name for name in core.TOOLS})
            with patch.dict(tools.os.environ, {'APKFORGE_OFFLINE': '1'}), \
                    patch.object(core.Settings, 'load', return_value=settings), \
                    patch.object(core.Settings, 'save'), \
                    patch.object(tools, 'install_root', return_value=Path(directory)), \
                    patch.object(tools, 'discover', return_value=False), \
                    patch.object(tools, 'read_url', side_effect=AssertionError('Network forbidden')), \
                    patch.object(tools, 'fetch', side_effect=AssertionError('Download forbidden')):
                tools.update()
                tools.update(upgrade=True)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_download_rejects_plain_http(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                tools.fetch('http://example.com/tool', Path(directory) / 'tool.jar')

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('../escaped', 'bad')
            with self.assertRaises(ValueError):
                tools.unpack(archive, Path(directory) / 'out')
            self.assertFalse((Path(directory) / 'escaped').exists())

    def test_github_uses_latest_release_and_reuses_cached_jar(self):
        release = {'tag_name': 'v99', 'assets': [
            {'name': 'apktool_99.jar', 'browser_download_url': 'https://example.com/tool'}]}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(tools, 'read_url', return_value=json.dumps(release).encode()), \
                    patch.object(tools, 'fetch', side_effect=lambda url, dest, checksum: (dest.parent.mkdir(parents=True), dest.touch())) as fetch:
                result = tools.github(Path(directory), 'owner/Apktool', ['apktool'])
                self.assertIn('v99', result['apktool'])
                tools.github(Path(directory), 'owner/Apktool', ['apktool'])
                self.assertEqual(fetch.call_count, 1)

    def test_available_tools_skip_every_provider_and_network(self):
        from apkforge import core
        with tempfile.TemporaryDirectory() as directory:
            settings = core.Settings(**{name: '/bin/echo' for name in core.TOOLS})
            with patch.object(core.Settings, 'load', return_value=settings), \
                    patch.object(core.Settings, 'save'), \
                    patch.object(tools, 'install_root', return_value=Path(directory)), \
                    patch.object(tools, 'read_url', side_effect=AssertionError('Network must not be used')):
                tools.update()
            self.assertTrue(all(settings.tool(name) == '/bin/echo' for name in core.TOOLS))

    def test_only_missing_tool_installed_in_selected_directory(self):
        from apkforge import core
        with tempfile.TemporaryDirectory() as directory:
            settings = core.Settings(**{name: '/bin/echo' for name in core.TOOLS}, tool_install_dir=directory)
            settings.smali = '/nonexistent/smali'
            replacement = str(Path(directory) / 'smali.jar')
            with patch.object(core.Settings, 'load', return_value=settings), \
                    patch.object(core.Settings, 'save'), \
                    patch.object(tools, 'discover', side_effect=lambda s, n, r: n != 'smali'), \
                    patch.object(tools, 'github', return_value={'smali': replacement}) as github, \
                    patch.object(tools, 'android') as android, patch.object(tools, 'java') as java:
                tools.update()
                github.assert_called_once_with(Path(directory), 'baksmali/smali', ['smali'])
                android.assert_not_called()
                java.assert_not_called()
            self.assertEqual(settings.smali, replacement)
            self.assertEqual(settings.baksmali, '/bin/echo')

    def test_explicit_update_includes_available_tools(self):
        from apkforge import core
        with tempfile.TemporaryDirectory() as directory:
            settings = core.Settings(**{name: '/bin/echo' for name in core.TOOLS}, tool_install_dir=directory)
            with patch.object(core.Settings, 'load', return_value=settings), \
                    patch.object(core.Settings, 'save'), \
                    patch.object(tools, 'github', return_value={}) as github, \
                    patch.object(tools, 'java', return_value={}) as java, \
                    patch.object(tools, 'android', return_value={}) as android:
                tools.update(upgrade=True)
                self.assertEqual(github.call_count, 3)
                java.assert_called_once_with(Path(directory))
                android.assert_called_once()

    def test_detect_sdk_tools_and_local_jar(self):
        from apkforge import core
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'build-tools' / '99.0.0' / 'aapt'
            executable.parent.mkdir(parents=True)
            executable.touch()
            executable.chmod(0o755)
            jar = root / 'APKEditor-99.jar'
            jar.touch()
            settings = core.Settings(java='/bin/echo', aapt='/missing/aapt')
            with patch.dict(tools.os.environ, {'ANDROID_HOME': directory}), \
                    patch.object(tools.shutil, 'which', return_value=None), \
                    patch.object(tools.Path, 'cwd', return_value=root):
                self.assertTrue(tools.discover(settings, 'aapt', root / 'downloads'))
                self.assertEqual(settings.aapt, str(executable))
                self.assertTrue(tools.discover(settings, 'apkeditor', root / 'downloads'))
                self.assertEqual(settings.apkeditor, str(jar))

    def test_existing_jar_is_available_when_java_is_missing(self):
        from apkforge import core
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / 'apktool.jar'
            jar.touch()
            settings = core.Settings(java='/missing/java', apktool=str(jar))
            self.assertTrue(tools.available(settings, 'apktool'))
            self.assertFalse(tools.available(settings, 'java'))
