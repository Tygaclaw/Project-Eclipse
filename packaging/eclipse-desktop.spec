# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
source_root = project_root / "src"

a = Analysis(
    [str(project_root / "packaging" / "launcher.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "eclipse",
        "eclipse.__main__",
        "eclipse.model_intelligence",
        "eclipse.model_intelligence.ggml_types",
        "eclipse.model_intelligence.gguf",
        "eclipse.model_intelligence.hf_folder",
        "eclipse.model_intelligence.model_atlas",
        "eclipse.model_intelligence.safetensors",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ECLIPSE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    upx=False,
    upx_exclude=[],
    name="ECLIPSE",
)