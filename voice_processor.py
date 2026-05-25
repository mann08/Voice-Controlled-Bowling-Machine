"""
voice_processor.py
------------------
VoiceProcessor class — captures microphone audio and converts it to text
using the SpeechRecognition library backed by Google's free Web Speech API.

OOP Concept Used: Single Responsibility Principle — this class ONLY handles
voice capture and transcription; it does NOT interpret the command.

Internet connection is required for the Google recogniser.
Fallback: if the mic is unavailable or recognition fails, returns None
so the caller can handle the error gracefully.
"""

import logging

# Attempt to import speech_recognition; degrade gracefully if missing.
try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False
    logging.warning("SpeechRecognition not installed. Voice input disabled.")


class VoiceProcessor:
    """
    Listens to the microphone and returns the recognised text.

    Usage
    -----
        vp = VoiceProcessor()
        text = vp.listen()     # blocks until speech detected or timeout
        if text:
            print(text)
    """

    def __init__(self, timeout: int = 5, phrase_limit: int = 6,
                 language: str = "en-IN"):
        """
        Parameters
        ----------
        timeout      : seconds to wait for speech to start (default 5)
        phrase_limit : max seconds to record a single phrase (default 6)
        language     : BCP-47 language tag (default en-IN for Indian accent)
        """
        self._enabled      = _SR_AVAILABLE
        self._timeout      = timeout
        self._phrase_limit = phrase_limit
        self._language     = language

        if self._enabled:
            self._recogniser = sr.Recognizer()
            # Reduce ambient-noise sensitivity — good for indoor use
            self._recogniser.dynamic_energy_threshold = True
            self._recogniser.pause_threshold = 0.8   # short pause = end of phrase

    # ── Public API ─────────────────────────────────────────────────────────

    def listen(self) -> str | None:
        """
        Open the microphone, wait for a voice phrase, and return its text.

        Returns
        -------
        str  : recognised text (lowercase, stripped)
        None : if mic unavailable, no speech detected, or recognition failed
        """
        if not self._enabled:
            return None

        try:
            with sr.Microphone() as source:
                # Calibrate for ambient noise (~0.5 s)
                self._recogniser.adjust_for_ambient_noise(source, duration=0.5)

                logging.info("🎙 Listening…")
                audio = self._recogniser.listen(
                    source,
                    timeout      = self._timeout,
                    phrase_time_limit = self._phrase_limit
                )

            # Send audio to Google for recognition
            text = self._recogniser.recognize_google(audio, language=self._language)
            return text.lower().strip()

        except sr.WaitTimeoutError:
            logging.warning("No speech detected within timeout.")
            return None
        except sr.UnknownValueError:
            logging.warning("Speech not understood.")
            return None
        except sr.RequestError as e:
            logging.error(f"Google Speech API error: {e}")
            return None
        except OSError as e:
            # Microphone not found / permission denied
            logging.error(f"Microphone error: {e}")
            return None

    # ── Mic availability check ─────────────────────────────────────────────

    def is_mic_available(self) -> bool:
        """Check whether a microphone device is accessible."""
        if not self._enabled:
            return False
        try:
            mic_names = sr.Microphone.list_microphone_names()
            return len(mic_names) > 0
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """True if the SpeechRecognition library is installed."""
        return self._enabled
