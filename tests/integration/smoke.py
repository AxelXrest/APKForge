"""Real-tool smoke run. No device, network, user APK or user config is needed.

APKFORGE_REFERENCE_TOOLS=/path/to/reference/Tools QT_QPA_PLATFORM=offscreen \
    .venv/bin/python tests/integration/smoke.py
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import zipfile

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from apkforge import core
from apkforge.app import Window

TOOLS = Path(os.environ['APKFORGE_REFERENCE_TOOLS'])
app = QApplication.instance() or QApplication([])


def command(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    if result.returncode:
        raise AssertionError(f'{args}\n{result.stdout}')
    return result.stdout


with tempfile.TemporaryDirectory(prefix='apkforge-integration-') as temporary:
    root = Path(temporary)
    with patch.object(core, 'CONFIG', root / 'config' / 'settings.json'):
        source = root / 'fixture'
        source.mkdir()
        resources = source / 'res'
        (resources / 'values').mkdir(parents=True)
        (resources / 'drawable').mkdir()
        (resources / 'values' / 'strings.xml').write_text('<resources><string name="app_name">APKForge Test</string></resources>')
        image = QImage(32, 32, QImage.Format.Format_ARGB32)
        image.fill(QColor('#3399cc'))
        image.save(str(resources / 'drawable' / 'icon.png'))
        manifest = source / 'AndroidManifest.xml'
        manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.apkforge.test" android:versionCode="1" android:versionName="1.0">
<uses-sdk android:minSdkVersion="21" android:targetSdkVersion="28"/>
<application android:label="@string/app_name" android:icon="@drawable/icon"><activity android:name=".MainActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>''')
        framework = root / 'framework.apk'
        with zipfile.ZipFile('/usr/share/java/android-apktool/apktool.jar') as jar:
            framework.write_bytes(jar.read('prebuilt/android-framework.jar'))
        apk = root / 'Fixture App.apk'
        command(['aapt', 'package', '-f', '-M', str(manifest), '-S', str(resources), '-I', str(framework), '-F', str(apk)])
        smali_source = root / 'smali-input'
        smali_source.mkdir()
        (smali_source / 'MainActivity.smali').write_text('''.class public Lorg/apkforge/test/MainActivity;
.super Landroid/app/Activity;
.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V
    return-void
.end method
''')
        settings = core.Settings(apkeditor=str(TOOLS / 'APKEditor.jar'), baksmali=str(TOOLS / 'baksmali.jar'), smali=str(TOOLS / 'smali.jar'))
        dex = root / 'classes.dex'
        command(core.smali(settings, str(smali_source), str(dex), assemble=True))
        with zipfile.ZipFile(apk, 'a') as archive:
            archive.write(dex, 'classes.dex')
        window = Window(probe=False)
        window.options['no_parse'].setChecked(True)
        window.settings = settings
        window.apktool_version(command(['apktool', '--version']), 0)
        log = []
        window.runner.output.connect(log.append)

        def run(jobs):
            loop = QEventLoop()
            results = []
            def done(success, message):
                results.append((success, message))
                loop.quit()
            window.runner.completed.connect(done)
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: (window.runner.stop(), loop.quit()))
            timer.start(90000)
            window.run_jobs(jobs)
            loop.exec()
            timer.stop()
            window.runner.completed.disconnect(done)
            if not results or not results[0][0]:
                raise AssertionError(str(results) + '\n' + window.log.toPlainText())
            print('PASS:', ', '.join(job.title for job in jobs), flush=True)

        window.paths['info_source'].set(apk)
        # Exercise full GUI callbacks as well as the command generation.
        def run_action(action):
            loop = QEventLoop()
            results = []
            def done(success, message):
                results.append((success, message))
                loop.quit()
            window.runner.completed.connect(done)
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: (window.runner.stop(), loop.quit()))
            timer.start(90000)
            action()
            loop.exec()
            timer.stop()
            window.runner.completed.disconnect(done)
            assert results and results[0][0], window.log.toPlainText()
        run_action(window.read_info)
        assert 'org.apkforge.test' in window.basic_info.toPlainText()
        assert window.icon_bytes, 'Bitmap icon was not extracted'
        print('PASS: APK basic info and icon extraction', flush=True)

        window.sign_mode.setCurrentIndex(1)
        window.paths['private_key'].set(TOOLS / 'testkey.pk8')
        window.paths['certificate'].set(TOOLS / 'testkey.x509.pem')
        window.paths['sign_source'].set(apk)
        run(window.sign_jobs())
        signed = window.last_output
        command(core.verify(settings, signed))
        window.paths['source'].set(signed)
        run(window.decode_jobs())
        project = window.value('project')
        assert (Path(project) / 'apktool.yml').is_file()
        assert (Path(project) / 'smali' / 'org' / 'apkforge' / 'test' / 'MainActivity.smali').is_file()
        window.options['align_after_build'].setChecked(True)
        window.options['sign_after_build'].setChecked(True)
        window.options['unsigned'].setChecked(True)
        run(window.build_jobs())
        compiled = window.last_output
        command(core.verify(settings, compiled))
        command(core.align(settings, compiled, check=True))
        assert Path(core.default_apk(window.value('build_dest'), '_unsigned')).is_file()
        print('PASS: rebuilt APK signature and alignment verified', flush=True)

        window.paths['source'].set(signed)
        window.paths['decode_dest'].set(root / 'apkeditor-project')
        window.options['decoder'].setCurrentIndex(1)
        run(window.decode_jobs())
        assert core.project_engine(window.value('project')) == 'APKEditor'
        window.options['align_after_build'].setChecked(False)
        window.options['sign_after_build'].setChecked(False)
        window.options['unsigned'].setChecked(False)
        run(window.build_jobs())
        assert zipfile.is_zipfile(window.last_output)
        print('PASS: APKEditor auto-detected and rebuilt', flush=True)

        bundle = root / 'fixture.apks'
        with zipfile.ZipFile(bundle, 'w') as archive:
            archive.write(apk, 'base.apk')
        window.paths['merge_source'].set(bundle)
        run(window.merge_jobs())
        assert zipfile.is_zipfile(window.last_output)
        window.paths['source'].set(bundle)
        window.paths['decode_dest'].set(root / 'decoded-bundle')
        window.options['decoder'].setCurrentIndex(0)
        window.options['clear_framework'].setChecked(True)
        run(window.decode_jobs())
        assert (Path(window.value('project')) / 'apktool.yml').is_file()
        window.paths['framework_apk'].set(framework)
        run(window.framework_jobs())
        print('PASS: split package merge/decode and framework clear/install', flush=True)

        window.paths['dex_source'].set(dex)
        run(window.disassemble_jobs())
        window.paths['smali_source'].set(window.value('smali_dest'))
        window.paths['dex_dest'].set(root / 'reassembled.dex')
        run(window.assemble_jobs())
        assert (root / 'reassembled.dex').read_bytes().startswith(b'dex\n')
        print('PASS: Baksmali / Smali roundtrip', flush=True)

        keystore = root / 'development.jks'
        secret = 'integration-test-password'
        keytool = settings.command('keytool') + ['-genkeypair', '-keystore', str(keystore),
            '-storetype', 'JKS', '-alias', 'apkforge', '-keyalg', 'RSA', '-keysize', '2048',
            '-validity', '10000', '-dname', 'CN=APKForge Development',
            '-storepass:env', 'APKFORGE_KS_PASS', '-keypass:env', 'APKFORGE_KS_PASS', '-noprompt']
        generated = subprocess.run(keytool, env={**os.environ, 'APKFORGE_KS_PASS': secret},
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        assert generated.returncode == 0, generated.stdout
        window.sign_mode.setCurrentIndex(0)
        window.paths['keystore'].set(keystore)
        window.options['alias'].setText('apkforge')
        window.password.setText(secret)
        window.paths['sign_source'].set(apk)
        window.paths['sign_dest'].set(root / 'keystore-signed.apk')
        run(window.sign_jobs())
        command(core.verify(settings, window.last_output))
        assert secret not in core.CONFIG.read_text()
        print('PASS: development keystore generation and password-environment signing', flush=True)
        window.close()
print('All real-tool integration checks passed.', flush=True)
