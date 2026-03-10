# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter

block_cipher = None

# Find customtkinter package path
ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(ctk_path, "assets"), "customtkinter/assets"),
    ],
    hiddenimports=[
        'config', 'filter_engine', 'ui_components', 'backend', 
        'updater', 'darkdetect', 'telethon', 'PIL', 'PIL._imagingtk', 
        'PIL.ImageTk', 'PIL.Image', 'tkinter', 'tkinter.filedialog', 'tkinter.messagebox'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    name='LoadHunter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
