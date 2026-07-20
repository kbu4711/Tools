# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for training_package with Whisper data files included

a = Analysis(
    ['transcription\\build_training_package.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.venv\\Lib\\site-packages\\whisper\\assets', 'whisper/assets'),
    ],
    hiddenimports=[
        'whisper',
        'torch',
        'pptx',
        'docx',
        'PIL',
        'matplotlib',
        'numpy',
        'scipy',
    ],
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
    [],
    exclude_binaries=True,
    name='training_package',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='training_package',
)
