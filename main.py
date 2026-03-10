import os
import sys
import asyncio
import threading
import json
import logging

# --- PyInstaller Paths ---
# Imports are resolved by PyInstaller's FrozenImporter.
# No manual sys.path manipulation is needed.
# ---------------------------------------------------------------------------

from config import COLORS, load_filters, save_filters, API_ID, API_HASH, FILTERS_CONFIG_FILE, log_successful_lead, save_credentials, LOG_FILE
import customtkinter as ctk
from tkinter import messagebox, filedialog

try:
    from filter_engine import FilterEngine
except ImportError:
    # This might happen if PyInstaller fails to bundle it properly in some environments
    import logging
    logging.error("CRITICAL: Module 'filter_engine' not found. Ensure it's bundled correctly.")
    class FilterEngine:
        def __init__(self, *args, **kwargs): pass
        def is_spam(self, *args, **kwargs): return None

from ui_components import LeadFrame, SettingsWindow, ErrorLogWindow, FloatingToast, SetupAPIWindow, LoginWindow
from backend import LoadHunterBackend

# Configure initial logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
class LogHandler(logging.Handler):
    def __init__(self, ui_callback):
        super().__init__()
        self.ui_callback = ui_callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.ui_callback(msg, record.levelno)
        except Exception:
            self.handleError(record)

class LoadHunterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Hide main window initially for the Splash Screen
        self.withdraw()
        
        self.title("LoadHunter - Modular Logistics Filter")
        self.geometry("950x800")
        self.configure(fg_color=COLORS["bg_primary"])
        
        # Internal log management
        self._file_handler = None
        
        # Load filters from JSON
        self.app_config = load_filters()
        save_filters(self.app_config)
        
        self.filter_engine = FilterEngine(self.app_config)
        self.loop = asyncio.new_event_loop()
        self.lead_count = 0
        self.leads = []
        
        # Backend setup
        self.backend = LoadHunterBackend(
            loop=self.loop,
            on_lead_callback=self.on_lead_received,
            on_groups_callback=self.update_groups_ui,
            on_error_callback=self.handle_backend_error,
            on_filter_log_callback=self.on_filter_traffic,
            on_ready_callback=self.on_backend_ready
        )
        
        self.setup_ui()
        self.update_logging_handlers()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.after(100, self.show_splash_screen)

    def show_splash_screen(self):
        self.splash = ctk.CTkToplevel(self)
        self.splash.title("Loading LoadHunter...")
        self.splash.geometry("400x250")
        self.splash.configure(fg_color=COLORS["bg_primary"])
        self.splash.overrideredirect(True) # Remove windows borders for a cleaner splash
        
        self.splash.update_idletasks()
        pw = self.winfo_screenwidth() // 2
        ph = self.winfo_screenheight() // 2
        w, h = 400, 250
        self.splash.geometry(f"{w}x{h}+{pw - w // 2}+{ph - h // 2}")

        self.splash.grid_rowconfigure(0, weight=1)
        self.splash.grid_columnconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(self.splash, fg_color="transparent")
        frame.grid(row=0, column=0)
        
        ctk.CTkLabel(
            frame, text="LoadHunter", 
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(0, 5))
        
        self.splash_status = ctk.CTkLabel(
            frame, text="Checking API credentials...",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]
        )
        self.splash_status.pack(pady=(0, 15))
        
        self.splash_progress = ctk.CTkProgressBar(frame, width=250, progress_color=COLORS["accent"])
        self.splash_progress.pack()
        self.splash_progress.set(0)
        self.splash_progress.start()
        
        self.after(500, self.check_api_keys)

    def check_api_keys(self):
        from config import API_ID, API_HASH
        if not API_ID or not API_HASH:
            self.splash_progress.stop()
            self.splash_status.configure(text="Waiting for API Keys...")
            # We must set SetupAPIWindow's parent to the splash so it displays above it
            SetupAPIWindow(self.splash, self.on_api_keys_saved)
        else:
            self.splash_status.configure(text="Connecting to Telegram...")
            self.backend.start(self.filter_engine)
            
    def on_api_keys_saved(self, api_id, api_hash):
        save_credentials(api_id, api_hash)
        self.splash_progress.start()
        self.splash_status.configure(text="Connecting to Telegram...")
        self.backend.start(self.filter_engine)

    def on_backend_ready(self):
        """Called by backend when Telegram is fully connected and authorized."""
        self.after(0, self._finalize_startup)
        
    def _finalize_startup(self):
        if hasattr(self, 'splash') and self.splash.winfo_exists():
            self.splash.destroy()
        
        self.deiconify() # Show the main UI
        self.show_toast("Telegram Connected!", "success")
        self.update_status_indicator("Ready", COLORS["text_muted"])
        
        # Start listening automatically
        if not self.backend.listening:
            self.toggle_listening()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Main Panel ---
        self.main_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.main_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_panel.grid_columnconfigure(0, weight=1)
        self.main_panel.grid_rowconfigure(1, weight=1)

        self.toolbar = ctk.CTkFrame(self.main_panel, fg_color=COLORS["bg_secondary"], height=50)
        self.toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.start_btn = ctk.CTkButton(self.toolbar, text="▶ Start Listening", fg_color=COLORS["success"], command=self.toggle_listening)
        self.start_btn.pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(self.toolbar, text="Clear All", width=80, fg_color=COLORS["danger"], command=self.clear_leads).pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar, text="⚙ Settings", width=80, command=self.open_settings).pack(side="right", padx=10)

        self.leads_list = ctk.CTkScrollableFrame(self.main_panel, label_text="Clean Logistics Leads", fg_color=COLORS["bg_secondary"])
        self.leads_list.grid(row=1, column=0, sticky="nsew")
        self.leads_list.grid_columnconfigure(0, weight=1)

        # --- Side Panel ---
        self.side_panel = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], width=250)
        self.side_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.side_panel.grid_propagate(False)

        ctk.CTkLabel(self.side_panel, text="STATUS PANEL", font=ctk.CTkFont(weight="bold")).pack(pady=15)
        self.count_label = ctk.CTkLabel(self.side_panel, text="Total Caught: 0", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["success"])
        self.count_label.pack(pady=10)

        # Tabview for side panel utilities
        self.side_tabs = ctk.CTkTabview(self.side_panel, height=550, fg_color=COLORS["bg_primary"])
        self.side_tabs.pack(padx=10, pady=5, fill="both", expand=True)
        
        tab_groups = self.side_tabs.add("Groups")
        tab_system = self.side_tabs.add("System")
        tab_traffic = self.side_tabs.add("Traffic")

        self.groups_box = ctk.CTkTextbox(tab_groups, fg_color="#000000", font=ctk.CTkFont(size=11), state="disabled")
        self.groups_box.pack(padx=5, pady=5, fill="both", expand=True)

        self.log_box = ctk.CTkTextbox(tab_system, fg_color="#000000", font=ctk.CTkFont(family="monospace", size=10), state="disabled")
        self.log_box.pack(padx=5, pady=5, fill="both", expand=True)
        
        self.traffic_box = ctk.CTkTextbox(tab_traffic, fg_color="#000000", font=ctk.CTkFont(family="monospace", size=10), state="disabled")
        self.traffic_box.pack(padx=5, pady=5, fill="both", expand=True)
        
        # Status Indicator
        self.status_frame = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        self.status_frame.pack(pady=10, fill="x", padx=10)
        
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", font=ctk.CTkFont(size=20), text_color=COLORS["text_muted"])
        self.status_dot.pack(side="left", padx=(5, 0))
        
        self.status_text = ctk.CTkLabel(self.status_frame, text="Ready", font=ctk.CTkFont(size=12))
        self.status_text.pack(side="left", padx=5)

        ctk.CTkButton(self.side_panel, text="📋 View Full Logs", height=30, fg_color=COLORS["bg_card"], hover_color=COLORS["border"], command=self.open_logs).pack(pady=5, padx=10, fill="x")
        
        # Setup Log Handlers
        self.setup_logging_ui()

    def setup_logging_ui(self):
        # Pre-configure tags for different levels
        for box in [self.log_box, self.traffic_box]:
            box.tag_config("error", foreground=COLORS["danger"])
            box.tag_config("warning", foreground="#ff9800")
            box.tag_config("success", foreground=COLORS["success"])
            box.tag_config("info", foreground=COLORS["accent"])
            box.tag_config("default", foreground=COLORS["text_primary"])
            box.tag_config("gray", foreground="#666666")
        
        handler = LogHandler(self.update_log_ui)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(handler)

    def on_filter_traffic(self, sender, status):
        """Called by backend for every message processed."""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        tag = "default"
        
        if "PASSED" in status:
            tag = "success"
        elif "REJECTED" in status:
            tag = "gray"
            
        msg = f"[{time_str}] {sender[:15]:<15} | {status}"
        self.after(0, lambda m=msg, t=tag: self._append_traffic_log(m, t))

    def _append_traffic_log(self, msg, tag):
        try:
            if not self.traffic_box.winfo_exists(): return
            self.traffic_box.configure(state="normal")
            self.traffic_box.insert("end", msg + "\n", (tag,))
            self.traffic_box.see("end")
            # Limit scrollback to 500 lines
            if int(self.traffic_box.index('end-1c').split('.')[0]) > 500:
                self.traffic_box.delete("1.0", "2.0")
            self.traffic_box.configure(state="disabled")
        except Exception:
            pass

    def update_logging_handlers(self):
        """Adds or removes the FileHandler based on config."""
        root_logger = logging.getLogger()
        
        # Handle File Logging
        should_save = self.app_config.get("save_critical_logs", True)
        if should_save and not self._file_handler:
            try:
                self._file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
                self._file_handler.setLevel(logging.WARNING)
                self._file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                root_logger.addHandler(self._file_handler)
                logging.info(f"File logging enabled: {LOG_FILE}")
            except Exception as e:
                print(f"Failed to setup file logging: {e}")
        elif not should_save and self._file_handler:
            root_logger.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None
            logging.info("File logging disabled.")

    def update_log_ui(self, msg, level):
        # Check setting directly from the config
        if not self.app_config.get("show_terminal_logs", True):
            return
            
        tag = "default"
        if level >= logging.ERROR: tag = "error"
        elif level >= logging.WARNING: tag = "warning"
        elif level == logging.INFO: 
            if any(x in msg.lower() for x in ["success", "connected", "authorized"]): tag = "success"
            else: tag = "info"
            
        self.after(0, lambda m=msg, t=tag: self._append_log(m, t))

    def _append_log(self, msg, tag):
        try:
            if not self.log_box.winfo_exists(): return
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n", (tag,))
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    def open_logs(self):
        ErrorLogWindow(self, LOG_FILE)

    def show_toast(self, message, level="info"):
        FloatingToast(self, message, level)

    def update_status_indicator(self, status, color):
        self.status_dot.configure(text_color=color)
        self.status_text.configure(text=status)

    def toggle_listening(self):
        if not self.backend.listening:
            self.backend.toggle_listening(True)
            self.start_btn.configure(text="■ Stop Listening", fg_color=COLORS["danger"])
            logging.info("Starting listening process...")
            self.update_status_indicator("Connecting...", COLORS["warning"])
            if not self.backend.client or not self.backend.client.is_connected():
                self.backend.start(self.filter_engine)
            else:
                self.update_status_indicator("Listening", COLORS["success"])
        else:
            self.backend.toggle_listening(False)
            self.start_btn.configure(text="▶ Start Listening", fg_color=COLORS["success"])
            logging.info("Listening process stopped.")
            self.update_status_indicator("Idle", COLORS["text_muted"])

    def on_lead_received(self, name, common, text, link, chat_id, message_id):
        self.after(0, lambda: self._add_lead_ui(name, common, text, link, chat_id, message_id))

    def _add_lead_ui(self, name, common, text, link, chat_id, message_id):
        self.lead_count += 1
        self.count_label.configure(text=f"Total Caught: {self.lead_count}")
        card = LeadFrame(
            self.leads_list, name, common, text, link, chat_id, message_id,
            on_open_callback=log_successful_lead,
            on_forward_callback=self.forward_lead_ui
        )
        card.grid(row=self.lead_count, column=0, padx=5, pady=5, sticky="ew")
        self.leads.append(card)

    def forward_lead_ui(self, chat_id, message_id):
        destinations = self.app_config.get("forward_destinations", ["me"])
        # Ensure we don't block the UI thread
        asyncio.run_coroutine_threadsafe(
            self.backend.forward_lead(chat_id, message_id, destinations), 
            self.loop
        )

    def clear_leads(self):
        for card in self.leads: card.destroy()
        self.leads = []
        self.lead_count = 0
        self.count_label.configure(text="Total Caught: 0")

    def update_groups_ui(self, names):
        self.update_status_indicator("Listening", COLORS["success"])
        self.after(0, lambda: self._update_groups_box(names))

    def _update_groups_box(self, names):
        self.groups_box.configure(state="normal")
        self.groups_box.delete("1.0", "end")
        self.groups_box.insert("end", "\n".join(names))
        self.groups_box.configure(state="disabled")

    def handle_backend_error(self, error_code):
        if hasattr(self, 'splash') and self.splash.winfo_exists():
            self.splash.destroy() # Ensure splash is gone if we hit an error

        if error_code == "AUTH_REQUIRED":
            self.withdraw() # Ensure main window stays hidden during login
            self.after(0, self.request_login)
        else:
            self.deiconify() # Force UI to show so the user sees the error
            logging.error(f"Backend Error: {error_code}")
            self.after(0, lambda: self.show_toast(f"Error: {error_code}", "error"))
            self.update_status_indicator("Error", COLORS["danger"])

    def open_settings(self):
        SettingsWindow(self, self.app_config, on_save=self.update_config, on_import=self.import_config, on_logout=self.logout_app)

    def logout_app(self):
        if not messagebox.askyesno("Log Out", "Are you sure you want to log out from Telegram? This will delete your local session."):
            return
            
        async def do_logout():
            try:
                success = await self.backend.logout()
                if success:
                    self.after(0, lambda: messagebox.showinfo("Logged Out", "Successfully logged out from Telegram."))
                    # Reset the backend client to force re-auth
                    self.backend.client = None
                    self.after(0, lambda: self.update_status_indicator("Logged Out", COLORS["text_muted"]))
                    self.after(0, lambda: self.start_btn.configure(text="▶ Start Listening", fg_color=COLORS["success"]))
                    self.backend.listening = False
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "Failed to log out cleanly."))
            except Exception as e:
                logging.error(f"Logout Error: {e}")

        asyncio.run_coroutine_threadsafe(do_logout(), self.loop)

    def update_config(self, new_config):
        self.app_config = new_config
        self.filter_engine.config = new_config
        self.filter_engine._compile_regex()
        self.update_logging_handlers()
        logging.info("Configuration updated.")

    def import_config(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                    self.update_config(new_config)
                    save_filters(new_config)
                    messagebox.showinfo("Success", "Configuration imported successfully.")
            except Exception as e:
                logging.error(f"Import Error: {e}")
                messagebox.showerror("Error", f"Failed to import config: {e}")

    def request_login(self):
        LoginWindow(self, self.backend, on_success=self.on_backend_ready)

    def on_closing(self):
        if not messagebox.askokcancel("Quit", "Do you want to quit?"):
            return

        self.start_btn.configure(state="disabled")

        def shutdown():
            try:
                if self.backend.client and self.backend.client.is_connected():
                    logging.info("Disconnecting Telegram client...")
                    future = asyncio.run_coroutine_threadsafe(self.backend.disconnect(), self.loop)
                    # Wait up to 5 seconds for clean disconnect
                    future.result(timeout=5)
            except Exception as e:
                logging.error(f"Error during shutdown disconnect: {e}")
            finally:
                logging.info("Stopping event loop...")
                self.loop.call_soon_threadsafe(self.loop.stop)
                
                # Join the backend thread
                if self.backend._thread and self.backend._thread.is_alive():
                    self.backend._thread.join(timeout=2)
                
                logging.info("Closing application window.")
                self.after(0, self.destroy)

        # Run shutdown in a separate thread to keep UI responsive while waiting for network
        threading.Thread(target=shutdown, daemon=True).start()

if __name__ == "__main__":
    try:
        app = LoadHunterApp()
        app.mainloop()
    except Exception as e:
        logging.critical(f"Application crashed: {e}", exc_info=True)
