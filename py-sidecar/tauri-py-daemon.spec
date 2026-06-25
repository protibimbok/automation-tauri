# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the tauri_py Python daemon."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH)

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=playwright_binaries,
    datas=playwright_datas,
    hiddenimports=[
        *playwright_hiddenimports,
        *collect_submodules("browser"),
        *collect_submodules("modules"),
        *collect_submodules("runtime"),
        "greenlet",
        "pyee",
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
    a.binaries,
    a.datas,
    [],
    name="tauri-py-daemon",
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
