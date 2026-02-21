# Focus Forensics

Desktop productivity behavior analyzer for Windows.

## Features

- Tracks active window title and process name
- Tracks keyboard and mouse activity
- Detects idle time
- Auto-categorizes usage (`coding`, `browsing`, `gaming`, etc.)
- Lets you edit category rules in-app
- Prompts you to classify uncategorized apps while tracking
- Stores local history in SQLite
- Includes light/dark theme toggle (saved in settings)
- Ignores Focus Forensics itself and auto-marks common Windows shell/utility windows as `system_idle`
- Rules tab supports explicit `Application + Keyword + Category` mappings
- Generates daily analytics:
  - Deep-focus time
  - Distraction spikes
  - Productivity score
- Shows weekly and monthly trend reports
- Displays dashboard charts
- Minimizes to system tray and keeps tracking in background
- Exports daily summaries as `json`, `csv`, or `txt`

## Requirements

- Windows 10/11
- Python 3.10+

## Run from source

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Start the app:

```powershell
python main.py
```

## How to use

1. Open app and click `Start Tracking`.
2. Work normally on your PC.
3. Check:
   - `Dashboard` for today metrics and category chart
   - `Trends` for 7-day and 30-day score trends
   - `Rules` to add/edit/delete categorization rules
   - `History` for recent activity samples
4. Click `Export Report` to save today summary as JSON/CSV/TXT.
5. Click `Stop Tracking` before closing (optional; app also stops on exit).

## Build Windows .exe

Use one of these options:

### Option A: From PowerShell

```powershell
.\build_exe.ps1
```

If script execution is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_exe.ps1
```

### Option B: From cmd.exe

```cmd
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

After a successful build:

- Executable path: `dist\FocusForensics.exe`

## Data location

Focus Forensics stores data locally at:

`%LOCALAPPDATA%\FocusForensics`

Files:

- `focus_forensics.db` (activity history)
- `category_rules.json` (custom categorization rules)

## Notes

- This version is designed for Windows desktop tracking.
- No cloud sync is used in this MVP.
