# 🏏 Voice-Controlled Cricket Bowling Machine

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Pygame](https://img.shields.io/badge/Pygame-2.5.2-brightgreen?logo=pygame)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Complete-success)

**A real-time, voice-controlled cricket simulation built with Pygame, OOP, and AI Speech Recognition.**

*Control the bowling machine using your voice — change ball type, speed, and difficulty mid-game!*

</div>

---

## 🎮 Demo Features

| Feature | Details |
|---|---|
| 🎙 **Voice Control** | Google Speech API — say commands hands-free |
| ⚾ **8 Ball Types** | Normal, Fast, Slow, Bouncer, Yorker, Spin, Left/Right Swing |
| 🎯 **3 Difficulty Levels** | Easy / Medium / Hard (affects ball speed multiplier) |
| ✨ **Particle Effects** | Hit sparks (burst of 50 particles), ball trails, miss flash |
| 📊 **Live Stats** | Score, Balls, Overs, Run Rate, Strike Rate, High Score |
| 🏆 **Persistent High Score** | Saved automatically to `stats.json` |
| 🖥 **Animated Menu** | Splash screen with drop-in title and animated cricket balls |
| 🎵 **Sound Effects** | Synthesised crack, whoosh, six-chord — no audio files needed |
| 🔄 **Game States** | MENU → PLAYING → GAME OVER flow |

---

## 🗂 Project Structure

```
minor project/
│
├── main.py              → Entry point (run this)
├── machine.py           → BowlingMachine class — hardware state engine
├── controller.py        → Controller — maps voice text → machine actions
├── voice_processor.py   → VoiceProcessor — mic → Google Speech → text
├── tts.py               → TextToSpeech — pyttsx3 offline voice feedback
├── physics.py           → Ball — gravity, bounce, swing, spin physics
├── pygame_game.py       → PygameGame — main simulation (rendering, HUD, particles)
├── stats.py             → SessionStats — live stats + JSON persistence
├── sounds.py            → SoundManager — synthesised sound effects via numpy
├── requirements.txt     → Python package dependencies
└── README.md            → This file
```

---

## 🧠 Architecture

```
 ┌─────────────────────────────────────────────────────────────┐
 │                        main.py                              │
 │   Instantiates all components and passes them to PygameGame │
 └──────────────────────────┬──────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────────┐
         ▼                  ▼                      ▼
  VoiceProcessor       TextToSpeech          BowlingMachine
  (mic → text)         (pyttsx3 TTS)         (state engine)
         │                                        ▲
         ▼                                        │
    Controller ──── maps text command ────────────┘
                     (dict dispatch)
         │
         ▼
    PygameGame  ←——  Ball (physics.py)
                ←——  SessionStats (stats.py)
                ←——  SoundManager (sounds.py)
```

---

## 🧱 OOP Design

| Class | File | OOP Concept |
|---|---|---|
| `BowlingMachine` | `machine.py` | **Encapsulation** — all state private, accessed via methods |
| `Controller` | `controller.py` | **Command Pattern** — dict dispatch avoids if/elif chains |
| `VoiceProcessor` | `voice_processor.py` | **SRP** — only handles speech capture, nothing else |
| `TextToSpeech` | `tts.py` | **Abstraction** — caller just calls `speak()` |
| `Ball` | `physics.py` | **Encapsulation** — position/velocity hidden, updated via `update()` |
| `PygameGame` | `pygame_game.py` | **Composition** — owns all sub-systems |
| `SessionStats` | `stats.py` | **Encapsulation + Persistence** — wraps JSON I/O |
| `SoundManager` | `sounds.py` | **Abstraction** — synthesises sounds internally |
| `Particle` / `TrailDot` | `pygame_game.py` | **SRP** — each particle manages its own lifecycle |

---

## 🎙 Voice Commands

| Command | Effect |
|---|---|
| `start` | Start the bowling machine |
| `stop` / `pause` / `halt` | Stop the machine |
| `reset` / `restart` | Reset to defaults |
| `fast` | Fast ball (high vx, flat) |
| `slow` | Slow looping arc |
| `bouncer` | Ball launches upward, bounces high |
| `yorker` | Near-ground, very fast |
| `spin` | Sinusoidal lateral drift |
| `left swing` | Constant leftward curve |
| `right swing` | Constant rightward curve |
| `normal` / `medium` | Default delivery |
| `easy` | Reduce ball speed 35% |
| `hard` | Increase ball speed 45% |
| `bowl` / `throw` / `fire` | Manually bowl one ball |
| `increase speed` / `faster` | Raise speed level |
| `decrease speed` / `slower` | Lower speed level |
| `left` / `right` / `straight` | Set direction |
| `spin on` / `spin off` | Toggle spin flag |
| `status` | Read machine status aloud |

> 💡 Fuzzy matching — partial phrases like *"please bowl a bouncer"* still trigger `bouncer`.

---

## 🕹 Keyboard Controls

| Key | Action |
|---|---|
| `← →` | Move bat up / down on pitch |
| `SPACE` | Manual bowl (machine must be running) |
| `ENTER` | Start game (from menu) / Restart (from game-over) |
| `Q` / `ESC` | Quit |

---

## 💻 Installation & Setup

### Prerequisites
- Python 3.10+ — [python.org](https://www.python.org/downloads/)
- Working microphone (optional — keyboard/SPACE works too)
- Internet for Google Speech API (offline fallback: type commands)

### 1 — Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ **Windows PyAudio fix** — if pyaudio fails:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

### 2 — Run

```bash
python main.py
```

---

## 🖼 Game Screens

```
╔══ MENU SCREEN ══════════════════════════════════════════════╗
║   🏏 CRICKET BOWLING MACHINE                                ║
║   Voice-Controlled Simulation                               ║
║                                                             ║
║   [⚾ 8 Types] [🎙 Voice] [🏆 Score] [📊 Stats] [✨ FX]    ║
║                                                             ║
║   ▶  Press ENTER or say 'start'  ◀                         ║
╚═════════════════════════════════════════════════════════════╝

╔══ PLAYING ══════════════════════════════════════════════════╗
║ HUD: ⚾ BOUNCER  ⚡ FAST  🎯 HARD  ● RUNNING  🎙 Listening ║
║                                                             ║
║ [MACHINE]══════════════ PITCH ══════════[BAT][BATSMAN]     ║
║             ••• (ball trail) ●→                             ║
║                                                             ║
║ Stats: 🏆12  🏏8  📅1.2  📈6.0  💥150%  🌟20              ║
╚═════════════════════════════════════════════════════════════╝
```

---

## ⚙️ How the Physics Works

| Ball Type | vx | vy (launch) | Effect |
|---|---|---|---|
| NORMAL | 9.0 | −2.0 | Gentle medium arc |
| FAST | 14.0 | −1.5 | Flat, rapid delivery |
| SLOW | 5.5 | −5.0 | High looping arc |
| BOUNCER | 9.0 | −11.0 | Launches upward, drops after bounce |
| YORKER | 13.0 | −0.5 | Near-ground skimmer |
| SPIN | 6.0 | −3.0 | Sinusoidal lateral drift |
| LEFT SWING | 8.5 | −2.5 | Constant leftward curve in flight |
| RIGHT SWING | 8.5 | −2.5 | Constant rightward curve |

Difficulty multiplier applied to `vx`: Easy ×0.65 · Medium ×1.0 · Hard ×1.45

---

## ⚠️ Troubleshooting

| Problem | Fix |
|---|---|
| `pyaudio` install fails | Use `pipwin install pyaudio` on Windows |
| "No speech recognised" | Speak clearly; check mic in Windows Sound settings |
| "Google API error" | Check internet connection |
| TTS not speaking | `pip install pyttsx3` |
| No sound effects | `pip install numpy` |
| App crashes on start | Ensure Python ≥ 3.10, then `pip install -r requirements.txt` |

---

## 🎓 Academic Value

This project demonstrates:
- ✅ **Object-Oriented Programming** — Encapsulation, Abstraction, Composition, SRP, Command Pattern
- ✅ **Real-time Game Loop** — 60 FPS Pygame event loop with delta-time awareness
- ✅ **Multi-threading** — voice capture thread does not block the render thread
- ✅ **Physics Simulation** — gravity, damped bouncing, sinusoidal drift
- ✅ **Data Persistence** — JSON-based session stats with auto-save
- ✅ **API Integration** — Google Speech Recognition Web API
- ✅ **Procedural Audio Synthesis** — numpy-generated waveforms (no audio files)
- ✅ **Particle Systems** — geometry-based hit spark and trail effects
- ✅ **State Machine** — MENU → PLAYING → GAME_OVER transitions

---

## 📄 License

MIT License — free to use for educational purposes.

---

*🏏 Voice-Controlled Cricket Bowling Machine — Minor Project, Python | OOP | Pygame*
