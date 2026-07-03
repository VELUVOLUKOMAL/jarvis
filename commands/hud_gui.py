"""
Unified Cyber HUD GUI — Futuristic desktop cockpit for JARVIS OS.
Combines Chat logs, System stats, Mic button, and Plan checklists in one Tkinter dashboard.
"""
from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

log = logging.getLogger("jarvis.hud")

# Thread-safe communications queue
hud_queue = queue.Queue()

# Global HUD instance pointer
_hud_instance: "HUDApp | None" = None

class HUDApp:
    COLORS = {
        "bg":         "#060a16",
        "surface":    "#0d1b38",
        "border":     "#00e5ff",
        "accent":     "#00e5ff",
        "accent2":    "#9d4edd",
        "text":       "#e2e8f0",
        "muted":      "#566a8a",
        "good":       "#10b981",
        "warn":       "#f59e0b",
        "danger":     "#ef4444",
        "panel_bg":   "#091224",
    }

    def __init__(self, start_listening_callback=None, submit_command_callback=None):
        global _hud_instance
        _hud_instance = self
        
        self.start_listening_callback = start_listening_callback
        self.submit_command_callback = submit_command_callback
        
        self.root = tk.Tk()
        self.root.title("JARVIS OS HUD")
        self.root.configure(bg=self.COLORS["bg"])
        self.root.overrideredirect(True)          # Frameless cyber deck
        self.root.attributes("-topmost", True)    # Always on top
        self.root.attributes("-alpha", 0.96)      # Slight transparency
        
        # Sizing and placement
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 880, 580
        # Place centered-ish on screen
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2 - 40}")
        
        # State indicators
        self.status_text = "SLEEPING"
        self.status_color = self.COLORS["muted"]
        self.plan_items: list[str] = []
        self.plan_status: list[str] = [] # "pending", "active", "done"
        
        self._build_ui()
        self._setup_events()
        self._running = True
        
        # Start update loops
        self.root.after(100, self._process_hud_queue)
        threading.Thread(target=self._stats_update_loop, daemon=True).start()
        
    def _build_ui(self):
        C = self.COLORS
        
        # Outer Glowing Border
        self.outer_frame = tk.Frame(self.root, bg=C["border"], padx=2, pady=2)
        self.outer_frame.pack(fill="both", expand=True)
        
        self.main_container = tk.Frame(self.outer_frame, bg=C["bg"])
        self.main_container.pack(fill="both", expand=True)
        
        # Header Tech Bar
        self.header = tk.Frame(self.main_container, bg=C["surface"], height=35)
        self.header.pack(fill="x", side="top")
        
        tk.Label(
            self.header, text="⚡ JARVIS OS : NATURAL LANGUAGE LAYER v1.0",
            bg=C["surface"], fg=C["accent"],
            font=("Consolas", 10, "bold"), padx=10
        ).pack(side="left")
        
        # Close & Minimize Buttons
        close_btn = tk.Label(
            self.header, text="✕", bg=C["surface"], fg=C["danger"],
            font=("Consolas", 11, "bold"), padx=15, cursor="hand2"
        )
        close_btn.pack(side="right", fill="y")
        close_btn.bind("<Button-1>", lambda e: self.close())
        
        min_btn = tk.Label(
            self.header, text="—", bg=C["surface"], fg=C["accent"],
            font=("Consolas", 11, "bold"), padx=15, cursor="hand2"
        )
        min_btn.pack(side="right", fill="y")
        min_btn.bind("<Button-1>", lambda e: self._minimize())
        
        # Splitting Layout: Left (Chat, Mic) vs Right (Stats, Plan)
        self.left_pane = tk.Frame(self.main_container, bg=C["bg"], padx=10, pady=10)
        self.left_pane.pack(side="left", fill="both", expand=True)
        
        self.right_pane = tk.Frame(self.main_container, bg=C["panel_bg"], width=320, padx=10, pady=10)
        self.right_pane.pack(side="right", fill="both")
        self.right_pane.pack_propagate(False)
        
        # --- LEFT PANE CONTENT (TRANSCRIPT & COMMANDS) ---
        # Chat log title
        tk.Label(
            self.left_pane, text="💬 INTERACTIVE LOG MATRIX",
            bg=C["bg"], fg=C["accent"],
            font=("Consolas", 9, "bold")
        ).pack(anchor="w")
        
        # Scrollable log area
        log_frame = tk.Frame(self.left_pane, bg=C["surface"], bd=1, relief="flat")
        log_frame.pack(fill="both", expand=True, pady=(5, 10))
        
        self.chat_log = tk.Text(
            log_frame, bg=C["bg"], fg=C["text"],
            font=("Consolas", 10), insertbackground=C["accent"],
            relief="flat", wrap="word", state="disabled", padx=8, pady=8
        )
        self.chat_log.pack(side="left", fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(log_frame, command=self.chat_log.yview, bg=C["bg"])
        scrollbar.pack(side="right", fill="y")
        self.chat_log.config(yscrollcommand=scrollbar.set)
        
        # Tags for text formatting
        self.chat_log.tag_config("user", foreground=C["accent"], font=("Consolas", 10, "bold"))
        self.chat_log.tag_config("jarvis", foreground=C["accent2"], font=("Consolas", 10, "bold"))
        self.chat_log.tag_config("system", foreground=C["good"], font=("Consolas", 9, "italic"))
        self.chat_log.tag_config("error", foreground=C["danger"], font=("Consolas", 9, "bold"))
        
        # Bottom Mic Button + Silent Command Input Row
        self.bottom_bar = tk.Frame(self.left_pane, bg=C["bg"])
        self.bottom_bar.pack(fill="x", side="bottom")
        
        # Canvas Microphone Button (Glowing pulse)
        self.mic_canvas = tk.Canvas(
            self.bottom_bar, bg=C["bg"], width=60, height=60, 
            highlightthickness=0, cursor="hand2"
        )
        self.mic_canvas.pack(side="left", padx=(0, 10))
        self.mic_canvas.bind("<Button-1>", lambda e: self._on_mic_clicked())
        self._draw_mic_button("idle")
        
        # Entry row
        input_container = tk.Frame(self.bottom_bar, bg=C["surface"], padx=8, pady=4)
        input_container.pack(side="right", fill="both", expand=True)
        
        tk.Label(
            input_container, text="> ", fg=C["accent"], bg=C["surface"],
            font=("Consolas", 12, "bold")
        ).pack(side="left")
        
        self.entry_var = tk.StringVar()
        self.cmd_entry = tk.Entry(
            input_container, textvariable=self.entry_var,
            bg=C["surface"], fg=C["text"], relief="flat",
            insertbackground=C["accent"], font=("Consolas", 11), bd=0
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", self._on_cmd_submitted)
        
        # --- RIGHT PANE CONTENT (STATS & PLAN RUNNER) ---
        # Status Section
        status_frame = tk.Frame(self.right_pane, bg=C["panel_bg"])
        status_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            status_frame, text="⚡ SYSTEM STATUS",
            bg=C["panel_bg"], fg=C["muted"],
            font=("Consolas", 8, "bold")
        ).pack(anchor="w")
        
        self.status_lbl = tk.Label(
            status_frame, text="SLEEPING",
            bg=C["panel_bg"], fg=C["muted"],
            font=("Consolas", 14, "bold")
        ).pack(anchor="w")
        
        # Real-time Metrics Hud
        tk.Label(
            self.right_pane, text="🔲 HARDWARE MONITOR MATRIX",
            bg=C["panel_bg"], fg=C["accent"],
            font=("Consolas", 9, "bold")
        ).pack(anchor="w", pady=(0, 5))
        
        self.metrics_container = tk.Frame(self.right_pane, bg=C["panel_bg"])
        self.metrics_container.pack(fill="x", pady=(0, 15))
        
        self._vars: dict[str, tk.StringVar] = {}
        self._bars: dict[str, tk.Canvas] = {}
        
        metrics = [
            ("CPU",     "cpu"),
            ("RAM",     "ram"),
            ("GPU",     "gpu"),
            ("BATTERY", "battery"),
            ("NETWORK", "network")
        ]
        for name, key in metrics:
            self._add_metric_row(name, key)
            
        # Plan / Checklist section
        tk.Label(
            self.right_pane, text="📋 PLAN EXECUTION TRACKER",
            bg=C["panel_bg"], fg=C["accent"],
            font=("Consolas", 9, "bold")
        ).pack(anchor="w", pady=(5, 5))
        
        self.plan_frame = tk.Frame(self.right_pane, bg=C["surface"], bd=1)
        self.plan_frame.pack(fill="both", expand=True)
        
        self.plan_list_frame = tk.Frame(self.plan_frame, bg=C["bg"])
        self.plan_list_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Welcome placeholder inside plan tracker
        self.plan_placeholder = tk.Label(
            self.plan_list_frame, text="No active execution plan.\nGive a multi-step task like\n'start coding session' or\n'install discord'.",
            bg=C["bg"], fg=C["muted"], font=("Consolas", 9)
        )
        self.plan_placeholder.pack(fill="both", expand=True)

    def _add_metric_row(self, name: str, key: str):
        C = self.COLORS
        row = tk.Frame(self.metrics_container, bg=C["panel_bg"])
        row.pack(fill="x", pady=2)
        
        tk.Label(row, text=name, bg=C["panel_bg"], fg=C["muted"], font=("Consolas", 8), width=8, anchor="w").pack(side="left")
        
        var = tk.StringVar(value="--")
        self._vars[key] = var
        tk.Label(row, textvariable=var, bg=C["panel_bg"], fg=C["text"], font=("Consolas", 8, "bold"), width=15, anchor="e").pack(side="right")
        
        # Mini bar
        bar_frame = tk.Frame(self.metrics_container, bg=C["surface"], height=3)
        bar_frame.pack(fill="x", pady=(0, 4))
        
        canvas = tk.Canvas(bar_frame, bg=C["surface"], height=3, highlightthickness=0, bd=0)
        canvas.pack(fill="x")
        self._bars[key] = canvas

    def _draw_mic_button(self, state: str):
        C = self.COLORS
        self.mic_canvas.delete("all")
        
        # Colors based on states
        if state == "listening":
            circle_color = C["accent"]
            outline_color = "#ffffff"
            pulse_ring = True
        elif state == "thinking":
            circle_color = C["accent2"]
            outline_color = C["accent2"]
            pulse_ring = False
        else:
            circle_color = C["surface"]
            outline_color = C["muted"]
            pulse_ring = False
            
        # Draw outer circle
        self.mic_canvas.create_oval(5, 5, 55, 55, fill=circle_color, outline=outline_color, width=2, tags="bg_circle")
        # Draw inner microphone icon
        # Mic stand
        self.mic_canvas.create_line(30, 42, 30, 48, fill=C["text"], width=3)
        self.mic_canvas.create_line(22, 48, 38, 48, fill=C["text"], width=3)
        # Mic cup
        self.mic_canvas.create_arc(18, 18, 42, 42, start=180, extent=180, outline=C["text"], width=3, style="arc")
        # Mic core
        self.mic_canvas.create_rectangle(24, 16, 36, 36, fill=C["text"], outline=C["text"], width=1)
        
        if pulse_ring:
            # Pulsing rings
            self.mic_canvas.create_oval(1, 1, 59, 59, outline=C["accent"], width=1, tags="ring1")

    def _setup_events(self):
        # Enable dragging
        self.header.bind("<ButtonPress-1>", self._drag_start)
        self.header.bind("<B1-Motion>", self._drag_motion)
        
    def _drag_start(self, e):
        self._drag_x = e.x
        self._drag_y = e.y
        
    def _drag_motion(self, e):
        x = self.root.winfo_x() + (e.x - self._drag_x)
        y = self.root.winfo_y() + (e.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")
        
    def _on_mic_clicked(self):
        # Trigger listening callback
        if self.start_listening_callback:
            self.start_listening_callback()

    def _on_cmd_submitted(self, e=None):
        cmd = self.entry_var.get().strip()
        if not cmd:
            return
        self.entry_var.set("")
        self.log_message("YOU", cmd)
        if self.submit_command_callback:
            threading.Thread(target=self.submit_command_callback, args=(cmd,), daemon=True).start()

    def log_message(self, sender: str, text: str):
        self.root.after(0, lambda: self._log_message_gui(sender, text))
        
    def _log_message_gui(self, sender: str, text: str):
        self.chat_log.config(state="normal")
        if sender == "YOU":
            self.chat_log.insert("end", f"▶ {sender}: ", "user")
            self.chat_log.insert("end", f"{text}\n\n")
        elif sender == "JARVIS":
            self.chat_log.insert("end", f"⚡ {sender}: ", "jarvis")
            self.chat_log.insert("end", f"{text}\n\n")
        elif sender == "SYSTEM":
            self.chat_log.insert("end", f"⚙ {text}\n", "system")
        elif sender == "ERROR":
            self.chat_log.insert("end", f"⚠ {text}\n", "error")
        self.chat_log.config(state="disabled")
        self.chat_log.see("end")

    def set_status(self, status: str):
        self.root.after(0, lambda: self._set_status_gui(status))
        
    def _set_status_gui(self, status: str):
        self.status_text = status.upper()
        if self.status_text == "LISTENING...":
            self.status_color = self.COLORS["accent"]
            self._draw_mic_button("listening")
        elif self.status_text == "THINKING...":
            self.status_color = self.COLORS["accent2"]
            self._draw_mic_button("thinking")
        elif self.status_text == "ACTING...":
            self.status_color = self.COLORS["good"]
            self._draw_mic_button("thinking")
        else:
            self.status_color = self.COLORS["muted"]
            self._draw_mic_button("idle")
            
        # Re-create/modify status label
        for child in self.right_pane.winfo_children():
            if isinstance(child, tk.Frame):
                # Search inside status frame
                for sub in child.winfo_children():
                    try:
                        txt = sub.cget("text")
                    except Exception:
                        continue  # widget doesn't support -text (e.g. Frame)
                    if txt not in ["⚡ SYSTEM STATUS", ""]:
                        try:
                            sub.config(text=self.status_text, fg=self.status_color)
                        except Exception:
                            pass
                        break

    def start_plan(self, steps: list[str]):
        self.root.after(0, lambda: self._start_plan_gui(steps))
        
    def _start_plan_gui(self, steps: list[str]):
        # Clear placeholder
        self.plan_placeholder.pack_forget()
        for widget in self.plan_list_frame.winfo_children():
            widget.destroy()
            
        self.plan_items = steps
        self.plan_status = ["pending"] * len(steps)
        self._vars_plan = []
        
        C = self.COLORS
        for i, step in enumerate(steps):
            row = tk.Frame(self.plan_list_frame, bg=C["bg"])
            row.pack(fill="x", anchor="w", pady=4, padx=8)
            
            chk_lbl = tk.Label(row, text="[ ]", fg=C["muted"], bg=C["bg"], font=("Consolas", 10, "bold"))
            chk_lbl.pack(side="left", padx=(0, 6))
            
            txt_lbl = tk.Label(row, text=step, fg=C["text"], bg=C["bg"], font=("Consolas", 9))
            txt_lbl.pack(side="left", anchor="w")
            
            self._vars_plan.append((chk_lbl, txt_lbl))

    def update_plan_step(self, step_idx: int, status: str):
        self.root.after(0, lambda: self._update_plan_step_gui(step_idx, status))
        
    def _update_plan_step_gui(self, step_idx: int, status: str):
        if step_idx < 0 or step_idx >= len(self._vars_plan):
            return
        chk_lbl, txt_lbl = self._vars_plan[step_idx]
        C = self.COLORS
        if status == "active":
            chk_lbl.config(text="»", fg=C["warn"])
            txt_lbl.config(fg="#ffffff", font=("Consolas", 9, "bold"))
        elif status == "done":
            chk_lbl.config(text="✓", fg=C["good"])
            txt_lbl.config(fg=C["muted"], font=("Consolas", 9))
        else:
            chk_lbl.config(text="[ ]", fg=C["muted"])
            txt_lbl.config(fg=C["text"], font=("Consolas", 9))

    def _draw_bar(self, key: str, pct: float, color: str):
        canvas = self._bars.get(key)
        if not canvas:
            return
        w = canvas.winfo_width()
        if w <= 1:
            w = 200
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, 3, fill=self.COLORS["surface"], outline="")
        filled = int(w * max(0.0, min(1.0, pct / 100)))
        if filled > 0:
            canvas.create_rectangle(0, 0, filled, 3, fill=color, outline="")

    def _pick_color(self, pct: float) -> str:
        if pct < 60:
            return self.COLORS["good"]
        if pct < 80:
            return self.COLORS["warn"]
        return self.COLORS["danger"]

    def _stats_update_loop(self):
        """Periodically query system stats."""
        try:
            import psutil
        except ImportError:
            return
            
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                ram_pct = mem.percent
                ram_gb = mem.used / (1024 ** 3)
                
                # Disk usage
                disk_pct = 0.0
                try:
                    disk = psutil.disk_usage("C:\\")
                    disk_pct = disk.percent
                except Exception:
                    pass
                    
                # Battery
                bat_pct = 100.0
                plugged = False
                try:
                    bat = psutil.sensors_battery()
                    if bat:
                        bat_pct = bat.percent
                        plugged = bat.power_plugged
                except Exception:
                    pass
                    
                # Network speed
                net = psutil.net_io_counters()
                if not hasattr(self, "_last_net"):
                    self._last_net = (net.bytes_sent, net.bytes_recv, time.time())
                    net_kbps = 0.0
                else:
                    s0, r0, t0 = self._last_net
                    dt = time.time() - t0
                    net_kbps = 0.0
                    if dt > 0:
                        net_kbps = ((net.bytes_sent - s0) + (net.bytes_recv - r0)) / 1024 / dt
                    self._last_net = (net.bytes_sent, net.bytes_recv, time.time())
                
                # Push GUI updates
                self.root.after(0, lambda: self._update_metrics_gui(cpu, ram_pct, ram_gb, disk_pct, bat_pct, plugged, net_kbps))
            except Exception as e:
                log.warning("Stats read error: %s", e)
            time.sleep(2.0)

    def _update_metrics_gui(self, cpu, ram_pct, ram_gb, disk_pct, bat_pct, plugged, net_kbps):
        C = self.COLORS
        # CPU
        self._vars["cpu"].set(f"{cpu:.0f}%")
        self._draw_bar("cpu", cpu, self._pick_color(cpu))
        # RAM
        self._vars["ram"].set(f"{ram_gb:.1f}GB / {ram_pct:.0f}%")
        self._draw_bar("ram", ram_pct, self._pick_color(ram_pct))
        # GPU / DISK (re-use GPU row as Disk)
        self._vars["gpu"].set(f"{disk_pct:.0f}% USED")
        self._draw_bar("gpu", disk_pct, self._pick_color(disk_pct))
        # Battery
        plug = " ⚡" if plugged else ""
        self._vars["battery"].set(f"{bat_pct:.0f}%{plug}")
        self._draw_bar("battery", bat_pct, C["good"] if plugged else self._pick_color(100 - bat_pct))
        # Network
        self._vars["network"].set(f"{net_kbps:.0f} KB/s")
        net_bar_pct = min(100.0, net_kbps / 10.0) # 1MB/s = full bar
        self._draw_bar("network", net_bar_pct, C["accent"])

    def _process_hud_queue(self):
        """Poll the communications queue for updates from background tasks."""
        try:
            while True:
                msg_type, data = hud_queue.get_nowait()
                if msg_type == "CHAT_LOG":
                    sender, text = data
                    self._log_message_gui(sender, text)
                elif msg_type == "STATUS":
                    self._set_status_gui(data)
                elif msg_type == "PLAN_START":
                    self._start_plan_gui(data)
                elif msg_type == "PLAN_STEP_ACTIVE":
                    self._update_plan_step_gui(data, "active")
                elif msg_type == "PLAN_STEP_COMPLETE":
                    self._update_plan_step_gui(data, "done")
                elif msg_type == "PLAN_STEP_PENDING":
                    self._update_plan_step_gui(data, "pending")
                elif msg_type == "SHOW_EMAIL_TRANSMISSION":
                    self._show_email_transmission(data)
                elif msg_type == "SHOW_SETUP_WINDOW":
                    self._show_setup_window(data)
                elif msg_type == "ASK_CONFIRMATION":
                    prompt, q_res = data
                    self._ask_confirmation_dialog(prompt, q_res)
                hud_queue.task_done()
        except queue.Empty:
            pass
        if self._running:
            self.root.after(100, self._process_hud_queue)

    def _show_email_transmission(self, zip_path: str):
        """Simulate sending an email with a file attachment."""
        C = self.COLORS
        email_win = tk.Toplevel(self.root)
        email_win.title("JARVIS SECURE MAIL TRANSMITTER")
        email_win.geometry("450x260")
        email_win.overrideredirect(True)
        email_win.attributes("-topmost", True)
        email_win.configure(bg=C["bg"])
        
        # Center popup
        sw = email_win.winfo_screenwidth()
        sh = email_win.winfo_screenheight()
        email_win.geometry(f"450x260+{(sw-450)//2}+{(sh-260)//2}")
        
        # Border frame
        border = tk.Frame(email_win, bg=C["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=C["bg"], padx=15, pady=15)
        inner.pack(fill="both", expand=True)
        
        tk.Label(inner, text="📤 SECURE OUTGOING TRANSMISSION", fg=C["accent"], bg=C["bg"], font=("Consolas", 11, "bold")).pack(pady=(0, 10))
        
        details_frame = tk.Frame(inner, bg=C["surface"], padx=8, pady=8)
        details_frame.pack(fill="x", pady=5)
        
        tk.Label(details_frame, text="Recipient: teammate@hackathon.dev", fg=C["text"], bg=C["surface"], font=("Consolas", 9)).pack(anchor="w")
        tk.Label(details_frame, text=f"Attachment: {Path(zip_path).name}", fg=C["accent2"], bg=C["surface"], font=("Consolas", 9)).pack(anchor="w")
        
        status_lbl = tk.Label(inner, text="Initiating handshake protocol...", fg=C["text"], bg=C["bg"], font=("Consolas", 9))
        status_lbl.pack(pady=5)
        
        canvas = tk.Canvas(inner, bg=C["surface"], height=16, highlightthickness=0)
        canvas.pack(fill="x", pady=10)
        
        def animate():
            for i in range(1, 101, 5):
                if not email_win.winfo_exists():
                    return
                canvas.delete("all")
                w = canvas.winfo_width() or 400
                canvas.create_rectangle(0, 0, int(w * i / 100), 16, fill=C["border"], outline="")
                status_lbl.config(text=f"Uploading packets: {i}%")
                email_win.update()
                time.sleep(0.12)
            if email_win.winfo_exists():
                status_lbl.config(text="[SUCCESS] Transmission complete! Archive encrypted and sent.", fg=C["good"])
                email_win.update()
                time.sleep(1.2)
                email_win.destroy()
                
        threading.Thread(target=animate, daemon=True).start()

    def _show_setup_window(self, software_name: str):
        """Simulate installing a application."""
        C = self.COLORS
        setup_win = tk.Toplevel(self.root)
        setup_win.title(f"{software_name.title()} Setup Wizard")
        setup_win.geometry("400x230")
        setup_win.overrideredirect(True)
        setup_win.attributes("-topmost", True)
        setup_win.configure(bg=C["bg"])
        
        # Center popup
        sw = setup_win.winfo_screenwidth()
        sh = setup_win.winfo_screenheight()
        setup_win.geometry(f"400x230+{(sw-400)//2}+{(sh-230)//2}")
        
        border = tk.Frame(setup_win, bg=C["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=C["bg"], padx=15, pady=15)
        inner.pack(fill="both", expand=True)
        
        lbl = tk.Label(inner, text=f"Installing {software_name.title()} Wizard", fg=C["accent"], bg=C["bg"], font=("Consolas", 11, "bold"))
        lbl.pack(pady=(0, 15))
        
        details = tk.Label(inner, text="Extracting files: package.zip", fg=C["text"], bg=C["bg"], font=("Consolas", 9))
        details.pack(pady=5)
        
        canvas = tk.Canvas(inner, bg=C["surface"], height=16, highlightthickness=0)
        canvas.pack(fill="x", pady=10)
        
        def animate():
            for i in range(1, 101, 10):
                if not setup_win.winfo_exists():
                    return
                canvas.delete("all")
                w = canvas.winfo_width() or 350
                canvas.create_rectangle(0, 0, int(w * i / 100), 16, fill=C["accent2"], outline="")
                details.config(text=f"Deploying registry keys and binary matrices... {i}%")
                setup_win.update()
                time.sleep(0.25)
            if setup_win.winfo_exists():
                details.config(text="[SUCCESS] Software fully deployed and integrated.", fg=C["good"])
                setup_win.update()
                time.sleep(1.2)
                setup_win.destroy()
                
        threading.Thread(target=animate, daemon=True).start()

    def _ask_confirmation_dialog(self, prompt: str, q_res: queue.Queue):
        """Displays a custom yes/no verification dialog."""
        C = self.COLORS
        conf_win = tk.Toplevel(self.root)
        conf_win.geometry("380x150")
        conf_win.overrideredirect(True)
        conf_win.attributes("-topmost", True)
        conf_win.configure(bg=C["bg"])
        
        sw = conf_win.winfo_screenwidth()
        sh = conf_win.winfo_screenheight()
        conf_win.geometry(f"380x150+{(sw-380)//2}+{(sh-150)//2}")
        
        border = tk.Frame(conf_win, bg=C["accent2"], padx=1, pady=1)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=C["bg"], padx=15, pady=15)
        inner.pack(fill="both", expand=True)
        
        tk.Label(inner, text="⚡ CORE CONFIRMATION REQUISITION", fg=C["accent2"], bg=C["bg"], font=("Consolas", 10, "bold")).pack(pady=(0, 10))
        tk.Label(inner, text=prompt, fg=C["text"], bg=C["bg"], font=("Consolas", 9), wraplength=340).pack(pady=5)
        
        btn_frame = tk.Frame(inner, bg=C["bg"])
        btn_frame.pack(pady=10)
        
        def on_yes():
            q_res.put(True)
            conf_win.destroy()
            
        def on_no():
            q_res.put(False)
            conf_win.destroy()
            
        tk.Button(
            btn_frame, text="[ YES ]", command=on_yes,
            bg=C["surface"], fg=C["good"], relief="flat",
            activebackground=C["good"], activeforeground="white",
            font=("Consolas", 9, "bold"), bd=0, padx=15
        ).pack(side="left", padx=10)
        
        tk.Button(
            btn_frame, text="[ CANCEL ]", command=on_no,
            bg=C["surface"], fg=C["danger"], relief="flat",
            activebackground=C["danger"], activeforeground="white",
            font=("Consolas", 9, "bold"), bd=0, padx=15
        ).pack(side="left", padx=10)

    def _minimize(self):
        """Minimize the HUD by hiding it. Click tray or press Ctrl+Shift+J to restore."""
        self.root.withdraw()
        # Schedule auto-restore after 3 minutes in case user forgets
        self.root.after(180000, self._restore)

    def _restore(self):
        """Restore the HUD window."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
        except Exception:
            pass

    def close(self):
        self._running = False
        global _hud_instance
        _hud_instance = None
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def run(self):
        # Bind Ctrl+Shift+J to restore the window from anywhere
        self.root.bind_all("<Control-Shift-J>", lambda e: self._restore())
        self.root.mainloop()

# --- Thread-Safe Public APIs to interact with HUD ---

def log_to_hud(sender: str, text: str):
    hud_queue.put(("CHAT_LOG", (sender, text)))

def set_hud_status(status: str):
    hud_queue.put(("STATUS", status))

def start_hud_plan(steps: list[str]):
    hud_queue.put(("PLAN_START", steps))

def set_hud_plan_step_active(step_idx: int):
    hud_queue.put(("PLAN_STEP_ACTIVE", step_idx))

def set_hud_plan_step_complete(step_idx: int):
    hud_queue.put(("PLAN_STEP_COMPLETE", step_idx))

def set_hud_plan_step_pending(step_idx: int):
    hud_queue.put(("PLAN_STEP_PENDING", step_idx))

def trigger_hud_email_window(zip_path: str):
    hud_queue.put(("SHOW_EMAIL_TRANSMISSION", zip_path))

def trigger_hud_setup_window(software_name: str):
    hud_queue.put(("SHOW_SETUP_WINDOW", software_name))

def trigger_hud_confirmation(prompt: str, res_queue: queue.Queue):
    hud_queue.put(("ASK_CONFIRMATION", (prompt, res_queue)))
