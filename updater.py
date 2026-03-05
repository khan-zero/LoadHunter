import requests
import json
import webbrowser
from tkinter import messagebox
import platform
import os
import sys

# Change this to your actual current version
CURRENT_VERSION = "v1.0.0"
GITHUB_REPO = "khan-zero/LoadHunter" # Up to date repository name

def get_latest_release():
    """Fetches the latest release from a GitHub repository."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def check_for_updates(parent_window=None):
    """Checks if a newer version is available and prompts the user."""
    if not GITHUB_REPO or "your_username" in GITHUB_REPO.lower():
        if parent_window:
            messagebox.showinfo("Updater", "Please set your GitHub Repository in updater.py first (e.g., username/repo_name).", parent=parent_window)
        return False
        
    release = get_latest_release()
    
    if "error" in release:
        if parent_window:
            messagebox.showerror("Update Check Failed", f"Could not check for updates:\n{release['error']}", parent=parent_window)
        return False

    latest_version = release.get("tag_name", CURRENT_VERSION)
    
    # Simple version check (assumes semantic versioning like v1.0.0)
    if latest_version != CURRENT_VERSION and latest_version > CURRENT_VERSION:
        msg = f"A new version ({latest_version}) is available!\nYou are currently running {CURRENT_VERSION}.\n\nWould you like to download it now?"
        if messagebox.askyesno("Update Available", msg, parent=parent_window):
            # Open the release page in the browser where they can download the .exe or .deb
            release_url = release.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
            webbrowser.open(release_url)
            return True
    else:
        if parent_window:
            messagebox.showinfo("Up to Date", f"You are running the latest version ({CURRENT_VERSION}).", parent=parent_window)
            
    return False

def report_issue():
    """Opens the GitHub issues page for the user to report a bug."""
    if not GITHUB_REPO or "your_username" in GITHUB_REPO.lower():
        messagebox.showinfo("Feedback", "Please set your GitHub Repository in updater.py first to open the Issues page.")
        return
    url = f"https://github.com/{GITHUB_REPO}/issues/new"
    webbrowser.open(url)
