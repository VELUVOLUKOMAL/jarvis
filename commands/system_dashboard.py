"""
System Dashboard — Real-time floating HUD with CPU, RAM, GPU, Disk, Battery, Network.

Command: "open system monitor" / "show dashboard" / "system stats"
"""
from __future__ import annotations

import logging
import os
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

log = logging.getLogger("jarvis.dashboard")

_dashboard_instance: "Dashboard | None" = None
_dashboard_lock = threading.Lock()


class Dashboard:
    """Floating always-on-top system monitor HUD."""

    COLORS = {
        "bg":         "#0a0f1e",
        "surface":    "#111827",
        "border":     "#1e3a5f",
        "accent":     "#00d4ff",
        "accent2":    "#7c3aed",
        "text":       "#e2e8f0",
        "muted":      "#64748b",
        "good":       "#10b981",
        "warn":       "#f59e0b",
        "danger":     "#ef4444",
        "gradient1":  "#0ea5e9",
        "gradient2":  "#8b5cf6",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JARVIS System Monitor")
        self.root.overrideredirect(True)          # No title bar
        self.root.attributes("-topmost", True)    # Always on top
        self.root.attributes("-alpha", 0.92)      # Slight transparency
        self.root.configure(bg=self.COLORS["bg"])

        # Position: top-right corner
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"280x420+{sw - 295}+10")

        self._build_ui()
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

        # Allow dragging
        self.root.bind("<ButtonPress-1>",   self._drag_start)
        self.root.bind("<B1-Motion>",       self._drag_motion)

        # Double-click to close
        self.root.bind("<Double-Button-1>", lambda e: self.close())

    def _drag_start(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _drag_motion(self, e):
        x = self.root.winfo_x() + (e.x - self._drag_x)
        y = self.root.winfo_y() + (e.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        C = self.COLORS

        # Header
        header = tk.Frame(self.root, bg=C["surface"], pady=8)
        header.pack(fill="x", padx=2, pady=(2, 0))

        tk.Label(
            header, text="⚡ JARVIS SYSTEM HUD",
            bg=C["surface"], fg=C["accent"],
            font=("Consolas", 10, "bold"), pady=0
        ).pack()

        tk.Label(
            header, text="Double-click to close  •  Drag to move",
            bg=C["surface"], fg=C["muted"],
            font=("Consolas", 7)
        ).pack()

        # Main content frame
        self.content = tk.Frame(self.root, bg=C["bg"], padx=10, pady=6)
        self.content.pack(fill="both", expand=True)

        self._vars: dict[str, tk.StringVar] = {}
        self._bars: dict[str, tk.Canvas] = {}

        metrics = [
            ("CPU",     "🔲", "cpu"),
            ("RAM",     "💾", "ram"),
            ("GPU",     "🎮", "gpu"),
            ("DISK C:", "💿", "disk"),
            ("BATTERY", "🔋", "battery"),
            ("NETWORK", "🌐", "network"),
        ]

        for label, icon, key in metrics:
            self._add_metric_row(label, icon, key)

        # Time display
        self.time_var = tk.StringVar(value="--:--:--")
        tk.Label(
            self.content,
            textvariable=self.time_var,
            bg=C["bg"], fg=C["accent2"],
            font=("Consolas", 14, "bold"),
            pady=4,
        ).pack(pady=(6, 2))

        # Process count
        self.proc_var = tk.StringVar(value="Processes: --")
        tk.Label(
            self.content,
            textvariable=self.proc_var,
            bg=C["bg"], fg=C["muted"],
            font=("Consolas", 8),
        ).pack()

    def _add_metric_row(self, label: str, icon: str, key: str):
        C = self.COLORS
        frame = tk.Frame(self.content, bg=C["bg"], pady=2)
        frame.pack(fill="x")

        # Label
        tk.Label(
            frame, text=f"{icon} {label}",
            bg=C["bg"], fg=C["muted"],
            font=("Consolas", 8), width=10, anchor="w"
        ).pack(side="left")

        # Value
        var = tk.StringVar(value="--")
        self._vars[key] = var
        tk.Label(
            frame, textvariable=var,
            bg=C["bg"], fg=C["text"],
            font=("Consolas", 8, "bold"), width=8, anchor="e"
        ).pack(side="right")

        # Progress bar
        bar_frame = tk.Frame(self.content, bg=C["surface"], height=4)
        bar_frame.pack(fill="x", pady=(0, 3))

        canvas = tk.Canvas(bar_frame, bg=C["surface"], height=4,
                           highlightthickness=0, bd=0)
        canvas.pack(fill="x")
        self._bars[key] = canvas

    def _draw_bar(self, key: str, pct: float, color: str):
        canvas = self._bars.get(key)
        if not canvas:
            return
        canvas.update_idletasks()
        w = canvas.winfo_width()
        if w <= 1:
            w = 240
        canvas.delete("all")
        canvas.create_rectangle(0, 0, w, 4, fill=self.COLORS["surface"], outline="")
        filled = int(w * max(0.0, min(1.0, pct / 100)))
        if filled > 0:
            canvas.create_rectangle(0, 0, filled, 4, fill=color, outline="")

    def _pick_color(self, pct: float) -> str:
        if pct < 60:
            return self.COLORS["good"]
        if pct < 80:
            return self.COLORS["warn"]
        return self.COLORS["danger"]

    def _update_loop(self):
        while self._running:
            try:
                self.root.after(0, self._refresh_stats)
            except Exception:
                pass
            time.sleep(2)

    def _refresh_stats(self):
        try:
            import psutil
        except ImportError:
            self._vars["cpu"].set("psutil?")
            return

        # CPU
        cpu = psutil.cpu_percent(interval=None)
        self._vars["cpu"].set(f"{cpu:.0f}%")
        self._draw_bar("cpu", cpu, self._pick_color(cpu))

        # RAM
        mem = psutil.virtual_memory()
        ram_pct = mem.percent
        ram_gb = mem.used / (1024 ** 3)
        self._vars["ram"].set(f"{ram_gb:.1f}GB / {ram_pct:.0f}%")
        self._draw_bar("ram", ram_pct, self._pick_color(ram_pct))

        # GPU (try nvidia-smi)
        try:
            import subprocess, re
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                timeout=2, stderr=subprocess.DEVNULL
            ).decode().strip()
            gpu_pct = float(out.split("\n")[0].strip())
            self._vars["gpu"].set(f"{gpu_pct:.0f}%")
            self._draw_bar("gpu", gpu_pct, self._pick_color(gpu_pct))
        except Exception:
            self._vars["gpu"].set("N/A")
            self._draw_bar("gpu", 0, self.COLORS["muted"])

        # Disk C:
        try:
            disk = psutil.disk_usage("C:\\")
            disk_pct = disk.percent
            disk_free = disk.free / (1024 ** 3)
            self._vars["disk"].set(f"{disk_free:.0f}GB free")
            self._draw_bar("disk", disk_pct, self._pick_color(disk_pct))
        except Exception:
            self._vars["disk"].set("N/A")

        # Battery
        try:
            bat = psutil.sensors_battery()
            if bat:
                bat_pct = bat.percent
                plugged = "⚡" if bat.power_plugged else ""
                self._vars["battery"].set(f"{bat_pct:.0f}% {plugged}")
                self._draw_bar("battery", bat_pct,
                               self.COLORS["good"] if bat.power_plugged else self._pick_color(100 - bat_pct))
            else:
                self._vars["battery"].set("Desktop")
                self._draw_bar("battery", 0, self.COLORS["muted"])
        except Exception:
            self._vars["battery"].set("N/A")

        # Network
        try:
            net = psutil.net_io_counters()
            if not hasattr(self, "_last_net"):
                self._last_net = (net.bytes_sent, net.bytes_recv, time.time())
            else:
                s0, r0, t0 = self._last_net
                dt = time.time() - t0
                if dt > 0:
                    up_kbps   = (net.bytes_sent - s0) / 1024 / dt
                    down_kbps = (net.bytes_recv - r0) / 1024 / dt
                    self._vars["network"].set(
                        f"↑{up_kbps:.0f}K ↓{down_kbps:.0f}K"
                    )
                    # Use download speed as indicator
                    bar_pct = min(100, down_kbps / 10)  # 1000 KB/s = full bar
                    self._draw_bar("network", bar_pct, self.COLORS["accent"])
                self._last_net = (net.bytes_sent, net.bytes_recv, time.time())
        except Exception:
            self._vars["network"].set("N/A")

        # Time
        self.time_var.set(time.strftime("%H:%M:%S"))

        # Process count
        try:
            procs = len(psutil.pids())
            self.proc_var.set(f"Processes: {procs}")
        except Exception:
            pass

    def run(self):
        """Start the Tk mainloop (blocking)."""
        self.root.mainloop()

    def close(self):
        self._running = False
        try:
            self.root.destroy()
        except Exception:
            pass
        global _dashboard_instance
        with _dashboard_lock:
            _dashboard_instance = None


# ─── Public API ───────────────────────────────────────────────────────────────

def open_dashboard() -> tuple[bool, str]:
    """Open the system monitor dashboard in a background thread."""
    global _dashboard_instance
    with _dashboard_lock:
        if _dashboard_instance is not None:
            return True, "Dashboard is already open."

    def _run():
        global _dashboard_instance
        try:
            d = Dashboard()
            with _dashboard_lock:
                _dashboard_instance = d
            d.run()
        except Exception as e:
            log.warning("Dashboard error: %s", e)
        finally:
            with _dashboard_lock:
                _dashboard_instance = None

    threading.Thread(target=_run, daemon=True).start()
    return True, "System monitor dashboard is now open, sir."


def close_dashboard() -> tuple[bool, str]:
    global _dashboard_instance
    with _dashboard_lock:
        d = _dashboard_instance
    if d:
        d.close()
        return True, "Dashboard closed."
    return True, "Dashboard is not open."
