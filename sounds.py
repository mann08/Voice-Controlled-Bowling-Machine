"""
sounds.py
---------
SoundManager — synthesises and plays game sound effects using pygame.mixer.

No external audio files required — all sounds are generated programmatically
using numpy-based waveforms so the project is fully self-contained.

OOP Concept: Abstraction — callers just say play("hit"); internal synthesis
             is completely hidden.

Graceful degradation: if mixer fails to init (e.g., no audio device),
all play() calls are silently no-ops.
"""

import logging
import math
import threading

# Pygame mixer imported lazily so the module imports cleanly without pygame
_MIXER_OK = False

try:
    import pygame
    import pygame.sndarray
    import numpy as np
    _MIXER_OK = True
except ImportError:
    logging.warning("pygame / numpy not found — sound disabled.")


# ── Synth helpers ──────────────────────────────────────────────────────────

def _make_tone(freq: float, duration: float, volume: float = 0.4,
               sample_rate: int = 22050, wave: str = "sine") -> "pygame.mixer.Sound":
    """
    Generate a mono sound buffer at the given frequency.

    Parameters
    ----------
    freq        : Hz
    duration    : seconds
    volume      : 0.0 – 1.0
    wave        : 'sine' | 'square' | 'sawtooth'
    """
    n = int(sample_rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    if wave == "square":
        samples = np.sign(np.sin(2 * math.pi * freq * t))
    elif wave == "sawtooth":
        samples = 2 * (t * freq - np.floor(0.5 + t * freq))
    else:  # default sine
        samples = np.sin(2 * math.pi * freq * t)

    # Apply simple exponential decay envelope
    decay = np.exp(-3.0 * t / duration)
    samples = (samples * decay * volume * 32767).astype(np.int16)

    # Make stereo
    stereo = np.column_stack([samples, samples])
    return pygame.sndarray.make_sound(stereo)


def _make_noise(duration: float, volume: float = 0.3,
                sample_rate: int = 22050) -> "pygame.mixer.Sound":
    """Generate white-noise burst (used for miss / whoosh effects)."""
    n = int(sample_rate * duration)
    noise = np.random.randint(-32768, 32767, n, dtype=np.int16)
    t     = np.linspace(0, duration, n, endpoint=False)
    decay = np.exp(-6.0 * t / duration)
    noise = (noise * decay * volume).astype(np.int16)
    stereo = np.column_stack([noise, noise])
    return pygame.sndarray.make_sound(stereo)


def _make_chord(freqs, duration: float, volume: float = 0.35,
                sample_rate: int = 22050) -> "pygame.mixer.Sound":
    """Mix several sine tones together."""
    n = int(sample_rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    combined = sum(np.sin(2 * math.pi * f * t) for f in freqs)
    combined /= len(freqs)
    decay   = np.exp(-2.5 * t / duration)
    out     = (combined * decay * volume * 32767).astype(np.int16)
    stereo  = np.column_stack([out, out])
    return pygame.sndarray.make_sound(stereo)


# ── Main Class ─────────────────────────────────────────────────────────────

class SoundManager:
    """
    Generates and caches all game sound effects.

    Sounds
    ------
    hit     : satisfying 'crack' of bat on ball
    miss    : soft whoosh
    bowl    : mechanical click / whirr
    six     : triumphant chord
    start   : rising beep
    stop    : falling beep
    """

    def __init__(self):
        self._enabled = False
        self._sounds: dict = {}

        if not _MIXER_OK:
            return

        try:
            # Only init mixer if not already done by pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._build_sounds()
            self._enabled = True
            logging.info("SoundManager: all sounds synthesised OK.")
        except Exception as e:
            logging.warning(f"SoundManager init failed: {e}")

    def _build_sounds(self) -> None:
        """Pre-build all synthesised sounds once at startup."""
        # Hit — sharp crack (high freq burst)
        self._sounds["hit"]   = _make_chord([440, 660, 880], 0.25, volume=0.5)
        # Six — triumphant major chord
        self._sounds["six"]   = _make_chord([261, 329, 392, 523], 0.7, volume=0.5)
        # Miss — quiet whoosh
        self._sounds["miss"]  = _make_noise(0.3, volume=0.2)
        # Bowl — mechanical click
        self._sounds["bowl"]  = _make_tone(200, 0.15, volume=0.3, wave="square")
        # Start — rising two-tone
        self._sounds["start"] = _make_chord([220, 440], 0.4, volume=0.4)
        # Stop — falling tone
        self._sounds["stop"]  = _make_tone(150, 0.35, volume=0.3)
        # Type change — quick high beep
        self._sounds["type"]  = _make_tone(880, 0.1, volume=0.25)

    def play(self, name: str) -> None:
        """
        Play a named sound effect in a daemon thread (non-blocking).

        Parameters
        ----------
        name : one of: hit, six, miss, bowl, start, stop, type
        """
        if not self._enabled:
            return
        sound = self._sounds.get(name)
        if sound:
            threading.Thread(target=sound.play, daemon=True).start()

    @property
    def is_available(self) -> bool:
        return self._enabled
