# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_all, collect_submodules


hiddenimports = (
    collect_submodules("pynput.keyboard")
    + collect_submodules("pynput.mouse")
    + collect_submodules("matplotlib.backends")
    + collect_submodules("pystray")
    + collect_submodules("PIL")
)
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all("numpy")
matplotlib_datas, matplotlib_binaries, matplotlib_hiddenimports = collect_all("matplotlib")
pillow_datas, pillow_binaries, pillow_hiddenimports = collect_all("PIL")
pystray_datas, pystray_binaries, pystray_hiddenimports = collect_all("pystray")

hiddenimports += (
    numpy_hiddenimports
    + matplotlib_hiddenimports
    + pillow_hiddenimports
    + pystray_hiddenimports
    + ["numpy._core._exceptions"]
)
binaries = numpy_binaries + matplotlib_binaries + pillow_binaries + pystray_binaries
datas = numpy_datas + matplotlib_datas + pillow_datas + pystray_datas


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="FocusForensics",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
