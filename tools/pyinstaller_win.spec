# -*- mode: python ; coding: utf-8 -*-
"""TheDevourer — Windows PyInstaller 打包配置（简化版）"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'resources' / 'pet_idle.png'), 'resources'),
        (str(ROOT / 'resources' / 'anim' / 'idle'), 'resources/anim/idle'),
        (str(ROOT / 'resources' / 'anim' / 'hungry'), 'resources/anim/hungry'),
        (str(ROOT / 'resources' / 'anim' / 'eating'), 'resources/anim/eating'),
        (str(ROOT / 'resources' / 'anim' / 'happy'), 'resources/anim/happy'),
        (str(ROOT / 'resources' / 'anim' / 'thinking'), 'resources/anim/thinking'),
        (str(ROOT / 'resources' / 'anim' / 'error'), 'resources/anim/error'),
    ],
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'PySide6.QtSvg',
        'docx', 'openpyxl', 'pptx', 'PyPDF2', 'pdfplumber',
        'PIL', 'PIL._imaging',
        'httpx', 'urllib3', 'certifi', 'bs4', 'openai',
        'yaml', 'chardet', 'watchdog',
        'chromadb', 'sqlite3',
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
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
        'PySide6.Qt3DExtras', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtTextToSpeech',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
        'PySide6.QtBluetooth', 'PySide6.QtNfc',
        'PySide6.QtSensors', 'PySide6.QtSerialPort',
        'PySide6.QtPositioning', 'PySide6.QtLocation',
        'numpy', 'scipy', 'matplotlib', 'pandas',
        'torch', 'tensorflow', 'transformers',
        'notebook', 'jupyter', 'ipython',
        'tkinter', 'unittest', 'pdb',
    ],
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TheDevourer',
    debug=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch='x86_64',
    icon=str(ROOT / 'resources' / 'pet_idle.png'),
)
