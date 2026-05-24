# NickWhispr

**talk, it types.** A 100% local Windows dictation app. Press a hotkey, speak, and cleaned text gets pasted into whatever window you were using.

No cloud APIs. No subscriptions. No data leaves your machine.

## How it works

1. **Hotkey** (Ctrl+Shift+Space) starts recording from your mic
2. **Whisper** (faster-whisper, running locally) transcribes your speech
3. **Qwen** (via Ollama, running locally) cleans up grammar, filler words, and punctuation
4. **Paste** the cleaned text into your active window automatically

## Screenshots

<p align="center">
  <img src="docs/screenshot-home.png" alt="Home page" width="800">
</p>

## Prerequisites

- **Windows 10/11** (uses Win32 APIs for hotkeys and text injection)
- **Python 3.13+**
- **Ollama** installed and running ([download](https://ollama.com))
- ~2GB free disk space (for Whisper + Qwen models)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yeahnickk/nickwhispr.git
cd nickwhispr
pip install -e .
```

### 2. Install Ollama and pull the cleanup model

Download Ollama from [ollama.com](https://ollama.com), then:

```bash
ollama pull qwen2.5:3b
```

### 3. Run

```bash
python -m whisprnick
```

On first launch, NickWhispr will download the Whisper `small` model (~500MB) automatically. A loading screen shows progress. After that, it's cached and loads in seconds.

### 4. Use it

- Press **Ctrl+Shift+Space** to start recording
- Speak naturally
- Press **Ctrl+Shift+Space** again to stop
- Your cleaned text gets pasted into the active window

## Building the exe (optional)

```bash
pip install pyinstaller
pyinstaller NickWhispr.spec
```

The standalone exe will be in `dist/NickWhispr.exe`. Note: the exe bundles the Python runtime and is ~130MB. The Whisper model is downloaded separately on first run.

## Project structure

```
src/whisprnick/
  __main__.py          # Entry point
  app.py               # Application orchestrator
  config.py            # Constants and defaults
  core/
    audio.py           # Mic recording (sounddevice)
    transcribe.py      # Whisper transcription (faster-whisper)
    cleanup.py         # Text cleanup (Ollama/Qwen)
    pipeline.py        # Recording -> transcribe -> cleanup -> inject
    hotkey.py          # Global hotkey listener (Win32)
    active_window.py   # Active window detection
    injector.py        # Text injection via keyboard simulation
  data/
    database.py        # SQLite persistence
    models.py          # Dataclasses
  ui/
    main_window.py     # Main window with sidebar
    hud.py             # Floating HUD overlay
    tray.py            # System tray icon
    pages/             # Home, History, Insights, Dictionary, Cleanup,
                       # HUD config, Safeguards, Settings, Onboarding
    widgets/           # Reusable UI components
    styles/            # Theme (colors, fonts, stylesheet)
  resources/           # App icon
```

## Configuration

All settings are stored in a local SQLite database at `%APPDATA%/WhisprNick/whisprnick.db`. You can configure:

- **Hotkey** for start/stop dictation
- **Max recording length** (15s to 10m)
- **Silence cutoff** (auto-stop after silence, 1-15s)
- **Cleanup rules** (filler removal, grammar, punctuation, capitalization, etc.)
- **Custom dictionary** (proper nouns Whisper gets wrong)
- **Replacements** (auto-correct specific phrases)
- **Nicknames** (expand short names to full names)

## Tech stack

- **PySide6** (Qt6) for the UI
- **faster-whisper** (CTranslate2) for local speech-to-text
- **Ollama** + **Qwen 2.5 3B** for local text cleanup
- **sounddevice** + **numpy** for audio capture
- **SQLite** for local data storage
- **Win32 API** for global hotkeys and text injection

## License

MIT
