import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET

from apkforge import core, tasks


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / 'My app.v2.APK'
        self.apk.touch()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.settings = core.Settings(**{name: '/bin/echo' for name in core.TOOLS})

    def test_default_decode_is_sibling_without_extension(self):
        command = core.decode(self.settings, str(self.apk))
        self.assertEqual(command[command.index('-o') + 1], str(self.root / 'My app.v2'))

    def test_blank_paths_never_mean_working_directory(self):
        for function in (core.require_file, core.require_dir, core.output, core.output_dir):
            with self.subTest(function=function.__name__), self.assertRaises(ValueError):
                function('  ')

    def test_force_decode_cannot_delete_input_parent_or_input(self):
        for destination in (self.root, self.apk, self.root / 'project' / '..'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                core.decode(self.settings, str(self.apk), str(destination), force=True)

    def test_project_engine_detection(self):
        with self.assertRaises(ValueError):
            core.project_engine(str(self.project))
        (self.project / 'path-map.json').write_text('{}')
        self.assertEqual(core.project_engine(str(self.project)), 'APKEditor')
        (self.project / 'apktool.yml').touch()
        self.assertEqual(core.project_engine(str(self.project)), 'Apktool')

    def test_decode_advanced_flags_and_version(self):
        command = core.decode(self.settings, str(self.apk), no_debug=True, keep_broken=True,
                              match_original=True, only_main=True, api=29, jobs=3, major=2,
                              frame_tag='test tag', framework=str(self.root), extra='--no-assets')
        for flag in ('--no-debug-info', '--keep-broken-res', '--match-original', '--only-main-classes', '--no-assets'):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index('-j') + 1], '3')
        self.assertEqual(command[command.index('-t') + 1], 'test tag')
        with self.assertRaises(ValueError):
            core.decode(self.settings, str(self.apk), api=29, major=3)
        self.assertNotIn('--only-main-classes', core.decode(self.settings, str(self.apk), only_main=True, major=3))

    def test_build_advanced_flags(self):
        command = core.build(self.settings, str(self.project), str(self.root / 'built.apk'),
                             force=True, copy_original=True, no_crunch=True, aapt='/bin/echo',
                             net_sec=True, use_aapt2=True, jobs=2, major=3)
        for flag in ('-f', '--copy-original', '--no-crunch', '--aapt', '--net-sec-conf'):
            self.assertIn(flag, command)
        self.assertNotIn('--use-aapt2', command)

    def test_extra_arguments_cannot_redirect_pipeline_outputs(self):
        for extra in ('-o /tmp/out', '--output=/tmp/out', '-i /tmp/input'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                core.decode(self.settings, str(self.apk), extra=extra)

    def test_align_check_has_no_destination_and_no_mutation_flags(self):
        command = core.align(self.settings, str(self.apk), check=True, force=True, recompress=True, page_size=16)
        self.assertIn('-c', command)
        self.assertNotIn('-f', command)
        self.assertNotIn('-z', command)
        self.assertEqual(command[-1], str(self.apk))
        self.assertEqual(command[command.index('-P') + 1], '16')

    def test_align_rejects_same_path(self):
        with self.assertRaises(ValueError):
            core.align(self.settings, str(self.apk), str(self.apk))

    def test_sign_certificate_and_auto_schemes(self):
        key, cert = self.root / 'test.pk8', self.root / 'test.pem'
        key.touch()
        cert.touch()
        command = core.sign(self.settings, str(self.apk), '', '', str(self.root / 'signed.apk'),
                            key=str(key), cert=str(cert), v1=None, v2=True, v3=False, v4=True)
        self.assertNotIn('--ks-key-alias', command)
        self.assertNotIn('--v1-signing-enabled', command)
        self.assertEqual(command[command.index('--v4-signing-enabled') + 1], 'true')
        self.assertIn(str(cert), command)

    def test_framework_cleanup_version_boundary(self):
        for version, subcommand in (((2, 12, 1), 'empty-framework-dir'), ((3, 0, 0), 'empty-framework-dir'),
                                    ((3, 0, 1), 'clean-frameworks'), ((3, 0, 3), 'clean-frameworks')):
            with self.subTest(version=version):
                self.assertEqual(core.framework_clear(self.settings, str(self.root), version=version)[1], subcommand)

    def test_install_device_vendor_abi(self):
        command = core.install(self.settings, str(self.apk), 'device-123', vendor=True, abi='arm64-v8a')
        self.assertEqual(command[1:4], ['-s', 'device-123', 'install'])
        self.assertIn('com.android.vending', command)
        self.assertEqual(command[-1], str(self.apk))
        with self.assertRaises(ValueError):
            core.install(self.settings, str(self.apk), abi='shell argument')

    def test_device_statuses(self):
        text = 'List of devices attached\nABC device product:test model:Pixel\nDEF unauthorized\nGHI offline\n* daemon started successfully\n'
        self.assertEqual([d[:2] for d in core.parse_devices(text)], [('ABC', 'device'), ('DEF', 'unauthorized'), ('GHI', 'offline')])

    def test_badging(self):
        text = "package: name='org.example.app' versionCode='12' versionName='1.2'\napplication-label:'Test app'\nsdkVersion:'23'\nlaunchable-activity: name='org.example.app.Main'\napplication-icon-160:'res/a.png'\napplication-icon-480:'res/b.png'\nuses-permission: name='android.permission.INTERNET'\nlocales: 'en' 'de'\n"
        values = core.parse_badging(text)
        self.assertEqual(values['Package'], 'org.example.app')
        self.assertEqual(values['Icon path'], 'res/b.png')
        self.assertIn('INTERNET', values['Permissions'])
        self.assertEqual(values['Locales'], 'en de')

    def test_settings_roundtrip_private_and_compatible(self):
        with patch.object(core, 'CONFIG', self.root / 'settings.json'):
            self.settings.preferences = {'no_res': True, 'decode_jobs': 4}
            self.settings.save()
            loaded = core.Settings.load()
            self.assertEqual(loaded.preferences, self.settings.preferences)
            self.assertEqual(stat.S_IMODE(core.CONFIG.stat().st_mode), 0o600)
            data = json.loads(core.CONFIG.read_text())
            data['unknown_option'] = True
            data['apktool'] = 55
            core.CONFIG.write_text(json.dumps(data))
            self.assertEqual(core.Settings.load().apktool, 'apktool')

    def test_desktop_entry_keeps_path_spaces_and_file_argument(self):
        entry = core.desktop_entry('/tmp/My Python/bin/python', '/tmp/My App')
        self.assertIn('Exec="/tmp/My Python/bin/python" -m apkforge.app %f', entry)
        self.assertIn('Path=/tmp/My App', entry)
        with self.assertRaises(ValueError):
            core.desktop_entry('/tmp/bad\npath', '/tmp')

    def test_jar_command_uses_java_and_jvm_arguments_without_a_shell(self):
        jar = self.root / 'Tool name.jar'
        jar.touch()
        self.settings.java = '/bin/echo'
        self.settings.apktool = str(jar)
        self.settings.jvm_args = '-Xmx512m -Dvalue="text with spaces"'
        self.assertEqual(self.settings.command('apktool'),
                         ['/bin/echo', '-Xmx512m', '-Dvalue=text with spaces', '-jar', str(jar)])

    def test_project_fixes_back_up_and_preserve_valid_xml(self):
        values = self.project / 'res' / 'values'
        values.mkdir(parents=True)
        resources = values / 'strings.xml'
        original = '<resources><string name="keep">Hello</string><string name="APKTOOL_DUMMY_1">bad</string></resources>'
        resources.write_text(original)
        yml = self.project / 'apktool.yml'
        yml.write_text('sparseResources: true\n')
        tasks.fix_project(str(self.project))
        tree = ET.parse(resources).getroot()
        self.assertEqual([node.get('name') for node in tree], ['keep'])
        self.assertEqual(resources.with_name('strings.xml.apkforge.bak').read_text(), original)
        self.assertIn('false', yml.read_text())
        tasks.fix_project(str(self.project))
        self.assertEqual(resources.with_name('strings.xml.apkforge.bak').read_text(), original)

    def test_unsigned_preserves_original_metadata_without_duplicate_entries(self):
        original = self.project / 'original' / 'META-INF'
        original.mkdir(parents=True)
        (original / 'CERT.RSA').write_bytes(b'original certificate')
        (original / 'MANIFEST.MF').write_bytes(b'original manifest')
        with zipfile.ZipFile(self.apk, 'w') as archive:
            archive.writestr('classes.dex', b'dex')
            archive.writestr('META-INF/CERT.RSA', b'rebuilt certificate')
        dest = self.root / 'unsigned.apk'
        tasks.unsigned(str(self.project), str(self.apk), str(dest))
        with zipfile.ZipFile(dest) as archive:
            self.assertEqual(archive.read('META-INF/CERT.RSA'), b'original certificate')
            self.assertEqual(archive.read('classes.dex'), b'dex')
            self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
        with zipfile.ZipFile(self.apk) as archive:
            self.assertEqual(archive.read('META-INF/CERT.RSA'), b'rebuilt certificate')


if __name__ == '__main__':
    unittest.main()
