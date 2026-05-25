"""
gui.py
------
BowlingMachineGUI — Tkinter-based graphical interface.

OOP Concept Used:
  - Composition — the GUI owns instances of BowlingMachine, Controller,
    VoiceProcessor, and TextToSpeech rather than extending them.
  - Observer-like pattern — after each command, the GUI refreshes its
    status panel to reflect the new machine state.

Layout
------
  ┌─────────────────────────────────────────┐
  │  🎳 VOICE-CONTROLLED BOWLING MACHINE    │ ← Title
  ├──────────────┬──────────────────────────┤
  │  STATUS      │  EVENT LOG               │
  │  Panel       │  (scrollable)            │
  ├──────────────┴──────────────────────────┤
  │  [🎙 Listen]  [Text input]  [Send]       │ ← Controls
  │  [Help / Command List]                   │
  └─────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import queue
import logging
from datetime import datetime

from machine        import BowlingMachine
from controller     import Controller
from voice_processor import VoiceProcessor
from tts            import TextToSpeech


# ── Colour Palette ─────────────────────────────────────────────────────────
CLR_BG        = "#0d1117"   # page background (GitHub Dark)
CLR_PANEL     = "#161b22"   # card / panel background
CLR_BORDER    = "#30363d"   # subtle border
CLR_TEXT      = "#c9d1d9"   # primary text
CLR_MUTED     = "#8b949e"   # secondary / muted text
CLR_GREEN     = "#3fb950"   # running / on
CLR_RED       = "#f85149"   # stopped / off
CLR_AMBER     = "#d29922"   # medium speed
CLR_BLUE      = "#58a6ff"   # accent / buttons
CLR_PURPLE    = "#bc8cff"   # spin
CLR_ENTRY_BG  = "#21262d"   # text-entry background
CLR_LOG_BG    = "#0d1117"   # log background
FONT_TITLE    = ("Segoe UI", 18, "bold")
FONT_LABEL    = ("Segoe UI", 10)
FONT_VALUE    = ("Segoe UI", 13, "bold")
FONT_BUTTON   = ("Segoe UI", 10, "bold")
FONT_LOG      = ("Consolas",  9)


class BowlingMachineGUI:
    """
    Main GUI class for the Voice-Controlled Bowling Machine.

    Parameters
    ----------
    machine  : BowlingMachine
    ctrl     : Controller
    vp       : VoiceProcessor
    tts      : TextToSpeech
    """

    def __init__(self, machine: BowlingMachine, ctrl: Controller,
                 vp: VoiceProcessor, tts: TextToSpeech):
        self._machine = machine
        self._ctrl    = ctrl
        self._vp      = vp
        self._tts     = tts
        self._listening = False

        # Thread-safe queue for sending log messages from worker threads
        self._log_queue: queue.Queue = queue.Queue()

        # ── Build window ───────────────────────────────────────────────────
        self._root = tk.Tk()
        self._root.title("🎳 Voice-Controlled Bowling Machine")
        self._root.configure(bg=CLR_BG)
        self._root.geometry("820x580")
        self._root.resizable(True, True)
        self._root.minsize(700, 500)

        self._build_ui()
        self._refresh_status()
        self._log("System ready. Click '🎙 Listen' or type a command below.")

        # Poll the log queue every 150 ms (thread-safe UI updates)
        self._root.after(150, self._poll_log_queue)

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        """Construct all widgets."""
        # Title bar
        title_frame = tk.Frame(self._root, bg=CLR_BG)
        title_frame.pack(fill="x", padx=16, pady=(14, 6))

        tk.Label(title_frame, text="🎳  Voice-Controlled Bowling Machine",
                 font=FONT_TITLE, bg=CLR_BG, fg=CLR_BLUE).pack(side="left")

        tk.Label(title_frame, text="Minor Project — Python",
                 font=FONT_LABEL, bg=CLR_BG, fg=CLR_MUTED).pack(side="right", anchor="s")

        # Separator
        tk.Frame(self._root, bg=CLR_BORDER, height=1).pack(fill="x", padx=16)

        # Main content area (status + log side by side)
        content = tk.Frame(self._root, bg=CLR_BG)
        content.pack(fill="both", expand=True, padx=16, pady=10)
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Status panel (left)
        self._build_status_panel(content)

        # Event log (right)
        self._build_log_panel(content)

        # Controls (bottom)
        self._build_controls()

    def _make_card(self, parent, col, row, title) -> tk.Frame:
        """Helper — create a titled card frame."""
        outer = tk.Frame(parent, bg=CLR_BORDER, bd=1, relief="flat")
        outer.grid(row=row, column=col, sticky="nsew",
                   padx=(0, 8) if col == 0 else (0, 0), pady=0)

        header = tk.Frame(outer, bg=CLR_PANEL)
        header.pack(fill="x")
        tk.Label(header, text=title, font=("Segoe UI", 9, "bold"),
                 bg=CLR_PANEL, fg=CLR_MUTED, pady=6, padx=10).pack(side="left")

        body = tk.Frame(outer, bg=CLR_PANEL)
        body.pack(fill="both", expand=True, padx=2, pady=2)
        return body

    def _build_status_panel(self, parent):
        """Left card — shows machine state."""
        card = self._make_card(parent, col=0, row=0, title="MACHINE STATUS")
        card.configure(width=220)

        # Each status row: label + value
        self._status_vars = {}

        rows = [
            ("STATE",     "STOPPED",   CLR_RED),
            ("SPEED",     "SLOW",      CLR_TEXT),
            ("DIRECTION", "STRAIGHT",  CLR_BLUE),
            ("SPIN",      "OFF",       CLR_RED),
            ("BALLS",     "0",         CLR_TEXT),
        ]

        for i, (key, initial, colour) in enumerate(rows):
            row_frame = tk.Frame(card, bg=CLR_PANEL)
            row_frame.pack(fill="x", padx=14, pady=6)

            tk.Label(row_frame, text=key, font=FONT_LABEL,
                     bg=CLR_PANEL, fg=CLR_MUTED, width=10, anchor="w").pack(side="left")

            var = tk.StringVar(value=initial)
            lbl = tk.Label(row_frame, textvariable=var, font=FONT_VALUE,
                           bg=CLR_PANEL, fg=colour, anchor="w")
            lbl.pack(side="left", padx=6)
            self._status_vars[key] = (var, lbl, colour)

        # Mic status indicator
        tk.Frame(card, bg=CLR_BORDER, height=1).pack(fill="x", padx=14, pady=(8, 4))
        mic_row = tk.Frame(card, bg=CLR_PANEL)
        mic_row.pack(fill="x", padx=14, pady=(0, 10))
        mic_ok = self._vp.is_mic_available() if self._vp.is_available else False
        mic_text = "🎙 Mic: READY" if mic_ok else "🎙 Mic: NOT FOUND"
        mic_col  = CLR_GREEN if mic_ok else CLR_AMBER
        tk.Label(mic_row, text=mic_text, font=FONT_LABEL,
                 bg=CLR_PANEL, fg=mic_col).pack(side="left")

        tts_ok   = self._tts.is_available
        tts_text = "🔊 TTS: ON" if tts_ok else "🔊 TTS: OFF"
        tts_col  = CLR_GREEN if tts_ok else CLR_MUTED
        tk.Label(mic_row, text=f"   {tts_text}", font=FONT_LABEL,
                 bg=CLR_PANEL, fg=tts_col).pack(side="left")

    def _build_log_panel(self, parent):
        """Right card — scrollable event log."""
        card = self._make_card(parent, col=1, row=0, title="EVENT LOG")

        self._log_widget = scrolledtext.ScrolledText(
            card,
            bg=CLR_LOG_BG, fg=CLR_TEXT, font=FONT_LOG,
            bd=0, relief="flat",
            wrap="word", state="disabled",
            insertbackground=CLR_BLUE,
        )
        self._log_widget.pack(fill="both", expand=True, padx=2, pady=2)

        # Colour tags for different log levels
        self._log_widget.tag_config("cmd",   foreground=CLR_BLUE)
        self._log_widget.tag_config("resp",  foreground=CLR_GREEN)
        self._log_widget.tag_config("error", foreground=CLR_RED)
        self._log_widget.tag_config("info",  foreground=CLR_MUTED)
        self._log_widget.tag_config("bowl",  foreground=CLR_PURPLE)

    def _build_controls(self):
        """Bottom bar — listen button + text input."""
        bar = tk.Frame(self._root, bg=CLR_PANEL, pady=10)
        bar.pack(fill="x", padx=16, pady=(0, 12))

        # Listen button
        self._listen_btn = tk.Button(
            bar, text="🎙  Listen", font=FONT_BUTTON,
            bg=CLR_BLUE, fg="#000000", activebackground="#1f6feb",
            relief="flat", padx=14, pady=6, cursor="hand2",
            command=self._on_listen_click,
        )
        self._listen_btn.pack(side="left", padx=(10, 8))

        # Text entry
        self._text_var = tk.StringVar()
        entry = tk.Entry(
            bar, textvariable=self._text_var,
            font=FONT_LABEL, bg=CLR_ENTRY_BG, fg=CLR_TEXT,
            insertbackground=CLR_BLUE, relief="flat",
            highlightthickness=1, highlightcolor=CLR_BLUE,
            highlightbackground=CLR_BORDER,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=5)
        entry.bind("<Return>", lambda e: self._on_text_send())

        # Send button
        tk.Button(
            bar, text="Send ▶", font=FONT_BUTTON,
            bg=CLR_GREEN, fg="#000000", activebackground="#2ea043",
            relief="flat", padx=12, pady=6, cursor="hand2",
            command=self._on_text_send,
        ).pack(side="left", padx=(0, 8))

        # Help button
        tk.Button(
            bar, text="❓ Commands", font=FONT_BUTTON,
            bg=CLR_PANEL, fg=CLR_MUTED,
            activebackground=CLR_BORDER,
            relief="flat", padx=10, pady=6, cursor="hand2",
            command=self._show_help,
        ).pack(side="left", padx=(0, 10))

    # ── Event Handlers ─────────────────────────────────────────────────────

    def _on_listen_click(self):
        """Handle the 🎙 Listen button — runs voice capture in a thread."""
        if self._listening:
            return
        if not self._vp.is_available:
            self._queue_log("❌ SpeechRecognition library not installed.", "error")
            return

        self._listening = True
        self._listen_btn.configure(text="⏳ Listening…", state="disabled", bg=CLR_AMBER)
        thread = threading.Thread(target=self._voice_listen_worker, daemon=True)
        thread.start()

    def _voice_listen_worker(self):
        """Background thread — captures voice and dispatches result."""
        self._queue_log("🎙 Listening for your command…", "info")
        text = self._vp.listen()

        if text:
            self._queue_log(f"🗣  Heard: '{text}'", "cmd")
            response = self._ctrl.handle(text)
            self._queue_log(f"➤  {response}", "resp" if "❓" not in response else "error")
            self._tts.speak(response)
        else:
            self._queue_log("⚠️  No speech recognised. Please try again.", "error")

        # Schedule UI updates back on main thread
        self._root.after(0, self._after_listen)

    def _after_listen(self):
        """Called on main thread after voice worker finishes."""
        self._listening = False
        self._listen_btn.configure(text="🎙  Listen", state="normal", bg=CLR_BLUE)
        self._refresh_status()

    def _on_text_send(self):
        """Handle typed command from the text entry widget."""
        text = self._text_var.get().strip()
        if not text:
            return
        self._text_var.set("")
        self._log(f"⌨️  Typed: '{text}'", "cmd")
        response = self._ctrl.handle(text)
        tag = "bowl" if "🎳" in response else ("resp" if "❓" not in response else "error")
        self._log(f"➤  {response}", tag)
        self._tts.speak(response)
        self._refresh_status()

    def _show_help(self):
        """Show a popup with all available commands."""
        cmds = self._ctrl.get_command_list()
        text = "Supported voice / text commands:\n\n" + "\n".join(f"  • {c}" for c in cmds)
        messagebox.showinfo("📋 Command Reference", text)

    # ── Status Refresh ─────────────────────────────────────────────────────

    def _refresh_status(self):
        """Read machine state and update all status labels."""
        s = self._machine.get_status()

        # STATE
        self._set_status("STATE",
                         "RUNNING" if s["running"] else "STOPPED",
                         CLR_GREEN if s["running"] else CLR_RED)

        # SPEED
        speed_colours = {"SLOW": CLR_TEXT, "MEDIUM": CLR_AMBER, "FAST": CLR_RED}
        self._set_status("SPEED", s["speed"], speed_colours.get(s["speed"], CLR_TEXT))

        # DIRECTION
        dir_colours = {"LEFT": CLR_PURPLE, "STRAIGHT": CLR_BLUE, "RIGHT": CLR_AMBER}
        self._set_status("DIRECTION", s["direction"],
                         dir_colours.get(s["direction"], CLR_BLUE))

        # SPIN
        self._set_status("SPIN",
                         "ON" if s["spin"] else "OFF",
                         CLR_GREEN if s["spin"] else CLR_RED)

        # BALLS
        self._set_status("BALLS", str(s["ball_count"]), CLR_TEXT)

    def _set_status(self, key: str, value: str, colour: str):
        """Update a single status row's text and colour."""
        if key in self._status_vars:
            var, lbl, _ = self._status_vars[key]
            var.set(value)
            lbl.configure(fg=colour)

    # ── Thread-safe logging ────────────────────────────────────────────────

    def _queue_log(self, message: str, tag: str = "info"):
        """Put a log entry on the queue (safe to call from any thread)."""
        self._log_queue.put((message, tag))

    def _poll_log_queue(self):
        """Drain the log queue on the main thread (called every 150 ms)."""
        while not self._log_queue.empty():
            msg, tag = self._log_queue.get_nowait()
            self._log(msg, tag)
        self._root.after(150, self._poll_log_queue)

    def _log(self, message: str, tag: str = "info"):
        """Append a timestamped line to the event log (main thread only)."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_widget.configure(state="normal")
        self._log_widget.insert("end", f"[{ts}] {message}\n", tag)
        self._log_widget.configure(state="disabled")
        self._log_widget.see("end")   # auto-scroll to bottom

    # ── Main loop ──────────────────────────────────────────────────────────

    def run(self):
        """Start the Tkinter main loop."""
        self._root.mainloop()
