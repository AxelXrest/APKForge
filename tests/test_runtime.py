"""Frozen builds must launch bundled helpers rather than a system Python."""
import os
import sys
import unittest
from unittest.mock import patch
from apkforge import core, runtime


class RuntimeTests(unittest.TestCase):
    def test_source_helper_uses_python_module(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(runtime.module_command('apkforge.tasks', 'fix', '/tmp/a b'),
                             [sys.executable, '-m', 'apkforge.tasks', 'fix', '/tmp/a b'])

    def test_frozen_helper_uses_internal_dispatch(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', '/opt/apkforge/apkforge'):
            self.assertEqual(runtime.module_command('apkforge.tasks', 'delete-idsig', '/tmp/a.apk'),
                             ['/opt/apkforge/apkforge', '--internal', 'apkforge.tasks', 'delete-idsig', '/tmp/a.apk'])

    def test_appimage_new_instance_uses_persistent_image_path(self):
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'APPIMAGE': '/home/demo/App Image.AppImage'}):
            self.assertEqual(runtime.module_command('apkforge.app', persistent=True),
                             ['/home/demo/App Image.AppImage', '--internal', 'apkforge.app'])

    def test_external_tools_restore_original_library_path(self):
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {
                'LD_LIBRARY_PATH': '/bundle/_internal', 'LD_LIBRARY_PATH_ORIG': '/custom/lib',
                'QT_PLUGIN_PATH': '/bundle/plugins', 'APKFORGE_OFFLINE': '1'}, clear=True):
            result = runtime.external_environment()
            self.assertEqual(result['LD_LIBRARY_PATH'], '/custom/lib')
            self.assertNotIn('QT_PLUGIN_PATH', result)
            self.assertEqual(result['APKFORGE_OFFLINE'], '1')
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/bundle/_internal')

    def test_external_tools_clear_bundle_path_without_original(self):
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'LD_LIBRARY_PATH': '/bundle'}, clear=True):
            self.assertNotIn('LD_LIBRARY_PATH', runtime.external_environment())

    def test_native_desktop_launcher_does_not_pass_python_flags(self):
        entry = core.desktop_entry('/home/demo/My App.AppImage', '/home/demo', frozen=True)
        self.assertIn('Exec="/home/demo/My App.AppImage" %f', entry)
        self.assertNotIn('-m apkforge.app', entry)


if __name__ == '__main__':
    unittest.main()
