# 🚚 LoadHunter Installation Guide

LoadHunter is a modular logistics filter designed for the Uzbekistan market. This guide covers how to install and run the application on Windows and Linux.

---

## 🪟 Windows Installation

### Option 1: Using the Installer (Recommended)
1. Download the `LoadHunter-Setup.exe` from the latest release.
2. Run the installer and follow the on-screen instructions.
3. A shortcut will be created on your Desktop and in the Start Menu.

### Option 2: Build from Source
If you want to build the executable yourself:
1. Install [Python 3.10+](https://www.python.org/).
2. Open PowerShell or CMD in the project folder.
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Build the executable using PyInstaller:
   ```powershell
   pyinstaller main.spec --noconfirm
   ```
5. The standalone `.exe` will be in the `dist/` folder.
6. (Optional) Use [Inno Setup](https://jrsoftware.org/isinfo.php) with `installer.iss` to create a setup wizard.

---

## 🐧 Linux Installation

### Option 1: Standalone Binary
1. Download the `LoadHunter` binary for Linux.
2. Give it execution permissions:
   ```bash
   chmod +x LoadHunter
   ```
3. Run it:
   ```bash
   ./LoadHunter
   ```

### Option 2: Build from Source
1. Ensure you have Python 3.10+ and `pip` installed.
2. Run the provided build script:
   ```bash
   chmod +x build_linux.sh
   ./build_linux.sh
   ```
3. This will create a standalone binary in `dist/` and optionally create a Desktop shortcut (`.desktop` file).

---

## 🛠 Running from Source (Development)
For both Windows and Linux, if you just want to run the app without building:
1. Clone the repository.
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   python main.py
   ```

---

## 🔑 Telegram API Setup
Upon first launch, you will need to provide your Telegram API credentials:
1. Go to [my.telegram.org](https://my.telegram.org/auth?to=apps).
2. Log in and create a new "App" (any name works).
3. Copy the **API ID** and **API Hash** and paste them into LoadHunter.
4. Log in with your phone number.

---

## 📁 Data Locations
LoadHunter saves your settings and session files in OS-specific folders to keep your data safe:
- **Windows:** `%APPDATA%\LoadHunter`
- **Linux:** `~/.local/share/LoadHunter`
- **macOS:** `~/Library/Application Support/LoadHunter`
