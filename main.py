import os
import sys
import asyncio
import threading
import json
import logging

# --- CRITICAL WINDOWS FIX: Ensure local modules are found in frozen state ---
def get_base_dir():
    if getattr(sys, 'frozen', False):
        # If running as PyInstaller bundle
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# ---------------------------------------------------------------------------

from config import COLORS, load_filters, save_filters, API_ID, API_HASH, FILTERS_CONFIG_FILE, log_successful_lead, save_credentials
import customtkinter as ctk
from tkinter import messagebox, filedialog
from filter_engine import FilterEngine
from ui_components import LeadFrame, SettingsWindow, ErrorLogWindow, FloatingToast, SetupAPIWindow
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
            on_error_callback=self.handle_backend_error
        )
        
        self.setup_ui()
        self.update_logging_handlers() # Apply logging settings
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Check API Keys
        self.after(200, self.check_api_keys)

    def check_api_keys(self):
        from config import API_ID, API_HASH
        if not API_ID or not API_HASH:
            self.start_btn.configure(state="disabled")
            SetupAPIWindow(self, self.on_api_keys_saved)
            
    def on_api_keys_saved(self, api_id, api_hash):
        save_credentials(api_id, api_hash)
        self.start_btn.configure(state="normal")
        self.show_toast("API Credentials saved!", "success")

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

        self.groups_box = ctk.CTkTextbox(self.side_panel, height=200, fg_color=COLORS["bg_primary"], font=ctk.CTkFont(size=11), state="disabled")
        self.groups_box.pack(padx=10, pady=5, fill="x")

        # Status Indicator
        self.status_frame = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        self.status_frame.pack(pady=10, fill="x", padx=10)
        
        self.status_dot = ctk.CTkLabel(self.status_frame, text="●", font=ctk.CTkFont(size=20), text_color=COLORS["text_muted"])
        self.status_dot.pack(side="left", padx=(5, 0))
        
        self.status_text = ctk.CTkLabel(self.status_frame, text="Ready", font=ctk.CTkFont(size=12))
        self.status_text.pack(side="left", padx=5)

        ctk.CTkButton(self.side_panel, text="📋 View Full Logs", height=30, fg_color=COLORS["bg_card"], hover_color=COLORS["border"], command=self.open_logs).pack(pady=5, padx=10, fill="x")

        ctk.CTkLabel(self.side_panel, text="Terminal Logs:", font=ctk.CTkFont(size=12)).pack(pady=(10, 5))
        self.log_box = ctk.CTkTextbox(self.side_panel, height=300, fg_color="#000000", font=ctk.CTkFont(family="monospace", size=10), state="disabled")
        self.log_box.pack(padx=10, pady=5, fill="both", expand=True)
        
        # Setup Log Handler
        self.setup_logging_ui()

    def setup_logging_ui(self):
        # Pre-configure tags for different levels
        self.log_box.tag_config("error", foreground=COLORS["danger"])
        self.log_box.tag_config("warning", foreground="#ff9800")
        self.log_box.tag_config("success", foreground=COLORS["success"])
        self.log_box.tag_config("info", foreground=COLORS["accent"])
        self.log_box.tag_config("default", foreground=COLORS["text_primary"])
        
        handler = LogHandler(self.update_log_ui)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(handler)

    def update_logging_handlers(self):
        """Adds or removes the FileHandler based on config."""
        root_logger = logging.getLogger()
        
        # Handle File Logging
        should_save = self.app_config.get("save_critical_logs", True)
        if should_save and not self._file_handler:
            try:
                self._file_handler = logging.FileHandler("loadhunter.log", encoding='utf-8')
                self._file_handler.setLevel(logging.WARNING)
                self._file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                root_logger.addHandler(self._file_handler)
                logging.info("File logging enabled (Warnings/Errors only).")
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
        ErrorLogWindow(self, "loadhunter.log")

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
        if error_code == "AUTH_REQUIRED":
            self.after(0, self.request_login)
            self.update_status_indicator("Auth Required", COLORS["danger"])
        else:
            logging.error(f"Backend Error: {error_code}")
            self.after(0, lambda: self.show_toast(f"Error: {error_code}", "error"))
            self.update_status_indicator("Error", COLORS["danger"])

    def open_settings(self):
        SettingsWindow(self, self.app_config, on_save=self.update_config, on_import=self.import_config)

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
        win = ctk.CTkToplevel(self)
        win.title("Telegram Login")
        win.geometry("300x350")
        win.attributes("-topmost", True)
        
        ctk.CTkLabel(win, text="Phone Number (+998...)").pack(pady=5)
        phone_entry = ctk.CTkEntry(win)
        phone_entry.pack(pady=5)
        
        code_entry = ctk.CTkEntry(win, placeholder_text="Enter Code")
        
        def send_code():
            phone = phone_entry.get().strip()
            if not phone: return
            
            # Ensure backend is initialized
            if not self.backend.client:
                from telethon import TelegramClient
                from config import SESSION_DIR
                session_path = os.path.join(SESSION_DIR, 'loadhunter_session')
                self.backend.client = TelegramClient(session_path, int(API_ID), API_HASH)
            
            if not self.backend.client.is_connected():
                asyncio.run_coroutine_threadsafe(self.backend.client.connect(), self.loop)

            asyncio.run_coroutine_threadsafe(self.backend.client.send_code_request(phone), self.loop)
            phone_entry.configure(state="disabled")
            code_entry.pack(pady=10)
            ctk.CTkButton(win, text="Sign In", command=lambda: sign_in(phone)).pack(pady=5)
            
        def sign_in(phone):
            code = code_entry.get().strip()
            if not code or not self.backend.client: return
            asyncio.run_coroutine_threadsafe(self.backend.client.sign_in(phone, code), self.loop)
            win.destroy()
            self.toggle_listening()
            
        ctk.CTkButton(win, text="Send Verification Code", command=send_code).pack(pady=10)

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
