"""Entry point for the frozen GUI and its bundled subprocess helpers."""
import sys


def self_test():
    import json
    from importlib.resources import files
    from pathlib import Path
    import tempfile
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from apkforge import core
    from apkforge.app import Window
    from apkforge.jobs import Job
    from apkforge.runtime import module_command
    app = QApplication([])
    assert json.loads(files('apkforge').joinpath('translations.json').read_text())['de']
    with tempfile.TemporaryDirectory(prefix='apkforge-native-test-') as directory:
        core.CONFIG = Path(directory) / 'settings.json'
        window = Window(probe=False)
        assert window.tabs.count() == 9
        apk = str(Path(directory) / 'sample.apk')
        sidecar = Path(apk + '.idsig')
        sidecar.touch()
        jobs = [Job('Bundled helper', module_command('apkforge.tasks', 'delete-idsig', apk)),
                Job('System subprocess', ['/bin/echo', 'native subprocess OK'])]
        loop = QEventLoop()
        results = []
        window.runner.completed.connect(lambda ok, message: (results.append((ok, message)), loop.quit()))
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(15000)
        window.runner.start(jobs)
        loop.exec()
        if window.runner.busy:
            window.runner.stop()
        assert results and results[0][0], results
        assert not sidecar.exists()
        window.close()
    print('Native self-test: GUI, translations, helper and system subprocess OK')


def main():
    if sys.argv[1:] == ['--version']:
        from apkforge import __version__
        print(__version__)
    elif sys.argv[1:] == ['--self-test']:
        self_test()
    elif sys.argv[1:2] == ['--internal']:
        import runpy
        if len(sys.argv) < 3 or sys.argv[2] not in ('apkforge.tasks', 'apkforge.tools', 'apkforge.app'):
            raise SystemExit('Unknown internal helper')
        module = sys.argv[2]
        sys.argv = [module, *sys.argv[3:]]
        runpy.run_module(module, run_name='__main__')
    else:
        from apkforge.app import main as gui
        gui()


if __name__ == '__main__':
    main()
