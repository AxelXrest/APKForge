"""Structured, selectable APK metadata matching the APKToolGUI information view."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QGridLayout, QSizePolicy,
)


class ApkInfoPanel(QWidget):
    def __init__(self, open_page):
        super().__init__()
        self.fields = {}
        self.metadata = {}
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        identity = QGridLayout()
        identity.setVerticalSpacing(4)
        identity.setColumnStretch(1, 1)
        for row, (key, title) in enumerate((('App name', 'App name:'), ('Package', 'Package name:'),
                                             ('Main activity', 'Launch activity:'))):
            identity.addWidget(QLabel(title), row, 0)
            identity.addWidget(self.field(key, title), row, 1)
        self.icon = QLabel('No icon')
        self.icon.setFixedSize(96, 96)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setObjectName('apkIcon')
        identity.addWidget(self.icon, 0, 2, 3, 1)
        layout.addLayout(identity)

        layout.addWidget(QLabel('Links:'))
        links = QGridLayout()
        self.link_buttons = []
        for position, (title, index) in enumerate((('Play Store', 0), ('APKCombo', 3), ('APKPure', 2),
                                                   ('APK.GK', 5), ('APK.support', 4), ('APKMirror', 1))):
            button = QPushButton(title)
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False, index=index: open_page(index))
            links.addWidget(button, position // 3, position % 3)
            self.link_buttons.append(button)
        for column in range(3):
            links.setColumnStretch(column, 1)
        layout.addLayout(links)

        details = QGridLayout()
        details.setVerticalSpacing(4)
        details.setColumnStretch(1, 1)
        details.setColumnStretch(3, 1)
        pairs = (
            (('Version name', 'Version:'), ('Version code', 'Build:')),
            (('Minimum SDK', 'Min. SDK:'), ('Target SDK', 'Target SDK:')),
            (('Screen sizes', 'Screen sizes:'), ('Native code', 'Architectures:')),
            (('Densities', 'Densities:'), ('File size', 'File size:')),
        )
        for row, pair in enumerate(pairs):
            for column, (key, title) in enumerate(pair):
                details.addWidget(QLabel(title), row, column * 2)
                details.addWidget(self.field(key, title), row, column * 2 + 1)
        layout.addLayout(details)

        layout.addWidget(QLabel('Locales:'))
        self.locales = self.list_field('Locales', 'Locales', 48)
        layout.addWidget(self.locales)
        layout.addWidget(QLabel('Permissions:'))
        self.permissions = self.list_field('Permissions', 'Permissions', 100)
        layout.addWidget(self.permissions, 1)
        self.clear()

    def field(self, key, title):
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setStyleSheet('QLineEdit { padding: 3px; }')
        edit.setMinimumWidth(0)
        edit.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        edit.setAccessibleName(title.rstrip(':'))
        edit.setPlaceholderText('Not specified')
        self.fields[key] = edit
        return edit

    def list_field(self, key, title, height):
        edit = QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setMinimumHeight(height)
        if key == 'Locales':
            edit.setMaximumHeight(height)
        edit.setPlaceholderText('Not specified')
        edit.setAccessibleName(title)
        self.fields[key] = edit
        return edit

    def clear(self):
        self.metadata = {}
        for field in self.fields.values():
            field.clear()
        for button in self.link_buttons:
            button.setEnabled(False)

    def set_info(self, values, source, size):
        self.clear()
        self.metadata = dict(values, File=source, **{'File size': f'{size:,} bytes'})
        for key, field in self.fields.items():
            text = self.metadata.get(key, '')
            if key in ('Native code', 'Screen sizes', 'Densities', 'Locales'):
                text = ', '.join(text.split())
            if key == 'Permissions':
                text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
            if isinstance(field, QLineEdit):
                field.setText(text)
                field.setCursorPosition(0)
                field.setToolTip(text)
            else:
                field.setPlainText(text)
        for button in self.link_buttons:
            button.setEnabled(bool(values.get('Package')))

    def toPlainText(self):
        """Copy/export all fields without relying on the current AAPT dump mode."""
        return '\n'.join(f'{key}: {value}' for key, value in self.metadata.items() if value and key != 'Icon path')
