"""
tts.py
------
TextToSpeech helper class using pyttsx3 (offline, no internet needed).

OOP Concept Used: Abstraction — the caller just calls speak() without
knowing anything about the underlying TTS engine.

The speech runs in a background thread so the GUI never freezes.
"""

import threading
import logging

# Attempt to import pyttsx3; degrade gracefully if not installed.
try:
    import pyttsx3
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    logging.warning("pyttsx3 not found. Text-to-speech will be disabled.")


class TextToSpeech:
    """
    Wraps pyttsx3 to provide simple text-to-speech.

    Usage
    -----
        tts = TextToSpeech()
        tts.speak("Machine started")
    """

    def __init__(self, rate: int = 160, volume: float = 0.9):
        """
        Initialise the TTS engine.

        Parameters
        ----------
        rate   : words per minute (default 160 — comfortable, clear pace)
        volume : 0.0 to 1.0 (default 0.9)
        """
        self._enabled = _TTS_AVAILABLE
        self._lock    = threading.Lock()   # prevent concurrent speech calls

        if self._enabled:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate",   rate)
                self._engine.setProperty("volume", volume)
            except Exception as e:
                logging.error(f"TTS init failed: {e}")
                self._enabled = False

    # ── Public API ─────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """
        Speak the given text in a daemon background thread.

        Parameters
        ----------
        text : The string to speak aloud.
        """
        if not self._enabled or not text:
            return
        # Run in a daemon thread — dies automatically when the app exits.
        thread = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
        thread.start()

    def _speak_sync(self, text: str) -> None:
        """Internal — runs pyttsx3 synchronously inside a worker thread."""
        with self._lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                logging.error(f"TTS speak error: {e}")

    @property
    def is_available(self) -> bool:
        """True if TTS is functional."""
        return self._enabled
