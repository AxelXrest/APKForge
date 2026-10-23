"""Native Linux APKToolGUI-style interface."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QLineEdit, QPushButton, QPlainTextEdit, QLabel, QCheckBox,
    QFileDialog, QMessageBox, QSplitter, QComboBox, QDialog, QDialogButtonBox,
    QGroupBox, QScrollArea, QGridLayout, QSpinBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from . import core, __version__
from .jobs import Job, Runner
from .apkinfo import ApkInfoPanel

STYLE = '''
QWidget { background: #242424; color: #ededed; font-size: 13px; }
QMainWindow, QDialog { background: #202020; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QTableWidget {
 background: #303030; border: 1px solid #515151; border-radius: 3px; padding: 5px;
 selection-background-color: #356ca2; }
QPushButton { background: #343434; border: 1px solid #585858; border-radius: 3px; padding: 6px 12px; }
QPushButton:hover { background: #454545; border-color: #888; }
QPushButton:disabled, QCheckBox:disabled { color: #858585; }
QPushButton#primary { background: #315f87; border-color: #4f85b2; }
QPushButton#primary:hover { background: #3d739f; }
QPushButton#stop { color: #ffc3bc; }
QTabWidget::pane { border: 1px solid #505050; }
QTabBar::tab { background: #2b2b2b; border: 1px solid #505050; padding: 8px 12px; }
QTabBar::tab:selected { background: #424242; border-bottom: 2px solid #76b6e7; }
QGroupBox { border: 1px solid #505050; border-radius: 3px; margin-top: 12px; padding: 12px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 4px; }
QMenu::item:selected { background: #3b6587; }
QHeaderView::section { background: #363636; padding: 6px; border: 1px solid #505050; }
QLabel#muted { color: #b6b6b6; }
QProgressBar { border: 0; background: #303030; max-height: 3px; }
QProgressBar::chunk { background: #79b5dd; }
QToolTip { background: #383838; color: white; border: 1px solid #777; }
'''
PACKAGE_FILTER = 'Android packages (*.apk *.xapk *.apks *.zip *.apkm);;All files (*)'


class PathInput(QWidget):
    def __init__(self, kind='file', filter_text='All files (*)', placeholder=''):
        super().__init__()
        self.kind, self.filter_text = kind, filter_text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setAcceptDrops(False)
        self.edit.setMinimumWidth(80)
        button = QPushButton('…')
        button.setFixedWidth(34)
        button.setToolTip('Browse')
        button.clicked.connect(self.browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)
        self.setAcceptDrops(True)
        self.edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.edit.customContextMenuRequested.connect(self.context_menu)

    def value(self):
        return self.edit.text().strip()

    def set(self, value):
        value = str(value)
        if self.edit.text() != value:
            self.edit.setText(value)

    def browse(self):
        path = Path(self.value()).expanduser() if self.value() else Path.home()
        start = str(path if path.is_dir() else path.parent)
        if self.kind == 'dir':
            result = QFileDialog.getExistingDirectory(self, 'Choose folder', start)
        elif self.kind == 'save':
            result, _ = QFileDialog.getSaveFileName(self, 'Choose output', self.value() or start, self.filter_text)
        else:
            result, _ = QFileDialog.getOpenFileName(self, 'Choose file', start, self.filter_text)
        if result:
            self.set(result)

    def context_menu(self, pos):
        menu = self.edit.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction('Open containing folder')
        action.setEnabled(bool(self.value()))
        action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.value()).expanduser().absolute().parent))))
        menu.exec(self.edit.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.set(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()


def scroll(widget):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(widget)
    return area


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle('Settings')
        self.resize(760, 590)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        tools = QWidget()
        form = QFormLayout(tools)
        self.fields = {}
        for name in core.TOOLS:
            widget = PathInput(placeholder=f'Command name, executable path or JAR for {name}')
            widget.set(settings.tool(name))
            self.fields[name] = widget
            form.addRow(name, widget)
        self.tool_install_dir = PathInput('dir', placeholder='Default: XDG data directory / apkforge / tools')
        self.tool_install_dir.set(settings.tool_install_dir)
        form.addRow('Tool installation directory', self.tool_install_dir)
        note = QLabel('Startup installs missing tools only. Use Settings → Update tools to latest stable to update existing tools. Changing this folder affects future downloads; existing files stay in place.')
        note.setWordWrap(True)
        form.addRow(note)
        tabs.addTab(scroll(tools), 'Tool paths')
        general = QWidget()
        form = QFormLayout(general)
        self.theme = QComboBox()
        self.theme.addItems(['Dark', 'Light', 'System'])
        self.theme.setCurrentText(settings.theme)
        form.addRow('Theme', self.theme)
        self.language = QComboBox()
        from .i18n import LANGUAGES
        for code, label in LANGUAGES.items():
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        form.addRow('Language (restart to apply)', self.language)
        self.jvm = QLineEdit(settings.jvm_args)
        form.addRow('Java VM arguments', self.jvm)
        self.temp = PathInput('dir', placeholder='System temporary directory')
        self.temp.set(settings.temp_dir)
        form.addRow('Temporary directory', self.temp)
        self.checks = {}
        for name, text in (('clear_log', 'Clear log before each action'), ('play_sound', 'Play a sound when done'),
                           ('open_output', 'Open output folder after successful operations')):
            check = QCheckBox(text)
            check.setChecked(getattr(settings, name))
            self.checks[name] = check
            form.addRow(check)
        note = QLabel('Options and paths are remembered. Passwords are never saved.\nTemporary files stay in an app-owned subfolder. Choose the tool installation directory in Tool paths.')
        note.setWordWrap(True)
        form.addRow(note)
        tabs.addTab(scroll(general), 'General')
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        from .i18n import translate_widgets
        translate_widgets(self, settings.language)

    def save(self):
        try:
            shlex.split(self.jvm.text())
            if self.temp.value():
                core.require_dir(self.temp.value())
            for name, widget in self.fields.items():
                setattr(self.settings, name, widget.value())
            if self.tool_install_dir.value():
                directory = Path(self.tool_install_dir.value()).expanduser().absolute()
                directory.mkdir(parents=True, exist_ok=True)
                self.settings.tool_install_dir = str(directory)
            else:
                self.settings.tool_install_dir = ''
            self.settings.jvm_args = self.jvm.text()
            self.settings.temp_dir = self.temp.value()
            self.settings.theme = self.theme.currentText()
            self.settings.language = self.language.currentData()
            for name, widget in self.checks.items():
                setattr(self.settings, name, widget.isChecked())
            self.settings.save()
        except Exception as error:
            QMessageBox.warning(self, 'Cannot save settings', str(error))
            return
        self.accept()


class Window(QMainWindow):
    def __init__(self, *, probe=True):
        super().__init__()
        self.settings = core.Settings.load()
        self.paths, self.options = {}, {}
        self.major, self.version = 3, (3, 0, 0)
        self.version_known = False
        self.last_output = ''
        self.icon_bytes = None
        self.temp = None
        self.auto_defaults = {}
        self.runner = Runner(self)
        self.runner.output.connect(self.process_output)
        self.runner.output.connect(self.signature_output)
        self.runner.step_started.connect(self.step_started)
        self.runner.completed.connect(self.finished)
        self.runner.busy_changed.connect(self.busy_changed)
        self.setWindowTitle(f'APKForge — APK Tool GUI for Linux · {__version__}')
        self.resize(1030, 820)
        self.setMinimumSize(730, 640)
        self.menus()
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(7, 5, 7, 5)
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)
        self.tabs = QTabWidget()
        splitter.addWidget(self.tabs)
        for title, create in (('Main', self.main_tab), ('APK Info', self.info_tab), ('Decode', self.decode_tab),
                              ('Build', self.build_tab), ('Sign', self.sign_tab), ('Zip align', self.align_tab),
                              ('Framework', self.framework_tab), ('Baksmali', self.smali_tab), ('ADB', self.adb_tab)):
            content = create()
            self.tabs.addTab(content if title == 'APK Info' else scroll(content), title)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(15000)
        self.log.setFont(QFont('monospace', 10))
        lower = QWidget()
        self.output_panel = lower
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 2, 0, 0)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('COMMAND OUTPUT'))
        toolbar.addStretch()
        for title, callback in (('Copy', lambda: QApplication.clipboard().setText(self.log.toPlainText())),
                                ('Save log', self.save_log), ('Clear', self.log.clear)):
            toolbar.addWidget(self.button(title, callback))
        self.cancel = self.button('Stop', self.runner.stop)
        self.cancel.setObjectName('stop')
        self.cancel.setEnabled(False)
        toolbar.addWidget(self.cancel)
        lower_layout.addLayout(toolbar)
        lower_layout.addWidget(self.log)
        splitter.addWidget(lower)
        splitter.setSizes([520, 240])
        self.tabs.currentChanged.connect(self.info_view_changed)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.statusBar().showMessage('Ready')
        self.apply_theme()
        from .i18n import translate_widgets
        translate_widgets(self, self.settings.language)
        self.connect_paths()
        self.append('APKForge ready. Drop an APK onto Main to begin. Tool paths: Settings → Tool paths.')
        self.setAcceptDrops(True)
        self.paths['source'].edit.textChanged.connect(self.schedule_info)
        if probe:
            QTimer.singleShot(0, self.update_tools)

    def button(self, text, callback, primary=False):
        button = QPushButton(text)
        if primary:
            button.setObjectName('primary')
        button.clicked.connect(lambda: self.dispatch(callback))
        return button

    def dispatch(self, callback):
        try:
            callback()
        except Exception as error:
            self.append(f'ERROR: {error}')
            QMessageBox.warning(self, 'Cannot start', str(error))

    def path(self, key, kind='file', filter_text='All files (*)', placeholder=''):
        widget = PathInput(kind, filter_text, placeholder)
        if key in self.paths:
            original = self.paths[key]
            widget.set(original.value())
            widget.edit.textChanged.connect(original.set)
            original.edit.textChanged.connect(widget.set)
        else:
            value = self.settings.preferences.get(key, '')
            widget.set(value if isinstance(value, str) else '')
            self.paths[key] = widget
        return widget

    def check(self, key, text, default=False, tooltip=''):
        widget = QCheckBox(text)
        widget.setChecked(bool(self.settings.preferences.get(key, default)))
        widget.setToolTip(tooltip)
        self.options[key] = widget
        return widget

    def number(self, key, default=0, maximum=512):
        widget = QSpinBox()
        widget.setRange(0, maximum)
        widget.setSpecialValueText('Auto')
        value = self.settings.preferences.get(key, default)
        widget.setValue(value if isinstance(value, int) else default)
        self.options[key] = widget
        return widget

    def combo(self, key, entries, default=0):
        widget = QComboBox()
        widget.addItems(entries)
        value = self.settings.preferences.get(key, default)
        widget.setCurrentIndex(value if isinstance(value, int) and 0 <= value < len(entries) else default)
        self.options[key] = widget
        return widget

    def text(self, key, placeholder=''):
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        value = self.settings.preferences.get(key, '')
        widget.setText(value if isinstance(value, str) else '')
        self.options[key] = widget
        return widget

    def value(self, key):
        widget = self.paths.get(key) or self.options[key]
        if isinstance(widget, PathInput):
            return widget.value()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text().strip()

    def form(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.addLayout(form)
        return widget, layout, form

    def actions(self, layout, title, factory):
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.button('Preview commands', lambda: self.preview(factory)))
        row.addWidget(self.button(title, lambda: self.execute(factory), True))
        layout.addLayout(row)

    def hint(self, layout, text):
        label = QLabel(text)
        label.setObjectName('muted')
        label.setWordWrap(True)
        layout.addWidget(label)

    def main_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(9)
        for label, key, kind, title, factory in (
            ('APK/XAPK/APKS/ZIP/APKM file:', 'source', 'file', 'Decompile', self.decode_jobs),
            ('Decompiled APK folder:', 'project', 'dir', 'Compile', self.build_jobs),
            ('APK file to align:', 'align_source', 'file', 'Align', self.align_jobs),
            ('APK file to sign:', 'sign_source', 'file', 'Sign', self.sign_jobs),
            ('Merge split APK into single APK:', 'merge_source', 'file', 'Merge', self.merge_jobs),
        ):
            layout.addWidget(QLabel(label))
            row = QHBoxLayout()
            row.addWidget(self.path(key, kind, PACKAGE_FILTER if key in ('source', 'merge_source') else 'APK (*.apk)'), 1)
            button = self.button(title, lambda factory=factory: self.execute(factory), True)
            button.setMinimumWidth(116)
            row.addWidget(button)
            layout.addLayout(row)
        grid = QGridLayout()
        shortcuts = (
            ('Decompile output location', lambda: self.open_location(self.value('decode_dest'), parent=True)),
            ('Decompiled APK location', lambda: self.open_location(self.value('project'))),
            ('Zipalign APK location', lambda: self.open_location(self.value('align_dest'), parent=True)),
            ('Compile output location', lambda: self.open_location(self.value('build_dest'), parent=True)),
            ('Compiled APK location', lambda: self.open_location(self.value('build_dest'), parent=True)),
            ('Sign APK location', lambda: self.open_location(self.value('sign_dest'), parent=True)),
            ('AndroidManifest.xml', lambda: self.open_project_file('AndroidManifest.xml')),
            ('Apktool.yml', lambda: self.open_project_file('apktool.yml')),
            ('Main activity smali', self.open_main_activity),
        )
        for index, (title, callback) in enumerate(shortcuts):
            grid.addWidget(self.button(title, callback), index // 3, index % 3)
        layout.addLayout(grid)
        self.hint(layout, 'Decode, build, signing and alignment options are in their matching tabs. Output folders default to beside the input file.')
        layout.addStretch()
        return widget

    def decode_tab(self):
        widget, layout, form = self.form()
        form.addRow('Input package', self.path('source', filter_text=PACKAGE_FILTER))
        form.addRow('Output folder', self.path('decode_dest', 'dir'))
        form.addRow('Decoder', self.combo('decoder', ['Apktool', 'APKEditor']))
        group = QGroupBox('Apktool options')
        grid = QGridLayout(group)
        flags = (
            ('no_src', 'Do not decode sources', False), ('no_res', 'Do not decode resources', False),
            ('decode_force', 'Overwrite existing output folder', False), ('keep_broken', 'Keep broken resources', False),
            ('match_original', 'Match original (may prevent rebuild)', False), ('only_main', 'Only disassemble main DEX classes (Apktool 2)', False),
            ('no_debug', 'Do not write debug information', False), ('fix_errors', 'Fix Apktool errors after decompile', False),
        )
        for index, (key, title, default) in enumerate(flags):
            grid.addWidget(self.check(key, title, default), index // 2, index % 2)
        layout.addWidget(group)
        extra = QFormLayout()
        extra.addRow('Framework directory (optional)', self.path('decode_framework', 'dir'))
        extra.addRow('Framework tag', self.text('decode_tag'))
        extra.addRow('API level (Apktool 2)', self.number('decode_api'))
        extra.addRow('Threads', self.number('decode_jobs', maximum=256))
        extra.addRow('Additional Apktool arguments', self.text('decode_extra', 'For example: --only-manifest'))
        extra.addRow('Additional APKEditor arguments', self.text('editor_decode_extra'))
        extra.addRow(self.check('no_parse', 'Do not parse APK info when selecting an APK'))
        layout.addLayout(extra)
        self.actions(layout, 'Decompile', self.decode_jobs)
        layout.addStretch()
        return widget

    def build_tab(self):
        widget, layout, form = self.form()
        form.addRow('Decompiled project', self.path('project', 'dir'))
        form.addRow('Output APK', self.path('build_dest', 'save', 'APK (*.apk)'))
        form.addRow('Builder', self.combo('builder', ['Auto detect', 'Apktool', 'APKEditor']))
        self.hint(layout, 'Auto detect uses apktool.yml or APKEditor path-map.json to select the correct builder.')
        group = QGroupBox('Apktool options')
        grid = QGridLayout(group)
        for index, (key, title) in enumerate((
            ('build_force', 'Build all files (skip change detection)'), ('copy_original', 'Copy original manifest and META-INF'),
            ('no_crunch', 'Disable resource crunching'), ('net_sec', 'Add network security configuration'),
            ('use_aapt2', 'Use aapt2 (older Apktool 2 only)'), ('unsigned', 'Create unsigned APK with original signature metadata'),
        )):
            grid.addWidget(self.check(key, title), index // 2, index % 2)
        layout.addWidget(group)
        extra = QFormLayout()
        extra.addRow('Custom aapt/aapt2 executable', self.path('build_aapt'))
        extra.addRow('Framework directory (optional)', self.path('build_framework', 'dir'))
        extra.addRow('API level (Apktool 2)', self.number('build_api'))
        extra.addRow('Threads', self.number('build_jobs', maximum=256))
        extra.addRow('Additional Apktool arguments', self.text('build_extra'))
        extra.addRow('Additional APKEditor arguments', self.text('editor_build_extra'))
        layout.addLayout(extra)
        chain = QHBoxLayout()
        chain.addWidget(self.check('align_after_build', 'Zipalign after build'))
        chain.addWidget(self.check('sign_after_build', 'Sign after build / zipalign'))
        chain.addStretch()
        layout.addLayout(chain)
        self.actions(layout, 'Compile', self.build_jobs)
        layout.addStretch()
        return widget

    def sign_tab(self):
        widget, layout, form = self.form()
        form.addRow('APK to sign', self.path('sign_source', filter_text='APK (*.apk)'))
        form.addRow('Signed APK', self.path('sign_dest', 'save', 'APK (*.apk)'))
        self.sign_mode = self.combo('sign_mode', ['Keystore', 'Private key + certificate', 'Default development key'], default=2)
        form.addRow('Signing identity', self.sign_mode)
        self.keystore_group = QGroupBox('Keystore')
        fields = QFormLayout(self.keystore_group)
        fields.addRow('Keystore / JKS', self.path('keystore', filter_text='Keystores (*.jks *.keystore *.p12);;All files (*)'))
        fields.addRow('Key alias (optional)', self.text('alias'))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_password = QLineEdit()
        self.key_password.setEchoMode(QLineEdit.EchoMode.Password)
        fields.addRow('Keystore password', self.password)
        fields.addRow('Key password (optional)', self.key_password)
        layout.addWidget(self.keystore_group)
        self.cert_group = QGroupBox('PKCS #8 private key and X.509 certificate')
        fields = QFormLayout(self.cert_group)
        fields.addRow('Private key', self.path('private_key', filter_text='Private keys (*.pk8 *.der);;All files (*)'))
        fields.addRow('Public certificate', self.path('certificate', filter_text='Certificates (*.pem *.cer *.crt);;All files (*)'))
        layout.addWidget(self.cert_group)
        self.sign_mode.currentIndexChanged.connect(self.sign_mode_changed)
        self.sign_mode_changed()
        schemes = QHBoxLayout()
        for number in range(1, 5):
            schemes.addWidget(QLabel(f'Scheme v{number}'))
            schemes.addWidget(self.combo(f'v{number}', ['Auto', 'Enabled', 'Disabled']))
        layout.addLayout(schemes)
        layout.addWidget(self.check('delete_idsig', 'Auto delete idsig file', True))
        layout.addWidget(self.check('overwrite_sign', 'Overwrite input file'))
        layout.addWidget(self.check('install_after_sign', 'Install APK after signing (select device in ADB tab)'))
        self.hint(layout, 'Passwords are passed through child-process environment variables and are never saved or logged.')
        self.actions(layout, 'Sign', self.sign_jobs)
        row = QHBoxLayout()
        row.addWidget(self.button('Verify signature', self.verify_selected))
        row.addWidget(self.button('Create development keystore…', self.create_keystore_dialog))
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return widget

    def sign_mode_changed(self, *args):
        self.keystore_group.setVisible(self.sign_mode.currentIndex() == 0)
        self.cert_group.setVisible(self.sign_mode.currentIndex() == 1)

    def align_tab(self):
        widget, layout, form = self.form()
        form.addRow('APK to align', self.path('align_source', filter_text='APK (*.apk)'))
        form.addRow('Aligned APK', self.path('align_dest', 'save', 'APK (*.apk)'))
        form.addRow('Alignment in bytes', self.combo('alignment', ['1', '2', '4', '8', '16', '32', '64'], 2))
        form.addRow('Native library page alignment', self.combo('page_size', ['4 KiB (legacy tools)', '16 KiB', '64 KiB', 'None']))
        for key, title, default in (('align_check', 'Check alignment only (does not modify file)', False),
                                    ('align_verbose', 'Verbose output', False), ('recompress', 'Recompress using Zopfli', False),
                                    ('align_force', 'Overwrite existing output file', False), ('sign_after_align', 'Sign after zipalign', False)):
            layout.addWidget(self.check(key, title, default))
        self.hint(layout, 'Use 16 KiB alignment with current Android Build Tools for native libraries on newer devices.')
        self.actions(layout, 'Align / Check', self.align_jobs)
        merge = QGroupBox('Merge split packages · APKEditor')
        fields = QFormLayout(merge)
        fields.addRow('Split package', self.path('merge_source', filter_text=PACKAGE_FILTER))
        fields.addRow('Merged APK', self.path('merge_dest', 'save', 'APK (*.apk)'))
        fields.addRow(self.check('merge_force', 'Overwrite existing merged APK'))
        fields.addRow('Additional arguments', self.text('merge_extra'))
        fields.addRow(self.button('Merge', lambda: self.execute(self.merge_jobs), True))
        layout.addWidget(merge)
        layout.addStretch()
        return widget

    def framework_tab(self):
        widget, layout, form = self.form()
        form.addRow('Framework APK', self.path('framework_apk', filter_text='APK (*.apk)'))
        form.addRow('Framework directory (optional)', self.path('framework_dir', 'dir', placeholder='App-managed framework directory'))
        form.addRow('Tag (optional)', self.text('framework_tag'))
        layout.addWidget(self.check('clear_framework', 'Clear framework before decompiling'))
        row = QHBoxLayout()
        row.addWidget(self.button('Install framework', lambda: self.execute(self.framework_jobs), True))
        row.addWidget(self.button('Clear framework', self.clear_framework))
        row.addWidget(self.button('Open framework folder', lambda: self.open_location(self.framework_directory())))
        layout.addLayout(row)
        self.hint(layout, 'A separate app-managed cache is used by default. Decode and build can use a custom framework folder.')
        layout.addStretch()
        return widget

    def smali_tab(self):
        widget, layout, form = self.form()
        form.addRow('DEX / ODEX / OAT / APK', self.path('dex_source', filter_text='DEX / Android files (*.dex *.odex *.oat *.apk);;All files (*)'))
        form.addRow('Smali output folder', self.path('smali_dest', 'dir'))
        form.addRow('API level', self.number('smali_api'))
        form.addRow('Threads', self.number('smali_jobs', maximum=256))
        form.addRow('Additional Baksmali arguments', self.text('baksmali_extra'))
        self.actions(layout, 'Disassemble', self.disassemble_jobs)
        group = QGroupBox('Smali → DEX')
        fields = QFormLayout(group)
        fields.addRow('Smali source folder', self.path('smali_source', 'dir'))
        fields.addRow('Output DEX', self.path('dex_dest', 'save', 'DEX (*.dex)'))
        fields.addRow('Additional Smali arguments', self.text('smali_extra'))
        fields.addRow(self.button('Assemble', lambda: self.execute(self.assemble_jobs), True))
        layout.addWidget(group)
        layout.addStretch()
        return widget

    def adb_tab(self):
        widget, layout, form = self.form()
        self.device = QComboBox()
        self.device.setEditable(True)
        self.device.setPlaceholderText('Refresh and select a device')
        form.addRow('Selected device serial', self.device)
        form.addRow('APK to install', self.path('install_source', filter_text='APK (*.apk)'))
        form.addRow(self.check('vendor', 'Set vendor to Play Store (com.android.vending)'))
        form.addRow('Override default ABI', self.combo('abi', ['Auto', 'arm64-v8a', 'armeabi-v7a', 'x86', 'x86_64']))
        form.addRow(self.check('replace', 'Replace existing application', True))
        self.device_table = QTableWidget(0, 3)
        self.device_table.setHorizontalHeaderLabels(['Serial', 'Status', 'Device details'])
        self.device_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.device_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.device_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.device_table.cellClicked.connect(self.select_device)
        layout.addWidget(self.device_table)
        row = QHBoxLayout()
        row.addWidget(self.button('Kill ADB server', lambda: self.run_jobs([Job('Stop ADB server', self.settings.command('adb') + ['kill-server'])])))
        row.addWidget(self.button('Refresh devices', self.refresh_devices))
        row.addStretch()
        row.addWidget(self.button('Install APK', lambda: self.execute(self.install_jobs), True))
        layout.addLayout(row)
        return widget

    def info_tab(self):
        widget, layout, form = self.form()
        form.addRow('APK file', self.path('info_source', filter_text='APK (*.apk)'))
        row = QHBoxLayout()
        row.addWidget(self.button('Read APK info', self.read_info, True))
        row.addWidget(self.button('Verify signature', self.verify_selected))
        row.addWidget(self.button('Save icon…', self.save_icon))
        row.addWidget(self.button('Copy details', lambda: QApplication.clipboard().setText(self.basic_info.toPlainText())))
        row.addStretch()
        self.info_focus_button = self.button('Expand details', self.toggle_info_focus)
        row.addWidget(self.info_focus_button)
        layout.addLayout(row)
        self.info_tabs = QTabWidget()
        self.basic_info = ApkInfoPanel(lambda index: self.dispatch(lambda: self.open_app_page(index)))
        self.icon = self.basic_info.icon
        self.info_tabs.addTab(scroll(self.basic_info), 'Basic info')
        self.aapt_info = QPlainTextEdit()
        self.aapt_info.setReadOnly(True)
        aapt_widget = QWidget()
        aapt_layout = QVBoxLayout(aapt_widget)
        row = QHBoxLayout()
        self.dump_kind = QComboBox()
        self.dump_kind.addItems(['badging', 'permissions', 'configurations', 'xmltree'])
        row.addWidget(self.dump_kind)
        row.addWidget(self.button('Dump', self.dump_info))
        row.addStretch()
        aapt_layout.addLayout(row)
        aapt_layout.addWidget(self.aapt_info)
        self.info_tabs.addTab(aapt_widget, 'AAPT dump')
        self.signature_info = QPlainTextEdit()
        self.signature_info.setReadOnly(True)
        self.info_tabs.addTab(self.signature_info, 'Signature')
        layout.addWidget(self.info_tabs)
        self.paths['info_source'].edit.textChanged.connect(self.clear_apk_info)
        return widget

    def info_view_changed(self, index):
        self.output_panel.setVisible(index != 1)
        self.info_focus_button.setText('Show log' if index == 1 else 'Expand details')

    def toggle_info_focus(self):
        self.output_panel.setVisible(self.output_panel.isHidden())
        self.info_focus_button.setText('Show log' if self.output_panel.isHidden() else 'Expand details')

    def menus(self):
        file_menu = self.menuBar().addMenu('File')
        self.menu_action(file_menu, 'New instance', self.new_instance, 'Ctrl+N')
        self.menu_action(file_menu, 'Save log to file', self.save_log, 'Ctrl+S')
        self.menu_action(file_menu, 'Open temp folder', lambda: self.open_location(self.temp_directory()))
        self.menu_action(file_menu, 'Clear temp folder', self.clear_temp)
        self.menu_action(file_menu, 'Install desktop / Open With entry', self.install_desktop_entry)
        file_menu.addSeparator()
        self.menu_action(file_menu, 'Exit', self.close, 'Ctrl+Q')
        settings_menu = self.menuBar().addMenu('Settings')
        self.use_editor = QAction('Use APKEditor for decompiling', self)
        self.use_editor.setCheckable(True)
        self.use_editor.setChecked(self.settings.preferences.get('decoder', 0) == 1)
        self.use_editor.toggled.connect(lambda enabled: self.options['decoder'].setCurrentIndex(int(enabled)))
        settings_menu.addAction(self.use_editor)
        self.menu_action(settings_menu, 'Open settings…', self.settings_dialog, 'Ctrl+,')
        self.menu_action(settings_menu, 'Check tool availability / versions', self.probe_tools)
        self.menu_action(settings_menu, 'Install missing tools', self.update_tools)
        self.menu_action(settings_menu, 'Update tools to latest stable', lambda: self.update_tools(upgrade=True))
        help_menu = self.menuBar().addMenu('Help')
        for title, url in (
            ('APKToolGUI reference / releases', 'https://github.com/AndnixSH/APKToolGUI/releases'),
            ('Apktool documentation / downloads', 'https://apktool.org/'),
            ('APKEditor downloads', 'https://github.com/REAndroid/APKEditor/releases'),
            ('Android Build Tools', 'https://developer.android.com/tools/releases/build-tools'),
            ('Baksmali / Smali downloads', 'https://github.com/google/smali/releases'),
            ('Apktool issue tracker', 'https://github.com/iBotPeaches/Apktool/issues'),
            ('Baksmali issue tracker', 'https://github.com/google/smali/issues'),
        ):
            self.menu_action(help_menu, title, lambda url=url: QDesktopServices.openUrl(QUrl(url)))
        help_menu.addSeparator()
        self.menu_action(help_menu, 'About', self.about)

    def menu_action(self, menu, text, callback, shortcut=''):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(lambda: self.dispatch(callback))
        menu.addAction(action)
        return action

    def connect_paths(self):
        for source, dest, convert in (
            ('source', 'decode_dest', core.default_decode),
            ('project', 'build_dest', lambda value: str(core.nonempty(value).with_name(core.nonempty(value).name + '_compiled.apk'))),
            ('align_source', 'align_dest', lambda value: core.default_apk(value, '_aligned')),
            ('sign_source', 'sign_dest', lambda value: core.default_apk(value, '_signed')),
            ('merge_source', 'merge_dest', lambda value: core.default_apk(value, '_merged')),
            ('dex_source', 'smali_dest', core.default_decode),
            ('smali_source', 'dex_dest', lambda value: str(core.nonempty(value).with_name(core.nonempty(value).name + '.dex'))),
        ):
            def update(text, source=source, dest=dest, convert=convert):
                previous = self.auto_defaults.get(dest, '')
                current = self.value(dest)
                suggested = convert(text.strip()) if text.strip() else ''
                if not current or current == previous:
                    self.paths[dest].set(suggested)
                self.auto_defaults[dest] = suggested
            # Recognize saved automatic paths, while retaining explicit custom destinations.
            current_source = self.value(source)
            self.auto_defaults[dest] = convert(current_source) if current_source else ''
            self.paths[source].edit.textChanged.connect(update)
            update(current_source)
        self.options['decoder'].currentIndexChanged.connect(lambda index: self.use_editor.setChecked(index == 1))

    def temp_directory(self):
        if self.temp is None:
            base = self.settings.temp_dir or None
            self.temp = tempfile.TemporaryDirectory(prefix='apkforge-', dir=base)
        return self.temp.name

    def framework_directory(self, override=''):
        value = override or self.value('framework_dir')
        if value:
            return core.require_dir(value)
        path = core.CONFIG.parent / 'frameworks'
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def task(self, title, action, *args):
        return Job(title, [sys.executable, '-m', 'apkforge.tasks', action, *map(str, args)])

    def decode_jobs(self):
        source = core.require_file(self.value('source'), core.PACKAGES)
        dest = self.value('decode_dest') or core.default_decode(source)
        force = self.value('decode_force')
        if Path(dest).exists() and not force:
            raise ValueError('Output folder already exists. Choose another folder or enable overwrite in Decode.')
        jobs = []
        engine = self.value('decoder')
        is_split = Path(source).suffix.lower() != '.apk'
        if is_split:
            merged = str(Path(self.temp_directory()) / 'decode-input-merged.apk')
            jobs.append(Job('Merge split package', core.editor(self.settings, 'm', source, merged, force=True)))
            source = merged
        if engine == 'Apktool':
            framework = self.framework_directory(self.value('decode_framework'))
            if self.value('clear_framework'):
                jobs.append(Job('Clear frameworks', core.framework_clear(self.settings, framework, version=self.version)))
            command = core.decode(
                self.settings, source, dest, resources=not self.value('no_res'), sources=not self.value('no_src'),
                force=force, framework=framework, no_debug=self.value('no_debug'), keep_broken=self.value('keep_broken'),
                match_original=self.value('match_original'), only_main=self.value('only_main') and self.version <= (2, 12, 1),
                api=self.value('decode_api'), jobs=self.value('decode_jobs'), frame_tag=self.value('decode_tag'),
                extra=self.value('decode_extra'), major=self.major, check_input=not is_split)
        else:
            command = core.editor(self.settings, 'd', source, dest, force=force,
                                  extra=self.value('editor_decode_extra'), check_input=not is_split)
        jobs.append(Job('Decompile with ' + engine, command))
        if self.value('fix_errors') and engine == 'Apktool':
            jobs.append(self.task('Fix decoded project (keep backups)', 'fix', dest))
        jobs[-1].done = lambda text, code: self.decoded(dest)
        return jobs

    def decoded(self, dest):
        self.paths['project'].set(dest)
        self.last_output = str(Path(dest).absolute())
        self.append('Decoded project: ' + self.last_output)

    def build_jobs(self):
        directory = core.require_dir(self.value('project'))
        dest = core.output(self.value('build_dest'), '.apk')
        engine = self.value('builder')
        if engine == 'Auto detect':
            engine = core.project_engine(directory)
        if self.value('unsigned'):
            if not (Path(directory) / 'original' / 'META-INF').is_dir():
                raise ValueError('Unsigned mode requires original/META-INF in the decoded project.')
        if engine == 'APKEditor':
            command = core.editor(self.settings, 'b', directory, dest, force=self.value('build_force'), extra=self.value('editor_build_extra'))
        else:
            command = core.build(
                self.settings, directory, dest, framework=self.framework_directory(self.value('build_framework')),
                force=self.value('build_force'), copy_original=self.value('copy_original'), no_crunch=self.value('no_crunch'),
                aapt=self.value('build_aapt'), use_aapt2=self.value('use_aapt2') and self.version < (2, 11, 1), net_sec=self.value('net_sec'),
                api=self.value('build_api'), jobs=self.value('build_jobs'), extra=self.value('build_extra'), major=self.major)
        jobs = [Job('Compile with ' + engine, command)]
        if self.value('unsigned'):
            unsigned = core.default_apk(dest, '_unsigned')
            jobs.append(self.task('Create unsigned APK with original signature metadata', 'unsigned', directory, dest, unsigned))
        final = dest
        if self.value('align_after_build'):
            aligned = core.default_apk(dest, '_aligned')
            jobs.append(Job('Zipalign compiled APK', self.align_command(dest, aligned, check_input=False)))
            final = aligned
        if self.value('sign_after_build'):
            signed = core.default_apk(final, '_signed')
            jobs += self.signing_steps(final, signed, check_input=False)
            final = signed
        jobs[-1].done = self.output_done(final)
        return jobs

    def align_command(self, source, dest, *, check_input=True, check=False):
        return core.align(self.settings, source, dest, alignment=int(self.value('alignment')),
                          page_size=(4, 16, 64, 0)[self.options['page_size'].currentIndex()],
                          verbose=self.value('align_verbose'), recompress=self.value('recompress'),
                          force=self.value('align_force'), check=check, check_input=check_input)

    def align_jobs(self):
        source = core.require_file(self.value('align_source'), {'.apk'})
        check = self.value('align_check')
        dest = self.value('align_dest')
        jobs = [Job('Check alignment' if check else 'Align APK', self.align_command(source, dest, check=check))]
        if not check:
            final = dest
            if self.value('sign_after_align'):
                final = core.default_apk(dest, '_signed')
                jobs += self.signing_steps(dest, final, check_input=False)
            jobs[-1].done = self.output_done(final)
        return jobs

    def signing_steps(self, source, dest, *, check_input=True):
        default_identity = self.sign_mode.currentIndex() == 2
        keystore = self.value('keystore') if self.sign_mode.currentIndex() == 0 else ''
        if self.sign_mode.currentIndex() == 0 and not keystore:
            raise ValueError('Choose a keystore in Sign, or switch to private key + certificate.')
        if keystore and not default_identity and not self.password.text():
            raise ValueError('Enter the keystore password in Sign. Interactive password prompts are not supported.')
        if default_identity:
            keystore = str(core.CONFIG.parent / 'signing' / 'development.jks')
        schemes = {f'v{i}': (None, True, False)[self.options[f'v{i}'].currentIndex()] for i in range(1, 5)}
        command = core.sign(self.settings, source, keystore, 'androiddebugkey' if default_identity else self.value('alias'), dest,
                            key=self.value('private_key'), cert=self.value('certificate'),
                            check_input=check_input, check_identity=not default_identity, **schemes)
        env = {}
        if keystore:
            command[-1:-1] = ['--ks-pass', 'env:APKFORGE_KS_PASS', '--key-pass', 'env:APKFORGE_KEY_PASS']
            env = {'APKFORGE_KS_PASS': 'android' if default_identity else self.password.text(),
                   'APKFORGE_KEY_PASS': 'android' if default_identity else self.key_password.text() or self.password.text()}
        jobs = []
        if default_identity:
            jobs.append(self.task('Prepare default development key', 'default-key', keystore))
        jobs.append(Job('Sign APK', command, env))
        if self.value('delete_idsig'):
            jobs.append(self.task('Remove idsig sidecar', 'delete-idsig', dest))
        if self.value('install_after_sign'):
            jobs += self.install_jobs(source=dest, check_input=False)
        return jobs

    def sign_jobs(self):
        source = core.require_file(self.value('sign_source'), {'.apk'})
        dest = source if self.value('overwrite_sign') else self.value('sign_dest')
        if not self.value('overwrite_sign'):
            core._different(source, dest)
        jobs = self.signing_steps(source, dest)
        jobs[-1].done = self.output_done(dest)
        return jobs

    def merge_jobs(self):
        dest = self.value('merge_dest')
        command = core.editor(self.settings, 'm', self.value('merge_source'), dest,
                              force=self.value('merge_force'), extra=self.value('merge_extra'))
        return [Job('Merge split APKs', command, done=self.output_done(dest))]

    def framework_jobs(self):
        return [Job('Install framework', core.framework_install(self.settings, self.value('framework_apk'),
                                                                self.framework_directory(), self.value('framework_tag')))]

    def clear_framework(self):
        if self.runner.busy:
            raise RuntimeError('Stop the active workflow before clearing frameworks.')
        directory = self.framework_directory()
        if QMessageBox.question(self, 'Clear framework', f'Clear cached framework APKs in:\n{directory}?') == QMessageBox.StandardButton.Yes:
            self.run_jobs([Job('Clear framework', core.framework_clear(self.settings, directory, version=self.version))])

    def disassemble_jobs(self):
        dest = self.value('smali_dest')
        command = core.smali(self.settings, self.value('dex_source'), dest, api=self.value('smali_api'),
                             jobs=self.value('smali_jobs'), extra=self.value('baksmali_extra'))
        return [Job('Disassemble DEX', command, done=self.output_done(dest))]

    def assemble_jobs(self):
        dest = self.value('dex_dest')
        command = core.smali(self.settings, self.value('smali_source'), dest, assemble=True,
                             api=self.value('smali_api'), jobs=self.value('smali_jobs'), extra=self.value('smali_extra'))
        return [Job('Assemble smali', command, done=self.output_done(dest))]

    def install_jobs(self, source=None, *, check_input=True):
        serial = self.device.currentText().strip()
        if not serial:
            raise ValueError('Refresh devices and select a device in ADB first.')
        abi = self.value('abi')
        return [Job('Install APK on ' + serial,
                    core.install(self.settings, source or self.value('install_source'), serial,
                                 vendor=self.value('vendor'), abi='' if abi == 'Auto' else abi,
                                 replace=self.value('replace'), check_input=check_input))]

    def output_done(self, path):
        def done(text, code):
            self.last_output = str(core.nonempty(path))
            self.append('Output: ' + self.last_output)
            if str(path).lower().endswith('.apk'):
                for name in ('align_source', 'sign_source', 'install_source', 'info_source'):
                    self.paths[name].set(path)
        return done

    def preview(self, factory):
        jobs = factory()
        text = '\n\n'.join(f'{index}. {job.title}\n$ {shlex.join(job.command)}' for index, job in enumerate(jobs, 1))
        dialog = QDialog(self)
        dialog.setWindowTitle('Command preview')
        dialog.resize(850, 450)
        layout = QVBoxLayout(dialog)
        edit = QPlainTextEdit(text)
        edit.setReadOnly(True)
        layout.addWidget(edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def execute(self, factory):
        if self.runner.busy:
            raise RuntimeError('A workflow is running. Stop it before starting another.')
        jobs = factory()  # Validate the entire chain, including credentials, before starting.
        self.last_output = ''
        self.run_jobs(jobs)

    def run_jobs(self, jobs, *, remember=True):
        if self.runner.busy:
            raise RuntimeError('A workflow is running. Stop it before starting another.')
        if remember:
            self.remember()
        if self.settings.clear_log:
            self.log.clear()
        self.runner.start(jobs)

    def remember(self):
        for name in self.paths:
            self.settings.preferences[name] = self.value(name)
        for name, widget in self.options.items():
            self.settings.preferences[name] = widget.currentIndex() if isinstance(widget, QComboBox) else self.value(name)
        try:
            self.settings.save()
        except OSError as error:
            self.append(f'Could not save preferences: {error}')

    def append(self, text):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.log.appendPlainText(f'[{stamp}] {text}')
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def process_output(self, text):
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def step_started(self, title, command):
        self.append(title + '\n$ ' + shlex.join(command))
        self.process_output('\n')
        self.statusBar().showMessage(title)

    def busy_changed(self, busy):
        self.cancel.setEnabled(busy)
        self.progress.setRange(0, 0 if busy else 1)
        self.progress.setValue(0)

    def finished(self, success, message):
        self.append(message)
        self.statusBar().showMessage(message)
        if self.settings.play_sound:
            QApplication.beep()
        if success and self.last_output and self.settings.open_output:
            self.dispatch(lambda: self.open_location(self.last_output, parent=not Path(self.last_output).is_dir()))

    def update_tools(self, *, upgrade=False):
        if self.runner.busy:
            raise RuntimeError('Wait for the active workflow to finish before installing tools.')
        self.settings.save()
        def updated(success, message):
            self.runner.completed.disconnect(updated)
            self.settings = core.Settings.load()
            QTimer.singleShot(0, self.probe_tools)
        self.runner.completed.connect(updated)
        command = [sys.executable, '-m', 'apkforge.tools'] + (['--update'] if upgrade else [])
        self.run_jobs([Job('Update tools to latest stable' if upgrade else 'Install missing tools', command)], remember=False)

    def probe_tools(self):
        if self.runner.busy:
            raise RuntimeError('Wait for the active workflow to finish before probing tools.')
        jobs = []
        for name, status, command in core.diagnose(self.settings):
            self.append(f'{name}: {status}' + (f' · {command}' if command else ''))
            if status != 'READY':
                continue
            args = {'java': ['-version'], 'apktool': ['--version'], 'apkeditor': ['-version'],
                    'adb': ['version'], 'aapt': ['version'], 'apksigner': ['version'],
                    'zipalign': ['-h'], 'keytool': ['-help'], 'baksmali': ['--version'], 'smali': ['--version']}[name]
            callback = self.apktool_version if name == 'apktool' else None
            jobs.append(Job(name + ' version / availability', self.settings.command(name) + args,
                            done=callback, allow_failure=True))
            if name == 'adb':
                jobs.append(Job('Find connected devices', core.devices(self.settings),
                                done=self.devices_received, allow_failure=True))
        if jobs:
            self.last_output = ''
            self.run_jobs(jobs, remember=False)

    def apktool_version(self, text, code):
        match = re.search(r'\b(\d+)\.(\d+)(?:\.(\d+))?', text)
        if not match or code:
            self.append('Unable to detect Apktool version; check Tool paths.')
            return
        self.version = tuple(int(part or 0) for part in match.groups())
        self.major = self.version[0]
        self.version_known = True
        for key in ('decode_api', 'build_api', 'only_main'):
            self.options[key].setEnabled(self.major < 3)
            if self.major >= 3:
                self.options[key].setToolTip('This option was removed in Apktool 3. Leave API level at Auto.')
        self.options['use_aapt2'].setEnabled(self.version < (2, 11, 1))
        self.options['only_main'].setEnabled(self.version <= (2, 12, 1))
        if self.major >= 3:
            self.options['decode_api'].setValue(0)
            self.options['build_api'].setValue(0)
        self.append('Apktool detected: ' + '.'.join(map(str, self.version)))

    def refresh_devices(self):
        self.run_jobs([Job('Refresh ADB devices', core.devices(self.settings), done=self.devices_received)])

    def devices_received(self, text, code):
        previous = self.device.currentText()
        self.device.clear()
        devices = core.parse_devices(text)
        self.device_table.setRowCount(len(devices))
        for row, (serial, status, details) in enumerate(devices):
            if status == 'device':
                self.device.addItem(serial)
            for column, value in enumerate((serial, status, details)):
                self.device_table.setItem(row, column, QTableWidgetItem(value))
        if self.device.findText(previous) >= 0:
            self.device.setCurrentText(previous)
        elif self.device.count():
            self.device.setCurrentIndex(0)
        self.append(f'{len(devices)} device(s) found')

    def select_device(self, row, column):
        if self.device_table.item(row, 1).text() == 'device':
            self.device.setCurrentText(self.device_table.item(row, 0).text())
        else:
            self.append('Device is not ready. Authorize USB debugging or reconnect it, then refresh.')

    def schedule_info(self, text):
        if not self.value('no_parse') and text.lower().endswith('.apk'):
            def read():
                if not self.runner.busy and self.value('source') == text and Path(text).expanduser().is_file():
                    self.paths['info_source'].set(text)
                    self.dispatch(self.read_info)
            QTimer.singleShot(350, read)

    def clear_apk_info(self):
        self.icon_bytes = None
        self.icon.setPixmap(QPixmap())
        self.icon.setText('No icon')
        self.basic_info.clear()
        self.aapt_info.clear()
        self.signature_info.clear()

    def read_info(self):
        if self.runner.busy:
            raise RuntimeError('Wait for the active workflow to finish before reading APK info.')
        source = self.value('info_source')
        command = core.info(self.settings, source)
        self.clear_apk_info()
        def received(text, code):
            if source != self.value('info_source'):
                return
            self.aapt_info.setPlainText(text)
            values = core.parse_badging(text)
            self.basic_info.set_info(values, source, Path(source).expanduser().stat().st_size)
            icon_path = values.get('Icon path')
            if icon_path:
                try:
                    with zipfile.ZipFile(Path(source).expanduser()) as archive:
                        if archive.getinfo(icon_path).file_size <= 10_000_000:
                            data = archive.read(icon_path)
                            pixmap = QPixmap()
                            if pixmap.loadFromData(data):
                                self.icon_bytes = data
                                self.icon.setPixmap(pixmap.scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                except (OSError, KeyError, zipfile.BadZipFile):
                    pass
        self.last_output = ''
        self.run_jobs([Job('Read APK information', command, done=received)])

    def dump_info(self):
        command = core.info(self.settings, self.value('info_source'), self.dump_kind.currentText())
        self.run_jobs([Job('AAPT dump', command, done=lambda text, code: self.aapt_info.setPlainText(text))])

    def verify_selected(self):
        source = self.value('info_source') if self.tabs.currentIndex() == 1 else self.value('sign_source')
        command = core.verify(self.settings, source)
        # Verification failures are still shown in the Signature pane.
        self.signature_info.clear()
        job = Job('Verify APK signature', command)
        self.run_jobs([job])

    def signature_output(self, text):
        if self.runner.current and self.runner.current.title == 'Verify APK signature':
            cursor = self.signature_info.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            self.signature_info.setTextCursor(cursor)

    def save_icon(self):
        if not self.icon_bytes:
            raise ValueError('Read APK info first. This APK may use an XML adaptive icon without a bitmap.')
        filename, _ = QFileDialog.getSaveFileName(self, 'Save APK icon', 'icon.png', 'PNG (*.png)')
        if filename:
            pixmap = QPixmap()
            pixmap.loadFromData(self.icon_bytes)
            if not pixmap.save(filename, 'PNG'):
                raise OSError('Could not save icon.')

    def open_app_page(self, index=0):
        from urllib.parse import quote
        package = self.basic_info.metadata.get('Package')
        if not package:
            raise ValueError('Read APK info before opening an app page.')
        package = quote(package, safe='')
        templates = (
            'https://play.google.com/store/apps/details?id={}',
            'https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s={}',
            'https://apkpure.com/search?q={}', 'https://apkcombo.com/search/{}',
            'https://apk.support/app/{}', 'https://apkgk.com/{}',
        )
        QDesktopServices.openUrl(QUrl(templates[index].format(package)))

    def open_location(self, path, *, parent=False):
        target = core.nonempty(path)
        if parent:
            target = target.parent
        if not target.exists():
            raise FileNotFoundError(f'Location does not exist: {target}')
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            raise OSError('Could not open location with the desktop application.')

    def open_project_file(self, name):
        project = self.value('project') or self.value('decode_dest')
        self.open_location(Path(core.require_dir(project)) / name)

    def open_main_activity(self):
        root = Path(core.require_dir(self.value('project') or self.value('decode_dest')))
        manifest = ET.parse(root / 'AndroidManifest.xml').getroot()
        android = '{http://schemas.android.com/apk/res/android}'
        package = manifest.get('package', '')
        activity = ''
        for node in manifest.iter():
            if node.tag not in ('activity', 'activity-alias'):
                continue
            for intent in node.findall('intent-filter'):
                main = any(item.get(android + 'name') == 'android.intent.action.MAIN' for item in intent.findall('action'))
                launcher = any(item.get(android + 'name') == 'android.intent.category.LAUNCHER' for item in intent.findall('category'))
                if main and launcher:
                    activity = node.get(android + 'targetActivity') or node.get(android + 'name', '')
                    break
            if activity:
                break
        if activity.startswith('.'):
            activity = package + activity
        elif activity and '.' not in activity:
            activity = package + '.' + activity
        if activity:
            relative = Path(*activity.split('.')).with_suffix('.smali')
            for folder in root.glob('smali*'):
                path = folder / relative
                if path.is_file():
                    self.open_location(path)
                    return
                for path in folder.rglob(relative.name):
                    if path.parts[-len(relative.parts):] == relative.parts:
                        self.open_location(path)
                        return
        raise FileNotFoundError('Main activity smali was not found. Check that sources were decoded.')

    def save_log(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Save log', 'apkforge.log', 'Log (*.log);;Text (*.txt)')
        if filename:
            Path(filename).write_text(self.log.toPlainText(), encoding='utf-8')

    def clear_temp(self):
        if self.runner.busy:
            raise RuntimeError('Stop the active workflow before clearing temporary files.')
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        self.append('Application temporary files cleared.')

    def new_instance(self):
        subprocess.Popen([sys.executable, '-m', 'apkforge.app'], start_new_session=True)

    def install_desktop_entry(self):
        from PySide6.QtCore import QStandardPaths
        directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) / 'applications'
        directory.mkdir(parents=True, exist_ok=True)
        entry = directory / 'apkforge.desktop'
        entry.write_text(core.desktop_entry(sys.executable, Path(__file__).resolve().parent.parent), encoding='utf-8')
        self.append('Installed desktop launcher and Open With entry: ' + str(entry))

    def settings_dialog(self):
        if self.runner.busy:
            raise RuntimeError('Finish or stop the active workflow before changing settings.')
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_theme()
            self.probe_tools()

    def apply_theme(self):
        QApplication.instance().setStyleSheet(STYLE if self.settings.theme == 'Dark' else '')
        if self.settings.theme == 'Light':
            from PySide6.QtGui import QPalette, QColor
            palette = QApplication.style().standardPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor('#f3f3f3'))
            palette.setColor(QPalette.ColorRole.WindowText, QColor('#202020'))
            palette.setColor(QPalette.ColorRole.Base, QColor('white'))
            palette.setColor(QPalette.ColorRole.Text, QColor('#202020'))
            palette.setColor(QPalette.ColorRole.Button, QColor('#e7e7e7'))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor('#202020'))
            QApplication.instance().setPalette(palette)
        else:
            QApplication.instance().setPalette(QApplication.style().standardPalette())

    def create_keystore_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Create development keystore')
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        dest = PathInput('save', 'Keystore (*.jks)')
        alias = QLineEdit('apkforge')
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('New keystore', dest)
        form.addRow('Alias', alias)
        form.addRow('Password (at least 6 characters)', password)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)
        def create():
            def prepare():
                filename = core.output(dest.value(), '.jks')
                if Path(filename).exists():
                    raise ValueError('Choose a new keystore file; an existing file will not be replaced.')
                if len(password.text()) < 6 or not alias.text().strip():
                    raise ValueError('Enter an alias and a password with at least 6 characters.')
                command = self.settings.command('keytool') + ['-genkeypair', '-keystore', filename,
                    '-storetype', 'JKS', '-alias', alias.text().strip(), '-keyalg', 'RSA', '-keysize', '2048',
                    '-validity', '10000', '-dname', 'CN=APKForge Development',
                    '-storepass:env', 'APKFORGE_KS_PASS', '-keypass:env', 'APKFORGE_KS_PASS', '-noprompt']
                def done(text, code):
                    self.paths['keystore'].set(filename)
                    self.options['alias'].setText(alias.text().strip())
                    self.password.setText(password.text())
                    self.sign_mode.setCurrentIndex(0)
                self.run_jobs([Job('Create development keystore', command, {'APKFORGE_KS_PASS': password.text()}, done)])
                dialog.accept()
            self.dispatch(prepare)
        buttons.accepted.connect(create)
        layout.addWidget(buttons)
        dialog.exec()

    def about(self):
        QMessageBox.about(self, 'About APKForge', f'APKForge {__version__}\nNative Linux APK Tool GUI\nMaintained by AxelXrest\n\nInspired by AndnixSH/APKToolGUI.\nUses local Apktool, APKEditor, Android Build Tools and Smali utilities.\n\nPython + Qt · No Wine required.\nSee README for feature coverage and upstream credits.')

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = Path(event.mimeData().urls()[0].toLocalFile())
        if path.is_dir():
            self.paths['project'].set(path)
        elif path.suffix.lower() in core.PACKAGES:
            self.paths['source'].set(path)
        elif path.suffix.lower() in ('.dex', '.odex', '.oat'):
            self.paths['dex_source'].set(path)
            self.tabs.setCurrentIndex(7)
        event.acceptProposedAction()

    def closeEvent(self, event):
        if self.runner.busy:
            result = QMessageBox.question(self, 'Process running', 'Stop the running workflow and close?')
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.stop()
            if self.runner.proc:
                self.runner.proc.waitForFinished(3000)
        self.remember()
        if self.temp:
            self.temp.cleanup()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('APKForge')
    app.setStyle('Fusion')
    window = Window()
    if len(sys.argv) > 1:
        path = Path(sys.argv[1]).expanduser().absolute()
        window.paths['project' if path.is_dir() else 'source'].set(path)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
