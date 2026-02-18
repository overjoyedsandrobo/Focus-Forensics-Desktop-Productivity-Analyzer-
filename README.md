# Focus Forensics

Desktop productivity behavior analyzer for Windows.

## What this MVP does

- Tracks active window title and process name
- Tracks keyboard and mouse activity
- Detects idle time
- Auto-categorizes usage (`coding`, `browsing`, `gaming`, etc.)
- Lets you edit category rules in-app (saved to `category_rules.json`)
- Stores local history in SQLite
- Generates daily analytics:
  - Deep-focus time
  - Distraction spikes
  - Productivity score
- Shows weekly and monthly trend reports
- Displays dashboard charts
- Exports daily summaries as `json`, `csv`, or `txt`

## Quick start

1. Install Python 3.10+
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run:

```powershell
python main.py
```

## Build Windows .exe

```powershell
.\build_exe.ps1
```

After build:

- Executable path: `dist\FocusForensics.exe`
- Data files are stored in `%LOCALAPPDATA%\FocusForensics`
  - `focus_forensics.db`
  - `category_rules.json`

## Notes

- This version is designed for Windows desktop tracking.
- Data is stored locally in `%LOCALAPPDATA%\FocusForensics`.
