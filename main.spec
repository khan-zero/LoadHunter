# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter

block_cipher = None

# Find project and customtkinter paths
work_dir = os.path.abspath(os.getcwd())
ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=[work_dir],
    binaries=[],
    datas=[
        (os.path.join(ctk_path, "assets"), "customtkinter/assets"),
        ('filter_engine.py', '.'),  # Fixes ModuleNotFoundError
        ('config.py', '.'),
        ('backend.py', '.'),
    ],
    hiddenimports=[
        'filter_engine',
        'config', 
        'ui_components', 
        'backend', 
        'updater', 
        'darkdetect', 
        'telethon', 
        'PIL', 
        'PIL._imagingtk', 
        'PIL.ImageTk', 
        'PIL.Image', 
        'tkinter', 
        'tkinter.filedialog', 
        'tkinter.messagebox'
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
    # Set console=True temporarily if you need to debug startup crashes
    console=False, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
