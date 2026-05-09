# -*- mode: python ; coding: utf-8 -*-
"""TheDevourer — Windows PyInstaller 打包配置"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 精灵图片
        (str(ROOT / 'resources' / 'pet_idle.png'), 'resources'),
        # 动画帧
        (str(ROOT / 'resources' / 'anim'), 'resources/anim'),
        # 核心模块
        (str(ROOT / 'core'), 'core'),
        # UI 模块
        (str(ROOT / 'ui'), 'ui'),
        # 插件模块（开发模式：从 modules/ 目录打包）
        (str(ROOT / 'modules'), 'modules'),
        # 存储模块
        (str(ROOT / 'storage'), 'storage'),
        (str(ROOT / 'knowledge_base'), 'knowledge_base'),
    ],
    hiddenimports=[
        # PySide6
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'PySide6.QtSvg',
        # 文档处理
        'docx', 'openpyxl', 'pptx', 'PyPDF2', 'pdfplumber',
        'PIL', 'PIL._imaging',
        # 网络
        'httpx', 'urllib3', 'certifi',
        'bs4', 'openai',
        # 数据
        'yaml', 'chardet', 'json',
        # 系统
        'watchdog',
        'chromadb', 'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的 Qt 模块（减体积 ~100MB）
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
        'PySide6.Qt3DExtras', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtTextToSpeech',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
        'PySide6.QtBluetooth', 'PySide6.QtNfc',
        'PySide6.QtSensors', 'PySide6.QtSerialPort',
        'PySide6.QtPositioning', 'PySide6.QtLocation',
        # 不需要的依赖
        'numpy', 'scipy', 'matplotlib', 'pandas',
        'torch', 'tensorflow', 'transformers',
        'notebook', 'jupyter', 'ipython',
        'tkinter', 'unittest', 'pdb',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
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
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'resources' / 'pet_idle.png'),
)
