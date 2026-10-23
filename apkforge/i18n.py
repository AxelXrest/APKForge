"""Upstream UI translations with English fallback for new Linux controls."""
import json
from functools import lru_cache
from importlib.resources import files
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QTabWidget, QMenu

LANGUAGES = {
    'en': 'English', 'de': 'Deutsch', 'pt-BR': 'Português (Brasil)', 'hu': 'Magyar',
    'ru': 'Русский', 'zh-CN': '简体中文', 'ja': '日本語', 'tr': 'Türkçe', 'vi-VN': 'Tiếng Việt',
}


@lru_cache(maxsize=1)
def _translations():
    return json.loads(files('apkforge').joinpath('translations.json').read_text(encoding='utf-8'))


def translate_widgets(window, language):
    if language == 'en':
        return
    data = _translations()
    mapping = data.get(language, {})
    def tr(text):
        return mapping.get(text, text)
    for widget in window.findChildren(QAbstractButton):
        widget.setText(tr(widget.text()))
    for widget in window.findChildren(QLabel):
        widget.setText(tr(widget.text()))
    for widget in window.findChildren(QGroupBox):
        widget.setTitle(tr(widget.title()))
    for widget in window.findChildren(QTabWidget):
        for index in range(widget.count()):
            widget.setTabText(index, tr(widget.tabText(index)))
    for action in window.findChildren(QAction):
        action.setText(tr(action.text()))
    for menu in window.findChildren(QMenu):
        menu.setTitle(tr(menu.title()))
