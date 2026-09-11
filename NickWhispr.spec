# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
ROOT = os.path.abspath('.')

a = Analysis(
    [os.path.join(ROOT, 'src', 'whisprnick', '__main__.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'src', 'whisprnick', 'resources'), 'whisprnick/resources'),
        # faster_whisper ships the Silero VAD model as a package asset; without
        # it every transcription in the exe fails and reads as "nothing heard".
        *collect_data_files('faster_whisper'),
    ],
    hiddenimports=[
        'whisprnick',
        'whisprnick.app',
        'whisprnick.config',
        'whisprnick.core',
        'whisprnick.core.active_window',
        'whisprnick.core.audio',
        'whisprnick.core.cleanup',
        'whisprnick.core.context',
        'whisprnick.core.textutil',
        'whisprnick.core.hotkey',
        'whisprnick.core.injector',
        'whisprnick.core.pipeline',
        'whisprnick.core.transcribe',
        'whisprnick.data',
        'whisprnick.data.database',
        'whisprnick.data.models',
        'whisprnick.ui',
        'whisprnick.ui.hud',
        'whisprnick.ui.main_window',
        'whisprnick.ui.tray',
        'whisprnick.ui.pages',
        'whisprnick.ui.pages.home',
        'whisprnick.ui.pages.history',
        'whisprnick.ui.pages.insights',
        'whisprnick.ui.pages.dictionary',
        'whisprnick.ui.pages.cleanup',
        'whisprnick.ui.pages.hud_config',
        'whisprnick.ui.pages.safeguards',
        'whisprnick.ui.pages.settings',
        'whisprnick.ui.styles',
        'whisprnick.ui.styles.theme',
        'whisprnick.ui.widgets',
        'whisprnick.ui.widgets.btn',
        'whisprnick.ui.widgets.card',
        'whisprnick.ui.widgets.field_label',
        'whisprnick.ui.widgets.icons',
        'whisprnick.ui.widgets.kbd',
        'whisprnick.ui.widgets.mic_orb',
        'whisprnick.ui.widgets.pill',
        'whisprnick.ui.widgets.pipeline',
        'whisprnick.ui.widgets.section_title',
        'whisprnick.ui.widgets.stat',
        'whisprnick.ui.widgets.toggle',
        'whisprnick.ui.widgets.loading_overlay',
        'whisprnick.ui.widgets.scroll_safe',
        'sounddevice',
        'numpy',
        'faster_whisper',
        'ctranslate2',
        'httpx',
        'httpcore',
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
    name='NickWhispr',
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
    icon=os.path.join(ROOT, 'src', 'whisprnick', 'resources', 'nickwhispr.ico'),
    version_info=None,
)
