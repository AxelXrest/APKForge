"""Offscreen checks of GUI state and the real asynchronous process runner."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from apkforge.app import Window
    from apkforge.jobs import Runner, Job
except ImportError:
    QApplication = None

from apkforge import core


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = patch.object(core, 'CONFIG', self.root / 'config' / 'settings.json')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.window = Window(probe=False)
        self.window.options['no_parse'].setChecked(True)
        self.addCleanup(self.window.close)
        self.window.settings = core.Settings(**{name: '/bin/echo' for name in core.TOOLS})
        self.apk = self.root / 'Test App.v2.apk'
        self.apk.touch()

    def test_reference_tabs_and_mirrored_paths(self):
        self.assertEqual([self.window.tabs.tabText(i) for i in range(9)],
                         ['Main', 'APK Info', 'Decode', 'Build', 'Sign', 'Zip align', 'Framework', 'Baksmali', 'ADB'])
        self.window.paths['source'].set(self.apk)
        self.assertEqual(self.window.value('decode_dest'), str(self.root / 'Test App.v2'))
        self.window.paths['source'].set(self.root / 'Other.apk')
        self.assertEqual(self.window.value('decode_dest'), str(self.root / 'Other'))
        self.window.paths['decode_dest'].set(self.root / 'custom')
        self.window.paths['source'].set(self.root / 'Third.apk')
        self.assertEqual(self.window.value('decode_dest'), str(self.root / 'custom'))

    def test_decode_then_project_path_updates_only_on_success(self):
        self.window.paths['source'].set(self.apk)
        jobs = self.window.decode_jobs()
        self.assertEqual(self.window.value('project'), '')
        jobs[-1].done('', 0)
        self.assertEqual(self.window.value('project'), str(self.root / 'Test App.v2'))
        self.assertEqual(self.window.value('build_dest'), str(self.root / 'Test App.v2_compiled.apk'))

    def test_split_package_prepares_merge_before_decode(self):
        source = self.root / 'app.apks'
        source.touch()
        self.window.paths['source'].set(source)
        jobs = self.window.decode_jobs()
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].command[1], 'm')
        self.assertEqual(jobs[1].command[1], 'd')
        merged = jobs[0].command[jobs[0].command.index('-o') + 1]
        self.assertIn(merged, jobs[1].command)

    def test_build_align_sign_install_order_and_secret_handling(self):
        project = self.root / 'project'
        project.mkdir()
        (project / 'apktool.yml').touch()
        key = self.root / 'key.jks'
        key.touch()
        self.window.paths['project'].set(project)
        self.window.sign_mode.setCurrentIndex(0)
        self.window.paths['keystore'].set(key)
        self.window.password.setText('SECRET password')
        self.window.key_password.setText('SECRET key password')
        self.window.options['align_after_build'].setChecked(True)
        self.window.options['sign_after_build'].setChecked(True)
        self.window.options['install_after_sign'].setChecked(True)
        self.window.device.setCurrentText('serial-123')
        jobs = self.window.build_jobs()
        self.assertEqual([job.title for job in jobs], ['Compile with Apktool', 'Zipalign compiled APK',
                         'Sign APK', 'Remove idsig sidecar', 'Install APK on serial-123'])
        sign = jobs[2]
        self.assertNotIn('SECRET password', sign.command)
        self.assertNotIn('SECRET key password', sign.command)
        self.assertEqual(sign.env['APKFORGE_KS_PASS'], 'SECRET password')
        self.assertEqual(sign.env['APKFORGE_KEY_PASS'], 'SECRET key password')
        signed = sign.command[sign.command.index('--out') + 1]
        self.assertEqual(jobs[-1].command[-1], signed)
        self.window.remember()
        saved = core.CONFIG.read_text()
        self.assertNotIn('SECRET', saved)

    def test_tool_installation_directory_is_saved(self):
        from apkforge.app import SettingsDialog
        directory = self.root / 'chosen' / 'tools'
        dialog = SettingsDialog(self.window.settings, self.window)
        self.addCleanup(dialog.close)
        dialog.tool_install_dir.set(directory)
        dialog.save()
        self.assertTrue(directory.is_dir())
        self.assertEqual(core.Settings.load().tool_install_dir, str(directory))

    def test_default_signing_requires_no_credentials(self):
        self.assertEqual(self.window.sign_mode.currentIndex(), 2)
        self.window.paths['sign_source'].set(self.apk)
        jobs = self.window.sign_jobs()
        self.assertEqual(jobs[0].title, 'Prepare default development key')
        self.assertEqual(jobs[1].title, 'Sign APK')
        self.assertEqual(jobs[1].env['APKFORGE_KS_PASS'], 'android')
        self.assertIn('androiddebugkey', jobs[1].command)

    def test_missing_signing_credentials_prevent_build_start(self):
        self.window.sign_mode.setCurrentIndex(0)
        project = self.root / 'project'
        project.mkdir()
        (project / 'apktool.yml').touch()
        self.window.paths['project'].set(project)
        self.window.options['sign_after_build'].setChecked(True)
        with self.assertRaises(ValueError):
            self.window.build_jobs()
        self.assertFalse(self.window.runner.busy)

    def test_apkeditor_build_auto_detection(self):
        project = self.root / 'editor-project'
        project.mkdir()
        (project / 'path-map.json').write_text('{}')
        self.window.paths['project'].set(project)
        self.assertEqual(self.window.build_jobs()[0].title, 'Compile with APKEditor')

    def test_version_detection_resets_removed_api_options(self):
        self.window.options['decode_api'].setValue(29)
        self.window.options['build_api'].setValue(29)
        self.window.apktool_version('3.0.3', 0)
        self.assertEqual(self.window.version, (3, 0, 3))
        self.assertEqual(self.window.value('decode_api'), 0)
        self.assertFalse(self.window.options['decode_api'].isEnabled())
        self.assertFalse(self.window.options['only_main'].isEnabled())
        self.window.apktool_version('2.9.3', 0)
        self.assertTrue(self.window.options['decode_api'].isEnabled())

    def test_device_refresh_filters_unavailable_devices(self):
        self.window.devices_received('List of devices attached\nA unauthorized\nB device model:Pixel\nC offline\n', 0)
        self.assertEqual(self.window.device.count(), 1)
        self.assertEqual(self.window.device.currentText(), 'B')
        self.assertEqual(self.window.device_table.rowCount(), 3)

    def test_sign_overwrite_requires_explicit_checkbox(self):
        self.window.paths['sign_source'].set(self.apk)
        self.window.paths['sign_dest'].set(self.apk)
        with self.assertRaisesRegex(ValueError, 'different paths'):
            self.window.sign_jobs()

    def test_main_activity_opens_from_apkeditor_nested_smali(self):
        root = self.root / 'project'
        source = root / 'smali' / 'classes' / 'org' / 'example'
        source.mkdir(parents=True)
        activity = source / 'Main.smali'
        activity.touch()
        (root / 'AndroidManifest.xml').write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.example"><application><activity-alias android:name=".Alias" android:targetActivity=".Main"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity-alias></application></manifest>''')
        self.window.paths['project'].set(root)
        with patch.object(self.window, 'open_location') as opened:
            self.window.open_main_activity()
        opened.assert_called_once_with(activity)

    def test_upstream_translation_and_english_fallback(self):
        from apkforge.i18n import translate_widgets
        translate_widgets(self.window, 'de')
        self.assertEqual(self.window.tabs.tabText(0), 'Hauptseite')
        self.assertEqual(self.window.value('decoder'), 'Apktool')
        self.assertEqual(self.window.value('builder'), 'Auto detect')

    def test_invalid_signature_output_remains_visible(self):
        self.window.runner.current = Job('Verify APK signature', [])
        self.window.signature_output('DOES NOT VERIFY\n')
        self.assertIn('DOES NOT VERIFY', self.window.signature_info.toPlainText())
        self.window.runner.current = None

    def test_structured_apk_info_formats_lists_and_keeps_fields_selectable(self):
        panel = self.window.basic_info
        panel.set_info({'App name': 'Example App', 'Package': 'org.example.app',
                        'Version name': '1.2', 'Version code': '123', 'Minimum SDK': '23',
                        'Native code': 'arm64-v8a x86_64', 'Locales': 'en de fr',
                        'Permissions': '\n  android.permission.INTERNET\n  android.permission.CAMERA'},
                       str(self.apk), 12345)
        self.assertEqual(panel.fields['Package'].text(), 'org.example.app')
        self.assertTrue(panel.fields['Package'].isReadOnly())
        self.assertEqual(panel.fields['Native code'].text(), 'arm64-v8a, x86_64')
        self.assertEqual(panel.locales.toPlainText(), 'en, de, fr')
        self.assertEqual(panel.permissions.toPlainText(), 'android.permission.INTERNET\nandroid.permission.CAMERA')
        self.assertEqual(panel.fields['File size'].text(), '12,345 bytes')
        self.assertTrue(all(button.isEnabled() for button in panel.link_buttons))

    def test_changing_apk_clears_old_details_and_disables_store_links(self):
        self.window.basic_info.set_info({'Package': 'org.previous'}, '/tmp/previous.apk', 100)
        self.window.icon_bytes = b'previous icon'
        self.window.paths['info_source'].set(self.apk)
        self.assertEqual(self.window.basic_info.fields['Package'].text(), '')
        self.assertIsNone(self.window.icon_bytes)
        self.assertFalse(any(button.isEnabled() for button in self.window.basic_info.link_buttons))

    def test_store_links_use_metadata_after_switching_aapt_dump_mode(self):
        self.window.basic_info.set_info({'Package': 'org.example.app'}, str(self.apk), 100)
        self.window.aapt_info.setPlainText('uses-permission: android.permission.INTERNET')
        with patch('apkforge.app.QDesktopServices.openUrl') as opened:
            self.window.basic_info.link_buttons[0].click()
        self.assertEqual(opened.call_args.args[0].toString(),
                         'https://play.google.com/store/apps/details?id=org.example.app')


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def run_jobs(self, jobs, stop_after=None):
        runner = Runner()
        loop = QEventLoop()
        result, output, titles = [], [], []
        runner.completed.connect(lambda success, message: (result.append((success, message)), loop.quit()))
        runner.output.connect(output.append)
        runner.step_started.connect(lambda title, command: titles.append(title))
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: (runner.stop(), loop.quit()))
        timer.start(8000)
        runner.start(jobs)
        if stop_after:
            QTimer.singleShot(stop_after, runner.stop)
        loop.exec()
        timer.stop()
        if runner.busy and runner.proc:
            runner.stop()
            runner.proc.waitForFinished(2000)
        self.assertTrue(result, 'Process runner failed to complete')
        return result[0], ''.join(output), titles

    def test_successful_workflow_runs_in_order(self):
        result, output, titles = self.run_jobs([
            Job('one', [sys.executable, '-c', 'print("first")']),
            Job('two', [sys.executable, '-c', 'print("second")']),
        ])
        self.assertTrue(result[0])
        self.assertEqual(titles, ['one', 'two'])
        self.assertIn('first', output)
        self.assertIn('second', output)

    def test_failed_step_skips_rest(self):
        result, output, titles = self.run_jobs([
            Job('fail', [sys.executable, '-c', 'import sys; print("failure"); sys.exit(7)']),
            Job('must not run', [sys.executable, '-c', 'print("bad")']),
        ])
        self.assertFalse(result[0])
        self.assertEqual(titles, ['fail'])
        self.assertIn('exit 7', result[1])

    def test_failed_start_releases_runner(self):
        result, output, titles = self.run_jobs([Job('missing', ['/no/such/executable'])])
        self.assertFalse(result[0])

    def test_cancel_skips_following_steps(self):
        result, output, titles = self.run_jobs([
            Job('wait', [sys.executable, '-c', 'import time; time.sleep(30)']),
            Job('must not run', [sys.executable, '-c', 'print("bad")']),
        ], stop_after=50)
        self.assertEqual(result, (False, 'Stopped'))
        self.assertEqual(titles, ['wait'])

    def test_missing_optional_probe_continues(self):
        result, output, titles = self.run_jobs([
            Job('optional', ['/no/such/executable'], allow_failure=True),
            Job('next', [sys.executable, '-c', 'print("OK")']),
        ])
        self.assertTrue(result[0])
        self.assertEqual(titles, ['optional', 'next'])


if __name__ == '__main__':
    unittest.main()
