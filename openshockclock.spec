# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Add static and template files
added_files = [
    ('singleuser/static', 'static'),
    ('singleuser/templates', 'templates'),
]

a = Analysis(
    ['singleuser/app.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'webview',
        'PIL',
        'flask',
        'configparser',
        'requests'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['kivy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OpenShockClock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Changed to True for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='singleuser/static/favicon.ico'
)
