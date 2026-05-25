"""
main.py
-------
Entry point for the Voice-Controlled Cricket Bowling Machine Simulation.

Wires together:
    BowlingMachine  ← Controller ← VoiceProcessor
                              ← TextToSpeech
                    ← PygameGame  (Pygame simulation window)

Run:
    python main.py

Controls:
    ← →   Move bat
    SPACE  Manual bowl
    Q/ESC  Quit
    Voice  Say: start | stop | fast | slow | bouncer |
               yorker | spin | left swing | right swing
"""

import logging
from machine         import BowlingMachine
from controller      import Controller
from voice_processor import VoiceProcessor
from tts             import TextToSpeech
from pygame_game     import PygameGame

# Configure logging for all modules
logging.basicConfig(
    level  = logging.INFO,
    format = "[%(levelname)s] %(name)s — %(message)s"
)


def main():
    print("=" * 60)
    print("  🏏  Voice-Controlled Cricket Bowling Machine")
    print("       Pygame Simulation — Minor Project")
    print("=" * 60)
    print()
    print("  Controls:")
    print("    ← →   Move bat left / right")
    print("    SPACE  Bowl manually")
    print("    Q/ESC  Quit")
    print()
    print("  Voice Commands (say aloud):")
    print("    start  stop  fast  slow  bouncer  yorker")
    print("    spin   left swing   right swing   reset")
    print("=" * 60)
    print()

    # ── Instantiate components ─────────────────────────────────────────────
    machine = BowlingMachine()           # hardware state
    ctrl    = Controller(machine)        # command dispatcher
    vp      = VoiceProcessor(            # speech → text (Google API)
                timeout     = 5,
                phrase_limit = 6,
                language    = "en-IN"
              )
    tts     = TextToSpeech(              # text → speech (pyttsx3, offline)
                rate   = 155,
                volume = 0.9
              )

    # ── Launch Pygame simulation ───────────────────────────────────────────
    game = PygameGame(machine, ctrl, vp, tts)
    tts.speak("Cricket Bowling Machine ready. Move bat with arrow keys.")
    game.run()   # blocks until window is closed

    print("\nSimulation ended. Goodbye! 🏏")


if __name__ == "__main__":
    main()
