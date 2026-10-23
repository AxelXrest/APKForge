# PyInstaller spec: keep the Widgets GUI and remove unrelated QML/PDF plugins.
from pathlib import Path
root = Path(SPECPATH).parent

a = Analysis(
    [str(root / 'packaging/entry.py')], pathex=[str(root)],
    datas=[(str(root / 'apkforge/translations.json'), 'apkforge'),
           (str(root / 'apkforge/assets/apkforge.svg'), 'apkforge/assets')],
    hiddenimports=['apkforge.app', 'apkforge.tasks', 'apkforge.tools'],
    excludes=['tkinter', 'PySide6.QtQml', 'PySide6.QtQuick'],
)
# QtGui's generic hooks collect every image/input plugin, including PDF and the
# QML virtual keyboard. Neither is used here; omit their libraries as well.
unused = ('libqpdf.so', 'libqtvirtualkeyboardplugin.so', 'libQt6Pdf.so',
          'libQt6VirtualKeyboard.so', 'libQt6Qml', 'libQt6Quick')
a.binaries = [item for item in a.binaries if not any(token in item[0] for token in unused)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='apkforge', console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='apkforge')
