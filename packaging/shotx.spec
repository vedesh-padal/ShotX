# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../src/shotx/main.py'],
    pathex=[],
    binaries=[],
    datas=[('../src/shotx/assets', 'shotx/assets')],
    hiddenimports=['PySide6.plugins.imageformats.qsvg', 'PySide6.plugins.iconengines.qsvgicon'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='shotx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
