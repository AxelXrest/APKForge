import tempfile
import unittest
from pathlib import Path
from apkforge import core

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / 'sample.apk'
        self.apk.write_bytes(b'fake apk for argument tests')
        self.project = self.root / 'decoded'
        self.project.mkdir()
        self.settings = core.Settings(apktool='/bin/echo', zipalign='/bin/echo', aapt='/bin/echo', adb='/bin/echo', apksigner='/bin/echo', apkeditor='/bin/echo')

    def test_decode(self):
        cmd=core.decode(self.settings,str(self.apk),str(self.root/'out'),sources=False,resources=False,force=True)
        self.assertEqual(cmd[1:3],['d',str(self.apk)])
        self.assertTrue(set(['-r','-s','-f']).issubset(cmd))

    def test_build(self):
        self.assertEqual(core.build(self.settings,str(self.project),str(self.root/'built.apk'))[1],'b')

    def test_editor_merge(self):
        self.assertEqual(core.editor(self.settings,'m',str(self.apk),str(self.root/'merged.apk'))[1],'m')

    def test_align(self):
        self.assertIn('4',core.align(self.settings,str(self.apk),str(self.root/'aligned.apk')))

    def test_no_shell_interpolation(self):
        tricky=self.root/'a ; $(touch injected).apk'
        tricky.write_bytes(b'x')
        cmd=core.info(self.settings,str(tricky))
        self.assertEqual(cmd[-1],str(tricky))
        self.assertFalse((self.root/'injected').exists())

    def test_bad_input(self):
        with self.assertRaises(FileNotFoundError): core.info(self.settings,str(self.root/'missing.apk'))
        with self.assertRaises(ValueError): core.build(self.settings,str(self.project),str(self.root/'invalid.zip'))

if __name__=='__main__': unittest.main()
