# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ctb_gui.exe — single-file Windows GUI."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    [r'src\\ctb_csv\\__main__.py'],
    pathex=[r'src'],
    binaries=[],
    datas=collect_data_files('ezdxf'),       # ezdxf ships font/resource data
    hiddenimports=[
        # our own package
        'ctb_csv',
        'ctb_csv.gui',
        'ctb_csv.cli',
        'ctb_csv.ctb_parser',
        'ctb_csv.csv_handler',
        'ctb_csv.validator',
        'ctb_csv.reporter',
        'ctb_csv.llm_grouper',
        # tkinter (sometimes missed on Windows)
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'tkinter.ttk',
        # ezdxf internals
        'ezdxf.colors',
        # anthropic + pydantic (AI feature — gracefully absent if missing)
        'anthropic',
        'pydantic',
        'pydantic.v1',
        'httpx',
        'httpcore',
        'anyio',
        'sniffio',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['weasyprint'],   # optional PDF dep — keep exe smaller
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ctb_gui',
    debug=False,
    strip=False,
    upx=False,
    console=False,          # no black console window
    icon=None,
)
