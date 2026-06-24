# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Joi Desktop (Phase 10).

Build with:
    cd personal-agent
    pyinstaller desktop/joi.spec

This bundles the tray launcher + Streamlit app into a single directory.
Note: Full single-file .exe is impractical for Streamlit apps due to
dynamic imports. Directory mode is the recommended approach.
"""

import os
import shutil
import sys
from PyInstaller.utils.hooks import copy_metadata

block_cipher = None
BASE_DIR = os.path.abspath(os.path.join(SPECPATH, ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STANDALONE_DIR = os.path.join(FRONTEND_DIR, ".next", "standalone")
NODE_EXE = shutil.which("node")

if not os.path.exists(os.path.join(STANDALONE_DIR, "server.js")):
    raise SystemExit("Missing frontend/.next/standalone/server.js. Run: cd frontend && npm run build")
if not NODE_EXE:
    raise SystemExit("Node.js is required to build the packaged Joi frontend runtime.")

# Collect metadata for packages that check their own version at runtime
my_datas = []
for pkg in ['streamlit', 'tqdm', 'regex', 'requests', 'packaging', 'filelock', 'numpy', 'tokenizers', 'huggingface-hub', 'safetensors', 'accelerate', 'pytesseract']:
    try:
        my_datas += copy_metadata(pkg)
    except Exception as e:
        print(f"Start-up warning: Could not copy metadata for {pkg}: {e}")

frontend_datas = [
    (STANDALONE_DIR, "frontend"),
    (os.path.join(FRONTEND_DIR, ".next", "static"), "frontend/.next/static"),
]
if os.path.isdir(os.path.join(FRONTEND_DIR, "public")):
    frontend_datas.append((os.path.join(FRONTEND_DIR, "public"), "frontend/public"))

a = Analysis(
    [os.path.join(BASE_DIR, "desktop", "tray_app.py")],
    pathex=[BASE_DIR],
    binaries=[(NODE_EXE, ".")],
    datas=[
        # App source (Streamlit needs these at runtime)
        (os.path.join(BASE_DIR, "app"), "app"),
        (os.path.join(BASE_DIR, "services"), "services"),
        (os.path.join(BASE_DIR, "desktop"), "desktop"),
        # Static assets
        (os.path.join(BASE_DIR, "static"), "static"),
        # Config files
        (os.path.join(BASE_DIR, ".env.example"), "."),
        (os.path.join(BASE_DIR, "persona.yaml"), "."),
        (os.path.join(BASE_DIR, "system_prompt.md"), "."),
    ] + frontend_datas + my_datas,
    hiddenimports=[
        "app.api.main",
        "fastapi",
        "starlette",
        "streamlit",
        "streamlit.web.cli",
        "app.ui.components",
        "app.ui.components.neon",
        "pystray",
        "webview",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "keyboard",
        "win10toast",
        "pyttsx3",
        "speech_recognition",
        "apscheduler",
        "apscheduler.schedulers.background",
        "apscheduler.triggers.interval",
        "sqlalchemy",
        "asyncpg",
        "chromadb",
        "transformers",
        "torch",
        "numpy",
        "pandas",
        "PIL",
        "pytesseract",
        "pydantic",
        "pydantic_settings",
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "jupyter",
        "notebook",
        "IPython",
        # Exclude heavy ML libs to ensure successful build (Joi runs in Safe Mode)
        "torch",
        "transformers",
        "sentence_transformers",
        "chromadb",
        "lancedb",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Joi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — tray app only
    disable_windowed_traceback=False,
    icon=os.path.join(BASE_DIR, "static", "assets", "joi_icon.ico")
    if os.path.exists(os.path.join(BASE_DIR, "static", "assets", "joi_icon.ico"))
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Joi",
)
