# -*- mode: python ; coding: utf-8 -*-
"""TheDevourer — Windows PyInstaller 打包配置"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'resources'), 'resources'),
    ],
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'docx', 'openpyxl', 'pptx', 'PyPDF2',
        'PIL', 'PIL._imaging',
        'httpx', 'openai', 'yaml', 'chardet', 'watchdog',
        'core.config', 'core.logger', 'core.db', 'core.signal_bus',
        'core.manifest_validator', 'core.module_loader',
        'core.chroma_client', 'core.feed_handler',
        'core.file_classifier', 'core.content_classifier',
        'core.storage_manager', 'core.file_watcher', 'core.kb_qa',
        'ui.pet_window', 'ui.feed_bubble', 'ui.sprite_animator',
        'ui.content_browser', 'ui.question_dialog',
        'ui.settings_dialog',
    ],
    excludes=[
        'PySide6.QtQml', 'PySide6.QtQuick',
        'PySide6.Qt3DCore', 'PySide6.QtCharts',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtBluetooth', 'PySide6.QtSensors',
        'numpy', 'scipy', 'matplotlib', 'pandas', 'tkinter',
    ],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='TheDevourer',
    debug=False, strip=True, upx=True, console=False,
    disable_windowed_traceback=False,
    target_arch='x86_64',
    icon=str(ROOT / 'resources' / 'pet_idle.png'),
)
