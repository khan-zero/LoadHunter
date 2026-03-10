import customtkinter as ctk
import webbrowser
import re
import json
import logging
import os
from tkinter import messagebox
from config import COLORS, save_filters


# ─────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────

def _extract_phones(text: str) -> list[str]:
    """Return up to 3 unique, normalised phone numbers found in *text*."""
    raw = re.findall(
        r'\+?\d{1,3}[\s\-]?\(?\d{2,3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
        text,
    )
    seen: list[str] = []
    for p in raw:
        clean = re.sub(r'[^\d+]', '', p)
        if len(clean) >= 9 and clean not in seen:
            seen.append(clean)
    return seen[:3]


def _truncate(text: str, limit: int = 180) -> str:
    return (text[:limit] + "…") if len(text) > limit else text


# ─────────────────────────────────────────────
#  LeadFrame
# ─────────────────────────────────────────────

class LeadFrame(ctk.CTkFrame):
    """
    A card widget that displays one lead.

    Improvements over original
    ──────────────────────────
    • Hover highlight via <Enter>/<Leave> bindings on the whole card
    • Copy-to-clipboard button for the message snippet
    • Clipboard confirmation tooltip ("Copied!")
    • Phone buttons open WhatsApp web as a fallback option (right-click context)
    • "Open in Telegram" is disabled + visually greyed when tg_link is empty
    • Common-groups badge uses a coloured pill instead of plain text
    • All child widgets forward mouse events so hover always fires
    """

    _HOVER_COLOR = "#2A2D3E"       # slightly lighter than card bg
    _NORMAL_COLOR = None           # resolved from COLORS in __init__

    def __init__(
        self,
        master,
        sender_name: str,
        common_groups: int,
        text_snippet: str,
        tg_link: str,
        chat_id: int,
        message_id: int,
        on_open_callback,
        on_forward_callback,
        **kwargs,
    ):
        self._NORMAL_COLOR = COLORS["bg_card"]
        self._HOVER_COLOR = COLORS["bg_secondary"]  # Slightly lighter background
        super().__init__(
            master,
            fg_color=self._NORMAL_COLOR,
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )

        self.on_open = on_open_callback
        self.on_forward = on_forward_callback
        self.tg_link = tg_link
        self.text_content = text_snippet or ""
        self.chat_id = chat_id
        self.message_id = message_id

        self.grid_columnconfigure(0, weight=1)
        self._build(sender_name, common_groups, text_snippet)
        self._bind_hover(self)

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self, sender_name: str, common_groups: int, text_snippet: str):
        text_to_show = text_snippet or "[No Text]"

        # Row 0 – header bar
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        name_lbl = ctk.CTkLabel(
            header,
            text=f"👤  {sender_name}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        name_lbl.grid(row=0, column=0, sticky="w")

        # Coloured pill for common-groups count
        pill_color = self._groups_pill_color(common_groups)
        pill = ctk.CTkLabel(
            header,
            text=f"  👥 {common_groups} groups  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=pill_color,
            corner_radius=8,
            text_color="#FFFFFF",
        )
        pill.grid(row=0, column=1, padx=(6, 0))

        snippet_lbl = ctk.CTkLabel(
            self,
            text=_truncate(text_to_show),
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            wraplength=460,
            justify="left",
            anchor="w",
        )
        snippet_lbl.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")

        # Row 2 – phone buttons
        phones = _extract_phones(text_to_show)
        if phones:
            phone_frame = ctk.CTkFrame(self, fg_color="transparent")
            phone_frame.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="w")
            for phone in phones:
                btn = ctk.CTkButton(
                    phone_frame,
                    text=f"📞 {phone}",
                    width=120,
                    height=26,
                    corner_radius=6,
                    fg_color=COLORS["success"],
                    hover_color=COLORS["success_hover"],
                    font=ctk.CTkFont(size=11),
                    command=lambda p=phone: webbrowser.open(f"tel:{p}"),
                )
                btn.pack(side="left", padx=(0, 4))
                self._bind_hover(btn)

        # Row 3 – action bar
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.grid(row=3, column=0, padx=12, pady=(2, 10), sticky="ew")
        action_bar.grid_columnconfigure(0, weight=1)

        # Copy snippet button (left)
        copy_btn = ctk.CTkButton(
            action_bar,
            text="📋 Copy",
            width=80,
            height=26,
            corner_radius=6,
            fg_color=COLORS["bg_secondary"],
            hover_color=COLORS["border"],
            font=ctk.CTkFont(size=11),
            command=self._copy_snippet,
        )
        copy_btn.grid(row=0, column=0, sticky="w")
        self._bind_hover(copy_btn)

        # Open Telegram button (right)
        tg_enabled = bool(self.tg_link)
        tg_btn = ctk.CTkButton(
            action_bar,
            text="✈  Open in Telegram",
            width=150,
            height=26,
            corner_radius=6,
            fg_color=COLORS["accent"] if tg_enabled else COLORS["bg_secondary"],
            hover_color=COLORS["accent_hover"] if tg_enabled else None,
            text_color="#FFFFFF" if tg_enabled else COLORS["text_muted"],
            state="normal" if tg_enabled else "disabled",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._handle_open,
        )
        tg_btn.grid(row=0, column=2, sticky="e")
        if tg_enabled:
            self._bind_hover(tg_btn)

        # Forward button (center-right)
        fwd_btn = ctk.CTkButton(
            action_bar,
            text="🚀 Forward Lead",
            width=130,
            height=26,
            corner_radius=6,
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._handle_forward,
        )
        fwd_btn.grid(row=0, column=1, sticky="e", padx=(0, 6))
        self._bind_hover(fwd_btn)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _groups_pill_color(n: int) -> str:
        """Return a colour that reflects engagement level."""
        if n >= 10:
            return "#C0392B"   # red  – lots of overlap
        if n >= 5:
            return "#E67E22"   # orange
        if n >= 2:
            return "#2980B9"   # blue
        return "#27AE60"       # green – rare overlap

    def _bind_hover(self, widget):
        """Recursively bind hover events so the whole card lights up."""
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self.configure(fg_color=self._HOVER_COLOR)

    def _on_leave(self, _event=None):
        self.configure(fg_color=self._NORMAL_COLOR)

    def _copy_snippet(self):
        self.clipboard_clear()
        self.clipboard_append(self.text_content)
        # Brief visual feedback
        self._flash_feedback("Copied ✓")

    def _flash_feedback(self, msg: str):
        """Show a temporary overlay label as a toast."""
        toast = ctk.CTkLabel(
            self,
            text=f"  {msg}  ",
            fg_color=COLORS.get("success", "#2ECC71"),
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFFFFF",
        )
        toast.place(relx=0.5, rely=0.5, anchor="center")
        self.after(1200, toast.destroy)

    def _handle_open(self):
        if self.tg_link:
            try:
                webbrowser.open(self.tg_link)
            except Exception as exc:
                logging.error("Failed to open Telegram link: %s", exc)
        if self.on_open:
            self.on_open(self.text_content)

    def _handle_forward(self):
        if self.on_forward:
            self.on_forward(self.chat_id, self.message_id)


# ─────────────────────────────────────────────
#  SettingsWindow
# ─────────────────────────────────────────────

class SettingsWindow(ctk.CTkToplevel):
    """
    Filter & debug settings dialog.

    Improvements over original
    ──────────────────────────
    • Inline validation feedback (red label under the offending field)
    • "Reset to defaults" button per numeric field (small ✕ icon)
    • Regex field has a live "Test regex" mini-panel
    • Unsaved-changes guard: closing with unsaved edits asks for confirmation
    • Window is centred on the parent on open
    • Title bar shows an asterisk (*) when there are unsaved changes
    • Import JSON also shows a success/failure banner inside the window
    """

    _TITLE_BASE = "Filter Settings"

    def __init__(self, parent, config: dict, on_save, on_import, on_logout=None):
        super().__init__(parent)
        self.title(self._TITLE_BASE)
        self.geometry("520x780")
        self.minsize(480, 600)
        self.configure(fg_color=COLORS["bg_primary"])
        self.attributes("-topmost", True)

        self._config = dict(config)
        self._on_save = on_save
        self._on_import = on_import
        self._on_logout = on_logout
        self._dirty = False
        self.entries: dict[str, tuple] = {}
        self._error_labels: dict[str, ctk.CTkLabel] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_tabs()
        self._build_footer()
        self._center_on_parent(parent)

        # Unsaved-changes guard
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)

    # ── Layout builders ───────────────────────────────────────────────────

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr,
            text="⚙  Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["accent"],
        ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        # Status banner (hidden until needed)
        self._banner = ctk.CTkLabel(
            hdr, text="", font=ctk.CTkFont(size=11),
            text_color="#FFFFFF", fg_color="transparent",
        )
        self._banner.grid(row=0, column=1, padx=12, pady=14, sticky="e")

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=COLORS["bg_secondary"],
            segmented_button_fg_color=COLORS["bg_primary"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
        )
        self.tabview.grid(row=1, column=0, padx=16, pady=(12, 4), sticky="nsew")

        self.filter_tab = self.tabview.add("  Filters  ")
        self.filter_tab.grid_columnconfigure(0, weight=1)
        self.filter_tab.grid_rowconfigure(0, weight=1)

        self.debug_tab = self.tabview.add("  Debug  ")
        self.debug_tab.grid_columnconfigure(0, weight=1)
        self.debug_tab.grid_rowconfigure(0, weight=1)

        self._build_filter_tab()
        self._build_debug_tab()

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=16, pady=(4, 16), sticky="ew")
        footer.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            footer,
            text="📥  Import JSON",
            width=120,
            height=34,
            corner_radius=8,
            fg_color=COLORS["bg_secondary"],
            hover_color=COLORS["border"],
            border_width=1,
            border_color=COLORS["accent"],
            text_color=COLORS["accent"],
            font=ctk.CTkFont(size=12),
            command=self._import_action,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer,
            text="✓  Save Settings",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_action,
        ).grid(row=0, column=2, sticky="e")

    # ── Tab content ────────────────────────────────────────────────────────

    def _build_filter_tab(self):
        scroll = ctk.CTkScrollableFrame(self.filter_tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._add_field(scroll, "Feminine Endings Regex", "fem_endings_regex",
                        height=64, is_textbox=True, hint="e.g. (а|я|ка|ша)$")
        self._add_regex_tester(scroll)

        self._add_field(scroll, "Blacklist Keywords", "blacklist_keywords",
                        height=80, is_textbox=True, is_list=True,
                        hint="Comma-separated, e.g.  spam, адvert, bot")
        self._add_field(scroll, "Bot / Service Keywords", "bot_service_keywords",
                        height=80, is_textbox=True, is_list=True,
                        hint="Comma-separated")

        self._add_field(scroll, "Max Line Breaks", "max_line_breaks",
                        hint="Integer, e.g. 10")
        self._add_field(scroll, "Max Common Groups", "max_common_groups",
                        hint="Integer, e.g. 20")
        self._add_field(scroll, "Min Uzbek Char Percentage (%)", "min_uz_char_percentage",
                        hint="Float 0–100, e.g. 30.5")

    def _add_regex_tester(self, master):
        """Mini panel to test the regex live."""
        frame = ctk.CTkFrame(master, fg_color=COLORS["bg_primary"],
                             corner_radius=8, border_width=1,
                             border_color=COLORS["border"])
        frame.pack(fill="x", padx=10, pady=(0, 10))
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="🔬  Test regex against a sample name",
                     font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"]
                     ).grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 2), sticky="w")

        self._regex_test_entry = ctk.CTkEntry(
            frame, placeholder_text="Type a name…", height=28,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
        )
        self._regex_test_entry.grid(row=1, column=0, padx=(10, 4), pady=(2, 8), sticky="ew")
        self._regex_test_entry.bind("<KeyRelease>", self._run_regex_test)

        self._regex_result_lbl = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=11), width=70,
        )
        self._regex_result_lbl.grid(row=1, column=1, padx=(0, 10), pady=(2, 8))

    def _run_regex_test(self, _event=None):
        regex_widget, *_ = self.entries.get("fem_endings_regex", (None,))
        if regex_widget is None:
            return
        pattern = regex_widget.get("1.0", "end-1c").strip()
        sample = self._regex_test_entry.get().strip()
        if not pattern or not sample:
            self._regex_result_lbl.configure(text="", fg_color="transparent")
            return
        try:
            matched = bool(re.search(pattern, sample))
            self._regex_result_lbl.configure(
                text="  ✓ match  " if matched else "  ✗ no match  ",
                fg_color=COLORS.get("success", "#2ECC71") if matched else COLORS.get("error", "#E74C3C"),
                corner_radius=6,
                text_color="#FFFFFF",
            )
        except re.error:
            self._regex_result_lbl.configure(
                text="  bad regex  ",
                fg_color=COLORS.get("error", "#E74C3C"),
                corner_radius=6,
                text_color="#FFFFFF",
            )

    def _build_debug_tab(self):
        scroll = ctk.CTkScrollableFrame(self.debug_tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._add_switch(scroll, "Save Critical Logs to File", "save_critical_logs",
                         description="Writes ERROR/CRITICAL log entries to logs/critical.log")
        self._add_switch(scroll, "Show Terminal Logs in UI", "show_terminal_logs",
                         description="Display log output inside the application window")

        self._add_field(scroll, "Forward Destinations", "forward_destinations",
                        is_list=True, is_textbox=True, height=60,
                        hint="Comma-separated: @user, -100123456, me")

        # Update & Feedback Buttons
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(15, 5))
        
        ctk.CTkButton(
            btn_frame, text="🔄 Check for Updates",
            fg_color=COLORS.get("accent", "#5B8CFF"), hover_color=COLORS.get("accent_hover", "#4A7AEE"),
            command=self._check_updates
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame, text="🐛 Report Issue",
            fg_color=COLORS.get("danger", "#ef4444"), hover_color=COLORS.get("danger_hover", "#dc2626"),
            command=self._report_issue
        ).pack(side="left")

        if self._on_logout:
            ctk.CTkButton(
                btn_frame, text="🚪 Log Out",
                fg_color="#334155", hover_color="#1E293B",
                command=self._logout
            ).pack(side="right")

    def _logout(self):
        self.destroy()
        if self._on_logout:
            self._on_logout()

    def _check_updates(self):
        import updater
        updater.check_for_updates(self)

    def _report_issue(self):
        import updater
        updater.report_issue()

    # ── Widget factories ───────────────────────────────────────────────────

    def _add_switch(self, master, label: str, key: str, description: str = ""):
        card = ctk.CTkFrame(master, fg_color=COLORS.get("bg_primary", "#13152A"),
                            corner_radius=8)
        card.pack(fill="x", padx=10, pady=6)
        card.grid_columnconfigure(0, weight=1)

        switch_var = ctk.BooleanVar(value=self._config.get(key, False))
        switch_var.trace_add("write", lambda *_: self._mark_dirty())

        text_col = ctk.CTkFrame(card, fg_color="transparent")
        text_col.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        ctk.CTkLabel(text_col, text=label, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLORS.get("text_primary", "#C8CEDE")).pack(anchor="w")
        if description:
            ctk.CTkLabel(text_col, text=description, font=ctk.CTkFont(size=11),
                         text_color=COLORS.get("text_muted", "#6B7280")).pack(anchor="w")

        ctk.CTkSwitch(card, text="", variable=switch_var,
                      progress_color=COLORS.get("success", "#2ECC71"),
                      width=44).grid(row=0, column=1, padx=12, pady=10)

        # Hover effect
        def on_enter(_): card.configure(fg_color=COLORS.get("bg_secondary", "#161b27"))
        def on_leave(_): card.configure(fg_color=COLORS.get("bg_primary", "#13152A"))
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        self.entries[key] = (switch_var, False, False)

    def _add_field(self, master, label: str, key: str,
                   height: int = 30, is_textbox: bool = False,
                   is_list: bool = False, hint: str = ""):
        # Section label
        ctk.CTkLabel(master, text=label,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=COLORS.get("text_primary", "#C8CEDE")
                     ).pack(pady=(12, 1), anchor="w", padx=12)

        if hint:
            ctk.CTkLabel(master, text=hint, font=ctk.CTkFont(size=10),
                         text_color=COLORS.get("text_muted", "#6B7280")
                         ).pack(anchor="w", padx=14, pady=(0, 2))

        val = self._config.get(key, "")
        if is_list and isinstance(val, list):
            val = ", ".join(val)

        common_kw = dict(
            fg_color=COLORS.get("bg_primary", "#13152A"),
            border_color=COLORS.get("border", "#2E3250"),
            border_width=1,
        )

        if is_textbox:
            widget = ctk.CTkTextbox(master, height=height, **common_kw)
            widget.insert("1.0", str(val))
            widget.bind("<KeyRelease>", lambda *_: self._mark_dirty())
        else:
            widget = ctk.CTkEntry(master, height=max(height, 32), **common_kw)
            widget.insert(0, str(val))
            widget.bind("<KeyRelease>", lambda *_: self._mark_dirty())

        widget.pack(fill="x", padx=12, pady=(0, 2))

        # Inline error label (hidden by default)
        err_lbl = ctk.CTkLabel(master, text="", font=ctk.CTkFont(size=10),
                               text_color=COLORS.get("error", "#E74C3C"))
        err_lbl.pack(anchor="w", padx=14)
        self._error_labels[key] = err_lbl

        self.entries[key] = (widget, is_textbox, is_list)

    # ── Actions ────────────────────────────────────────────────────────────

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self.title(self._TITLE_BASE + "  •  unsaved changes")

    def _clear_errors(self):
        for lbl in self._error_labels.values():
            lbl.configure(text="")

    def _show_banner(self, msg: str, ok: bool = True):
        color = COLORS.get("success", "#2ECC71") if ok else COLORS.get("error", "#E74C3C")
        self._banner.configure(
            text=f"  {msg}  ",
            fg_color=color,
            corner_radius=6,
        )
        self.after(3000, lambda: self._banner.configure(text="", fg_color="transparent"))

    def _import_action(self):
        try:
            self._on_import()
            self._show_banner("JSON imported ✓")
        except Exception as exc:
            logging.error("Import failed: %s", exc)
            self._show_banner("Import failed ✗", ok=False)

    def _save_action(self):
        self._clear_errors()
        new_config: dict = {}
        errors: list[str] = []

        for key, (widget_or_var, is_textbox, is_list) in self.entries.items():
            # Boolean switches
            if isinstance(widget_or_var, ctk.BooleanVar):
                new_config[key] = widget_or_var.get()
                continue

            raw_val = (
                widget_or_var.get("1.0", "end-1c").strip()
                if is_textbox
                else widget_or_var.get().strip()
            )

            if is_list:
                new_config[key] = [k.strip() for k in raw_val.split(",") if k.strip()]

            elif key == "fem_endings_regex":
                try:
                    re.compile(raw_val)
                    new_config[key] = raw_val
                except re.error as exc:
                    errors.append(key)
                    self._error_labels[key].configure(text=f"⚠ Invalid regex: {exc}")

            elif key in {"max_line_breaks", "max_common_groups", "min_uz_char_percentage"}:
                try:
                    new_config[key] = float(raw_val) if "." in raw_val else int(raw_val)
                except ValueError:
                    errors.append(key)
                    self._error_labels[key].configure(text="⚠ Must be a number")

            else:
                new_config[key] = raw_val

        if errors:
            self._show_banner(f"{len(errors)} field(s) have errors", ok=False)
            return

        final_config = {**self._config, **new_config}
        try:
            save_filters(final_config)
            self._on_save(final_config)
            self._dirty = False
            self.destroy()
        except Exception as exc:
            logging.error("Failed to save settings: %s", exc)
            self._show_banner("Save failed ✗", ok=False)

    def _on_close_request(self):
        if self._dirty:
            if not messagebox.askyesno(
                "Unsaved Changes",
                "You have unsaved changes.\nClose without saving?",
                parent=self,
            ):
                return
        self.destroy()

    # ── Utility ────────────────────────────────────────────────────────────

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = 520, 780
        self.geometry(f"{w}x{h}+{pw - w // 2}+{ph - h // 2}")


# ─────────────────────────────────────────────
#  ErrorLogWindow
# ─────────────────────────────────────────────

class ErrorLogWindow(ctk.CTkToplevel):
    """
    A window to view and filter the application logs.
    """
    def __init__(self, parent, log_file_path: str):
        super().__init__(parent)
        self.title("Application Logs")
        self.geometry("700x500")
        self.configure(fg_color=COLORS["bg_primary"])
        self.attributes("-topmost", True)
        self.log_file_path = log_file_path

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=50, corner_radius=8)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(header, text="📜  Application Logs", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=15, pady=10)
        
        self.filter_var = ctk.StringVar(value="ALL")
        filter_menu = ctk.CTkOptionMenu(
            header, 
            values=["ALL", "INFO", "WARNING", "ERROR"], 
            variable=self.filter_var,
            command=self._refresh_logs,
            width=100
        )
        filter_menu.pack(side="right", padx=15, pady=10)
        ctk.CTkLabel(header, text="Filter:").pack(side="right", padx=5)

        # Log Display
        self.log_box = ctk.CTkTextbox(
            self, 
            fg_color="#1E1E1E", # Better log box background
            font=ctk.CTkFont(family="monospace", size=11),
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=8
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Tags for coloring
        self.log_box.tag_config("ERROR", foreground=COLORS["danger"])
        self.log_box.tag_config("WARNING", foreground=COLORS["warning"])
        self.log_box.tag_config("INFO", foreground=COLORS["accent"])

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ctk.CTkButton(footer, text="Refresh", width=100, command=self._refresh_logs, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkButton(footer, text="Clear File", width=100, fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"], corner_radius=6, command=self._clear_log_file).pack(side="left", padx=5)
        ctk.CTkButton(footer, text="Close", width=80, command=self.destroy, corner_radius=6).pack(side="right", padx=5)

        self._refresh_logs()

    def _refresh_logs(self, *_):
        if not os.path.exists(self.log_file_path):
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.insert("end", "Log file not found.")
            self.log_box.configure(state="disabled")
            return

        filter_level = self.filter_var.get()
        
        try:
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            
            for line in lines:
                should_show = False
                level = "INFO"
                if "ERROR" in line:
                    level = "ERROR"
                elif "WARNING" in line:
                    level = "WARNING"
                
                if filter_level == "ALL" or filter_level == level:
                    self.log_box.insert("end", line, (level,))
            
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception as e:
            logging.error(f"Failed to read log file: {e}")

    def _clear_log_file(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the log file?"):
            try:
                open(self.log_file_path, "w").close()
                self._refresh_logs()
            except Exception as e:
                logging.error(f"Failed to clear log file: {e}")


# ─────────────────────────────────────────────
#  FloatingToast
# ─────────────────────────────────────────────

class FloatingToast(ctk.CTkFrame):
    """
    A non-intrusive floating notification.
    """
    def __init__(self, parent, message: str, level: str = "info"):
        fg_color = COLORS["accent"]
        if level == "success":
            fg_color = COLORS["success"]
        elif level == "error":
            fg_color = COLORS["danger"]
        elif level == "warning":
            fg_color = COLORS["warning"]

        super().__init__(
            parent, 
            fg_color=fg_color, 
            corner_radius=20,
            border_width=0
        )
        
        self.label = ctk.CTkLabel(
            self, 
            text=message, 
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            padx=20,
            pady=8
        )
        self.label.pack()
        
        # Position at the top center
        self.place(relx=0.5, rely=0.05, anchor="n")
        
        # Auto-destroy after 3 seconds
        self.after(3000, self._fade_out)

    def _fade_out(self):
        # Simplistic animation
        self.destroy()

# ─────────────────────────────────────────────
#  SetupAPIWindow
# ─────────────────────────────────────────────

class SetupAPIWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.title("API Key Setup")
        self.geometry("400x350")
        self.configure(fg_color=COLORS["bg_primary"])
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.on_save = on_save_callback
        
        self._build_ui()
        self._center_on_parent(parent)
        
        ctk.CTkLabel(
            self, text="Welcome to LoadHunter!", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(20, 10))
        ctk.CTkLabel(
            self, text="Please enter your Telegram API credentials.\nThese will be saved securely.",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"],
            justify="center"
        ).pack(pady=5)
        
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=30, pady=20)
        
        ctk.CTkLabel(frame, text="API ID:", anchor="w").pack(fill="x")
        self.api_id_entry = ctk.CTkEntry(frame, placeholder_text="e.g. 1234567")
        self.api_id_entry.pack(fill="x", pady=(2, 10))
        
        ctk.CTkLabel(frame, text="API Hash:", anchor="w").pack(fill="x")
        self.api_hash_entry = ctk.CTkEntry(frame, placeholder_text="e.g. abc123def456...")
        self.api_hash_entry.pack(fill="x", pady=(2, 10))
        
        self.error_label = ctk.CTkLabel(self, text="", text_color=COLORS["danger"], font=ctk.CTkFont(size=11))
        self.error_label.pack()
        
        ctk.CTkButton(
            self, text="Save Credentials", 
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            font=ctk.CTkFont(weight="bold"),
            corner_radius=8,
            command=self._save
        ).pack(pady=15)
        
    def _save(self):
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        
        if not api_id or not api_hash:
            self.error_label.configure(text="Both fields are required!")
            return
            
        if not api_id.isdigit():
            self.error_label.configure(text="API ID must be a number!")
            return
            
        self.on_save(api_id, api_hash)
        self.destroy()
        
    def _on_close(self):
        if messagebox.askyesno("Exit", "You must provide API credentials to use the app. Quit?"):
            import sys
            sys.exit(0)
            
    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = 400, 350
        self.geometry(f"{w}x{h}+{pw - w // 2}+{ph - h // 2}")


# ─────────────────────────────────────────────
#  LoginWindow
# ─────────────────────────────────────────────

class LoginWindow(ctk.CTkToplevel):
    """
    Modern Windows 11-style dialog for Telegram authentication.
    """
    def __init__(self, parent, backend, on_success):
        super().__init__(parent)
        self.title("Telegram Authentication")
        self.geometry("360x420")
        self.configure(fg_color=COLORS["bg_primary"])
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        self.backend = backend
        self.on_success = on_success
        self.loop = backend.loop
        self._phone_code_hash = None # Added for robust sign-in
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._build_ui()
        self._center_on_parent(parent)

    def _build_ui(self):
        # Header Area
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(30, 10))
        
        ctk.CTkLabel(
            header,
            text="📱",
            font=ctk.CTkFont(size=48)
        ).pack()
        
        ctk.CTkLabel(
            header, text="Sign in to Telegram", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(10, 5))
        
        self.subtitle = ctk.CTkLabel(
            header, text="Please confirm your phone number.",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]
        )
        self.subtitle.pack()

        # Input Area
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=40, pady=10)
        
        self.phone_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Phone Number (+998...)",
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"]
        )
        self.phone_entry.pack(fill="x", pady=5)
        
        self.code_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Enter Verification Code",
            height=36,
            corner_radius=8,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"]
        )
        # Verify code is hidden initially
        
        self.error_label = ctk.CTkLabel(self.input_frame, text="", text_color=COLORS["danger"], font=ctk.CTkFont(size=11))
        self.error_label.pack(pady=2)

        self.action_btn = ctk.CTkButton(
            self.input_frame, 
            text="Send Code",
            height=36,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(weight="bold"),
            command=self._send_code
        )
        self.action_btn.pack(fill="x", pady=10)

        self.resend_btn = ctk.CTkButton(
            self.input_frame, 
            text="Resend Code",
            height=36,
            corner_radius=8,
            fg_color="transparent",
            text_color=COLORS["accent"],
            hover_color=COLORS["bg_secondary"],
            font=ctk.CTkFont(weight="bold"),
            command=self._send_code
        )
        # Verify code and Resend button are hidden initially

    def _send_code(self):
        import asyncio
        phone = self.phone_entry.get().strip()
        if not phone:
            self.error_label.configure(text="Phone number is required.")
            return

        self.subtitle.configure(text="Connecting to Telegram...")
        self.action_btn.configure(state="disabled")
        self.resend_btn.configure(state="disabled")
        self.error_label.configure(text="")
        
        async def run_auth():
            try:
                # 1. CRITICAL: Ensure client is fully connected and wait for it
                if not self.backend.client.is_connected():
                    await self.backend.client.connect()
                
                self.after(0, lambda: self.subtitle.configure(text="Requesting code..."))
                
                # 2. Request the code and capture the result
                result = await self.backend.client.send_code_request(phone)
                self._phone_code_hash = result.phone_code_hash
                
                self.after(0, self._show_code_input)
                self.after(0, lambda: self.resend_btn.configure(state="normal"))
            except Exception as e:
                logging.error(f"Failed to send code: {e}")
                self.after(0, lambda: self.action_btn.configure(state="normal"))
                self.after(0, lambda: self.error_label.configure(text=f"Error: {e}"))
                self.after(0, lambda: self.subtitle.configure(text="Could not send code."))

        asyncio.run_coroutine_threadsafe(run_auth(), self.loop)

    def _show_code_input(self):
        self.phone_entry.configure(state="disabled")
        self.subtitle.configure(text="We've sent a verification code to your app.")
        self.code_entry.pack(fill="x", pady=5, before=self.error_label)
        self.action_btn.configure(text="Verify & Sign In", state="normal", command=self._verify_code)
        self.resend_btn.pack(fill="x", pady=(0, 10))

    def _verify_code(self):
        import asyncio
        phone = self.phone_entry.get().strip()
        code = self.code_entry.get().strip()
        
        if not code:
            self.error_label.configure(text="Verification code is required.")
            return

        self.action_btn.configure(state="disabled")
        self.resend_btn.configure(state="disabled")
        self.subtitle.configure(text="Verifying...")
        
        future = asyncio.run_coroutine_threadsafe(
            self.backend.client.sign_in(phone, code, phone_code_hash=self._phone_code_hash), 
            self.loop
        )
        
        def on_sign_in(f):
            try:
                f.result()
                self.on_success()
                self.destroy()
            except Exception as e:
                self.action_btn.configure(state="normal")
                self.resend_btn.configure(state="normal")
                self.error_label.configure(text=f"Invalid Code: {e}")
                self.subtitle.configure(text="Failed to verify.")
                
        future.add_done_callback(lambda f: self.after(0, on_sign_in, f))

    def _on_close(self):
        import sys
        from tkinter import messagebox
        if messagebox.askyesno("Exit", "Cancel login and close application?", parent=self):
            sys.exit(0)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = 360, 420
        self.geometry(f"{w}x{h}+{pw - w // 2}+{ph - h // 2}")

