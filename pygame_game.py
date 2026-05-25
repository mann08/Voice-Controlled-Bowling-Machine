"""
pygame_game.py
--------------
PygameGame — the main Pygame cricket bowling machine simulation.

Layout (1100 × 650 window):
  ┌────────────────────────────────────────────────────────────┐
  │  HUD: Ball Type | Speed | Difficulty | Score | Mic Status  │
  │                                                            │
  │  [Machine]  ══════════ PITCH ══════════ [Bat] [Batsman]   │
  │                                                            │
  │  Stats: Balls | Overs | Run Rate | Strike Rate | Hi-Score  │
  └────────────────────────────────────────────────────────────┘

States: MENU → PLAYING → GAME_OVER

Controls:
  ← →    Move bat up / down (in screen-y dimension)
  SPACE  Manual bowl (if machine running)
  ENTER  Start game from menu / restart from game-over
  Q/ESC  Quit

Voice Commands:
  start, stop, fast, slow, bouncer, yorker, spin,
  left swing, right swing, reset, easy, medium, hard
"""

import pygame
import sys
import math
import threading
import queue
import time
import random

# ── Import project modules ─────────────────────────────────────────────────
from machine         import BowlingMachine
from controller      import Controller
from voice_processor import VoiceProcessor
from tts             import TextToSpeech
from physics         import Ball
from stats           import SessionStats
from sounds          import SoundManager


# ── Window & FPS ───────────────────────────────────────────────────────────
W, H  = 1100, 650
FPS   = 60

# ── Pitch geometry ─────────────────────────────────────────────────────────
PITCH_TOP    = 310
PITCH_BOTTOM = 440
PITCH_Y      = PITCH_BOTTOM - 12   # ball bounce level

# ── Machine nozzle ─────────────────────────────────────────────────────────
MACHINE_X    = 80
MACHINE_Y    = PITCH_Y - 40

# ── Bat geometry ───────────────────────────────────────────────────────────
CREASE_X     = 940
BAT_Y_DEFAULT = PITCH_Y - 45
BAT_W, BAT_H = 14, 90
BAT_X       = CREASE_X + 2
BAT_STEP     = 8
BAT_MIN_Y    = PITCH_TOP + 10
BAT_MAX_Y    = PITCH_BOTTOM - BAT_H - 10

# ── Difficulty speed multipliers ───────────────────────────────────────────
DIFFICULTY_MULT = {"EASY": 0.65, "MEDIUM": 1.0, "HARD": 1.45}
DIFFICULTY_COLOURS = {
    "EASY":   (50, 220, 80),
    "MEDIUM": (255, 215, 0),
    "HARD":   (255, 60, 60),
}

# ── Colour palette ─────────────────────────────────────────────────────────
C_SKY_TOP    = (12, 28, 60)
C_SKY_BOT    = (40, 80, 160)
C_PITCH      = (194, 178, 128)
C_PITCH_LINE = (240, 230, 200)
C_GRASS_DARK = (18, 105, 18)
C_GRASS_LITE = (25, 135, 25)
C_BALL       = (200, 30, 30)
C_BALL_SEAM  = (180, 160, 130)
C_BAT        = (210, 180, 80)
C_BAT_HANDLE = (120, 80, 40)
C_WHITE      = (255, 255, 255)
C_YELLOW     = (255, 215, 0)
C_GREEN      = (50, 220, 80)
C_RED        = (255, 60, 60)
C_CYAN       = (60, 200, 255)
C_ORANGE     = (255, 160, 30)
C_PURPLE     = (180, 80, 255)
C_TEXT       = (220, 220, 220)
C_MUTED      = (140, 140, 160)
C_DARK       = (8, 12, 22)
C_PANEL      = (15, 22, 45, 210)

TYPE_COLOURS = {
    "NORMAL":      C_WHITE,
    "FAST":        C_RED,
    "SLOW":        C_GREEN,
    "BOUNCER":     C_ORANGE,
    "YORKER":      C_YELLOW,
    "SPIN":        C_PURPLE,
    "LEFT_SWING":  C_CYAN,
    "RIGHT_SWING": C_CYAN,
}

# ── Game states ────────────────────────────────────────────────────────────
STATE_MENU    = "MENU"
STATE_PLAYING = "PLAYING"
STATE_OVER    = "GAME_OVER"


# ══════════════════════════════════════════════════════════════════════════════
# Particle system
# ══════════════════════════════════════════════════════════════════════════════

class Particle:
    """A single short-lived coloured dot."""
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "colour", "radius")

    def __init__(self, x, y, colour, speed=4.0, radius=4):
        angle      = random.uniform(0, 2 * math.pi)
        spd        = random.uniform(speed * 0.4, speed)
        self.x     = float(x)
        self.y     = float(y)
        self.vx    = math.cos(angle) * spd
        self.vy    = math.sin(angle) * spd
        self.life  = random.randint(18, 35)
        self.max_life = self.life
        self.colour   = colour
        self.radius   = radius

    def update(self) -> bool:
        """Advance particle. Returns False when dead."""
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.25          # gravity
        self.vx *= 0.92          # air drag
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        alpha  = int(255 * (self.life / self.max_life))
        r      = max(1, int(self.radius * self.life / self.max_life))
        pygame.draw.circle(surf, self.colour, (int(self.x), int(self.y)), r)


class TrailDot:
    """Fading trail dot left behind the ball."""
    __slots__ = ("x", "y", "life", "max_life", "radius")

    def __init__(self, x, y):
        self.x        = x
        self.y        = y
        self.life     = 14
        self.max_life = 14
        self.radius   = 7

    def update(self) -> bool:
        self.life -= 1
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        alpha = int(180 * self.life / self.max_life)
        r     = max(1, int(self.radius * self.life / self.max_life))
        col   = (200, 30, 30)
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), r)


# ══════════════════════════════════════════════════════════════════════════════
# Main Game Class
# ══════════════════════════════════════════════════════════════════════════════

class PygameGame:
    """
    Full Pygame cricket bowling machine simulation.

    Parameters
    ----------
    machine  : BowlingMachine
    ctrl     : Controller
    vp       : VoiceProcessor
    tts      : TextToSpeech
    """

    def __init__(self, machine: BowlingMachine, ctrl: Controller,
                 vp: VoiceProcessor, tts: TextToSpeech):
        self._machine    = machine
        self._ctrl       = ctrl
        self._vp         = vp
        self._tts        = tts

        # Sub-systems
        self._stats  = SessionStats()
        self._sounds = SoundManager()

        # Voice queue
        self._cmd_queue: queue.Queue = queue.Queue()
        self._listening  = False

        # Game state machine
        self._state = STATE_MENU

        # Session
        self._score          = 0
        self._wickets        = 0           # wickets lost
        self._difficulty     = "MEDIUM"
        self._feedback_msg   = ""
        self._feedback_timer = 0
        self._last_cmd_text  = ""
        self._bat_y          = BAT_Y_DEFAULT
        self._bowl_timer     = 0
        self._bowl_interval  = FPS * 2      # auto-bowl every 2 s
        self._mic_status     = "READY" if vp.is_available else "N/A"
        self._message_log    = []
        self._miss_flash     = 0            # frames of red miss flash

        # Wicket/stump state
        self._stumps_fallen    = False
        self._stump_pieces     = []         # list of falling stump rects
        self._wicket_flash     = 0          # frames for WICKET! banner

        # Cloud positions (static seed, scrolled slightly over time)
        self._clouds = [
            {"x": 120, "y": 75, "w": 180, "h": 40, "spd": 0.12},
            {"x": 380, "y": 58, "w": 240, "h": 50, "spd": 0.08},
            {"x": 650, "y": 80, "w": 160, "h": 36, "spd": 0.15},
            {"x": 870, "y": 65, "w": 200, "h": 44, "spd": 0.10},
        ]

        # Particles
        self._particles: list[Particle] = []
        self._trail:     list[TrailDot] = []

        # Menu animation
        self._menu_angle  = 0.0            # spinning ball angle on menu
        self._menu_title_y = -80           # title drops in on startup
        self._wheel_angle  = 0.0           # spinning machine wheel angle

        # Countdown bar (0 → 1)
        self._countdown_frac = 0.0

        # Pygame init
        pygame.init()
        self._screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("🏏 Voice-Controlled Cricket Bowling Machine")
        self._clock  = pygame.time.Clock()

        # Fonts
        self._font_title  = pygame.font.SysFont("segoeui", 52, bold=True)
        self._font_big    = pygame.font.SysFont("segoeui", 34, bold=True)
        self._font_med    = pygame.font.SysFont("segoeui", 22, bold=True)
        self._font_small  = pygame.font.SysFont("segoeui", 16)
        self._font_tiny   = pygame.font.SysFont("consolas", 14)
        self._font_hud    = pygame.font.SysFont("segoeui", 18, bold=True)
        self._font_stat   = pygame.font.SysFont("segoeui", 15, bold=True)
        self._font_sub    = pygame.font.SysFont("segoeui", 20, bold=True)

        # Pre-render sky gradient (expensive per-frame avoided)
        self._bg_surf = self._make_gradient(W, H, C_SKY_TOP, C_SKY_BOT)

        # Physics ball
        self._ball = Ball(
            start_x  = MACHINE_X + 30,
            start_y  = MACHINE_Y,
            pitch_y  = PITCH_Y,
            screen_w = W,
        )

        # Start voice daemon
        self._start_voice_thread()

    # ════════════════════════════════════════════════════════════════════════
    # Main Loop
    # ════════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Start and maintain the game loop at FPS."""
        while True:
            self._clock.tick(FPS)
            self._handle_events()
            self._process_voice_queue()

            if self._state == STATE_MENU:
                self._update_menu()
                self._draw_menu()
            elif self._state == STATE_PLAYING:
                self._update_game()
                self._draw_game()
            elif self._state == STATE_OVER:
                self._draw_game_over()

            pygame.display.flip()

    # ════════════════════════════════════════════════════════════════════════
    # Event Handling
    # ════════════════════════════════════════════════════════════════════════

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()

            if event.type == pygame.KEYDOWN:
                k = event.key

                if k in (pygame.K_q, pygame.K_ESCAPE):
                    self._quit()

                # ENTER — start or restart
                if k == pygame.K_RETURN:
                    if self._state == STATE_MENU:
                        self._start_game()
                    elif self._state == STATE_OVER:
                        self._restart_game()

                if self._state == STATE_PLAYING:
                    if k == pygame.K_LEFT:
                        self._bat_y = max(BAT_MIN_Y, self._bat_y - BAT_STEP)
                    if k == pygame.K_RIGHT:
                        self._bat_y = min(BAT_MAX_Y, self._bat_y + BAT_STEP)
                    if k == pygame.K_SPACE:
                        if self._machine.get_status()["running"]:
                            self._bowl_ball()

    def _quit(self) -> None:
        self._stats.record_game_end()
        pygame.quit()
        sys.exit(0)

    # ════════════════════════════════════════════════════════════════════════
    # State Transitions
    # ════════════════════════════════════════════════════════════════════════

    def _start_game(self) -> None:
        self._state          = STATE_PLAYING
        self._score          = 0
        self._wickets        = 0
        self._bat_y          = BAT_Y_DEFAULT
        self._stats          = SessionStats()
        self._particles      = []
        self._trail          = []
        self._message_log    = []
        self._stumps_fallen  = False
        self._stump_pieces   = []
        self._wicket_flash   = 0
        self._machine.start()
        self._sounds.play("start")
        self._tts.speak("Game started. Bowl with voice or space bar.")
        self._bowl_ball()

    def _restart_game(self) -> None:
        self._machine.reset()
        self._start_game()

    def _end_game(self) -> None:
        self._state = STATE_OVER
        self._stats.record_game_end()
        self._machine.stop()
        self._sounds.play("stop")
        self._tts.speak(f"Great game! You scored {self._score} runs.")

    # ════════════════════════════════════════════════════════════════════════
    # Voice Processing
    # ════════════════════════════════════════════════════════════════════════

    def _start_voice_thread(self) -> None:
        t = threading.Thread(target=self._voice_loop, daemon=True)
        t.start()

    def _voice_loop(self) -> None:
        while True:
            if not self._vp.is_available:
                time.sleep(2)
                continue
            self._listening = True
            text = self._vp.listen()
            self._listening = False
            if text:
                self._cmd_queue.put(text)
            time.sleep(0.05)

    def _process_voice_queue(self) -> None:
        while not self._cmd_queue.empty():
            cmd = self._cmd_queue.get_nowait()
            self._last_cmd_text = f'"{cmd}"'

            # Difficulty commands handled here before controller
            lower = cmd.lower().strip()
            if lower in ("easy", "medium", "hard"):
                self._difficulty = lower.upper()
                resp = f"Difficulty set to {self._difficulty}."
                self._show_feedback(resp, 90)
                self._tts.speak(resp)
                self._sounds.play("type")
                self._log_event(f"🎙 {cmd} → {resp}")
                continue

            # Start/Stop from menu too
            if self._state == STATE_MENU and lower == "start":
                self._start_game()
                continue

            response = self._ctrl.handle(cmd)
            self._show_feedback(response, 90)
            self._tts.speak(response)
            self._sounds.play("type")
            self._log_event(f"🎙 {cmd} → {response}")

            # If ball type changed, re-bowl immediately
            if not self._ball.alive and self._state == STATE_PLAYING:
                self._bowl_ball()

    # ════════════════════════════════════════════════════════════════════════
    # Menu Update
    # ════════════════════════════════════════════════════════════════════════

    def _update_menu(self) -> None:
        self._menu_angle     += 2.0
        self._menu_title_y    = min(60, self._menu_title_y + 3)   # drop-in
        self._wheel_angle    += 3.0

    # ════════════════════════════════════════════════════════════════════════
    # Game Update
    # ════════════════════════════════════════════════════════════════════════

    def _update_game(self) -> None:
        status = self._machine.get_status()

        # Countdown bar fraction
        if not self._ball.alive and status["running"]:
            self._countdown_frac = min(1.0, self._bowl_timer / self._bowl_interval)
        else:
            self._countdown_frac = 0.0

        # Ball physics
        if self._ball.alive:
            self._trail.append(TrailDot(*self._ball.draw_pos))
            self._ball.update()
            self._check_hit()
            self._check_miss()
            self._check_wicket()

        # Particles
        self._particles = [p for p in self._particles if p.update()]
        self._trail     = [t for t in self._trail     if t.update()]

        # Stump physics (stumps fall outwards)
        for sp in self._stump_pieces:
            sp["x"] += sp["vx"]
            sp["y"] += sp["vy"]
            sp["vy"] += 0.5   # gravity on stump
            sp["angle"] += sp["angv"]
            sp["life"]  -= 1
        self._stump_pieces = [s for s in self._stump_pieces if s["life"] > 0]

        # Auto-bowl
        if not self._ball.alive and status["running"]:
            self._bowl_timer += 1
            if self._bowl_timer >= self._bowl_interval:
                self._stumps_fallen = False     # reset stumps for next ball
                self._bowl_ball()

        # Timers
        if self._feedback_timer > 0:
            self._feedback_timer -= 1
        if self._miss_flash > 0:
            self._miss_flash -= 1
        if self._wicket_flash > 0:
            self._wicket_flash -= 1

        # Scrolling clouds
        for cloud in self._clouds:
            cloud["x"] += cloud["spd"]
            if cloud["x"] > W + 100:
                cloud["x"] = -cloud["w"] - 20

        # Spinning machine wheels
        self._wheel_angle += 4.0 if status["running"] else 0.5

    # ════════════════════════════════════════════════════════════════════════
    # Game Logic
    # ════════════════════════════════════════════════════════════════════════

    def _bowl_ball(self) -> None:
        status    = self._machine.get_status()
        ball_type = status["ball_type"]
        self._ball.reset(ball_type=ball_type)

        # Apply difficulty multiplier to horizontal speed
        mult          = DIFFICULTY_MULT.get(self._difficulty, 1.0)
        self._ball.vx = self._ball.vx * mult

        self._bowl_timer = 0
        self._machine.bowl()
        self._sounds.play("bowl")

    def _check_hit(self) -> None:
        bat_rect = pygame.Rect(
            BAT_X,
            self._bat_y,
            BAT_W, BAT_H
        )
        bx, by = self._ball.draw_pos
        by_disp = by + int(self._ball.lateral_offset)
        ball_rect = pygame.Rect(
            bx - self._ball.radius,
            by_disp - self._ball.radius,
            self._ball.radius * 2,
            self._ball.radius * 2,
        )

        if bat_rect.colliderect(ball_rect):
            # Determine runs based on height of hit and difficulty
            runs = random.choice([1, 1, 2, 4, 4, 6])

            self._score += runs
            self._stats.record_hit(runs)
            self._ball.alive = False

            # Choose feedback message
            if runs == 6:
                msg = "SIX! 🌟 Magnificent!"
                self._sounds.play("six")
            elif runs == 4:
                msg = "FOUR! 💥 Great shot!"
                self._sounds.play("hit")
            else:
                msgs = ["Nice shot! 🏏", "Well played! 👏", "Good hit! ✅"]
                msg  = random.choice(msgs)
                self._sounds.play("hit")

            self._show_feedback(msg, 130)
            self._tts.speak(msg)
            self._log_event(f"✅ HIT! +{runs}  Total: {self._score}")

            # Spark particles at bat contact point
            cx = BAT_X + BAT_W // 2
            cy = self._bat_y + BAT_H // 2
            self._spawn_sparks(cx, cy, count=35, colour=C_YELLOW)
            self._spawn_sparks(cx, cy, count=15, colour=C_ORANGE)

    def _check_miss(self) -> None:
        """Called when ball is past bat x and hasn't been hit."""
        bx, _ = self._ball.draw_pos
        if bx > BAT_X + BAT_W + 10 and self._ball.alive:
            self._ball.alive = False
            self._stats.record_miss()
            self._miss_flash = 45
            self._show_feedback("Miss! 😬", 80)
            self._sounds.play("miss")
            self._log_event(f"❌ Miss | Balls: {self._stats.balls}")

    def _check_wicket(self) -> None:
        """Detect if ball hits stumps at the batting crease (missed by bat)."""
        if self._stumps_fallen:
            return
        bx, by = self._ball.draw_pos
        by_disp = by + int(self._ball.lateral_offset)
        stump_cx  = CREASE_X - 10          # centre of stumps x
        stump_top = PITCH_BOTTOM - 52      # top of stumps
        stump_w   = 26                     # total stump zone width

        if (stump_cx - stump_w // 2 < bx < stump_cx + stump_w // 2 and
                stump_top < by_disp < PITCH_BOTTOM and
                self._ball.alive):
            self._stumps_fallen = True
            self._ball.alive    = False
            self._wickets      += 1
            self._wicket_flash  = 120
            self._stats.record_miss()    # count as ball faced

            # Shoot stump pieces outwards
            for i in range(3):
                self._stump_pieces.append({
                    "x":    float(stump_cx - 8 + i * 8),
                    "y":    float(stump_top + 10),
                    "vx":   random.uniform(-2.5, 2.5),
                    "vy":   random.uniform(-7.0, -4.0),
                    "angle": 0.0,
                    "angv":  random.uniform(-8.0, 8.0),
                    "life":  55,
                })
            # Bail pieces
            self._stump_pieces.append({
                "x":    float(stump_cx), "y": float(stump_top - 4),
                "vx":   random.uniform(-3.0, 3.0),
                "vy":   random.uniform(-6.0, -3.0),
                "angle": 0.0, "angv": random.uniform(-12.0, 12.0),
                "life":  50,
            })

            msg = f"WICKET! 🏏 ({self._wickets} down)"
            self._show_feedback(msg, 140)
            self._tts.speak("Wicket!")
            self._sounds.play("miss")
            self._log_event(f"🎯 WICKET! Total: {self._wickets} wickets")

    def _spawn_sparks(self, x: int, y: int, count: int = 30,
                      colour=(255, 215, 0)) -> None:
        for _ in range(count):
            self._particles.append(Particle(x, y, colour, speed=5.0, radius=5))

    def _show_feedback(self, msg: str, duration: int = 90) -> None:
        self._feedback_msg   = msg
        self._feedback_timer = duration

    def _log_event(self, text: str) -> None:
        self._message_log.append(text)
        if len(self._message_log) > 6:
            self._message_log.pop(0)

    # ════════════════════════════════════════════════════════════════════════
    # Menu Drawing
    # ════════════════════════════════════════════════════════════════════════

    def _draw_menu(self) -> None:
        self._screen.blit(self._bg_surf, (0, 0))

        # Animated cricket balls floating in background
        t = pygame.time.get_ticks() / 1000.0
        for i in range(8):
            bx = int((W / 9) * (i + 1))
            by = int(H // 2 + math.sin(t * 0.8 + i * 0.9) * 140)
            pygame.draw.circle(self._screen, (160, 20, 20), (bx, by), 18)
            pygame.draw.circle(self._screen, (200, 60, 60), (bx - 4, by - 4), 6)

        # Dark overlay panel
        panel = pygame.Surface((800, 380), pygame.SRCALPHA)
        panel.fill((5, 10, 28, 200))
        self._screen.blit(panel, ((W - 800) // 2, (H - 380) // 2))

        # Animated title drop-in
        title_y = int((H - 380) // 2 + self._menu_title_y)
        title = self._font_title.render("🏏 CRICKET BOWLING MACHINE", True, C_YELLOW)
        self._screen.blit(title, (W // 2 - title.get_width() // 2, title_y))

        sub = self._font_sub.render("Voice-Controlled Simulation", True, C_CYAN)
        self._screen.blit(sub, (W // 2 - sub.get_width() // 2, title_y + 68))

        # Separator
        pygame.draw.line(self._screen, C_YELLOW,
                         (W // 2 - 300, title_y + 108), (W // 2 + 300, title_y + 108), 2)

        # Feature badges
        features = [
            ("⚾", "8 Ball Types"),
            ("🎙", "Voice Control"),
            ("🏆", "High Score"),
            ("📊", "Live Stats"),
            ("✨", "Particles"),
        ]
        bx_start = W // 2 - 330
        for i, (icon, label) in enumerate(features):
            bx = bx_start + i * 135
            by = title_y + 130
            pygame.draw.rect(self._screen, (20, 35, 70),
                             (bx, by, 120, 54), border_radius=8)
            pygame.draw.rect(self._screen, C_CYAN,
                             (bx, by, 120, 54), 1, border_radius=8)
            ic = self._font_med.render(icon, True, C_YELLOW)
            lb = self._font_tiny.render(label, True, C_TEXT)
            self._screen.blit(ic, (bx + 44, by + 5))
            self._screen.blit(lb, (bx + 60 - lb.get_width() // 2, by + 32))

        # Voice commands quick ref
        vc_y = title_y + 206
        vc_label = self._font_small.render(
            "Voice: start  fast  slow  bouncer  yorker  spin  left swing  right swing  easy  hard",
            True, C_MUTED)
        self._screen.blit(vc_label, (W // 2 - vc_label.get_width() // 2, vc_y))

        # ENTER to start — pulsing
        pulse = int(128 + 127 * math.sin(t * 3))
        enter_col = (pulse, 255, pulse)
        enter = self._font_big.render("▶  Press ENTER or say 'start'  ◀", True, enter_col)
        self._screen.blit(enter, (W // 2 - enter.get_width() // 2, title_y + 240))

        # High score from previous sessions
        if self._stats.high_score > 0:
            hs = self._font_stat.render(
                f"🏆 All-Time High Score: {self._stats.high_score}", True, C_YELLOW)
            self._screen.blit(hs, (W // 2 - hs.get_width() // 2, title_y + 300))

        # Keyboard hint strip at bottom
        hint = self._font_tiny.render(
            "← → Move Bat  |  SPACE Bowl  |  Q Quit  |  ENTER Start", True, C_MUTED)
        self._screen.blit(hint, (W // 2 - hint.get_width() // 2, H - 28))

    # ════════════════════════════════════════════════════════════════════════
    # Game Drawing
    # ════════════════════════════════════════════════════════════════════════

    def _draw_game(self) -> None:
        # 1. Sky
        self._screen.blit(self._bg_surf, (0, 0))

        # 2. Clouds
        self._draw_clouds()

        # Red miss flash overlay
        if self._miss_flash > 0:
            flash_alpha = int(80 * self._miss_flash / 45)
            flash_surf  = pygame.Surface((W, H), pygame.SRCALPHA)
            flash_surf.fill((255, 30, 30, flash_alpha))
            self._screen.blit(flash_surf, (0, 0))

        # Wicket flash (golden glow)
        if self._wicket_flash > 0:
            wa = min(120, self._wicket_flash * 3)
            wf = pygame.Surface((W, H), pygame.SRCALPHA)
            wf.fill((255, 200, 0, wa // 3))
            self._screen.blit(wf, (0, 0))

        # 3. Scene
        self._draw_crowd()
        self._draw_grass()
        self._draw_pitch()
        self._draw_fielders()
        self._draw_machine()
        self._draw_batsman()

        # 4. Trail
        for td in self._trail:
            td.draw(self._screen)

        # 5. Ball
        self._draw_ball()

        # 6. Falling stump pieces
        self._draw_stump_pieces()

        # 7. Particles
        for p in self._particles:
            p.draw(self._screen)

        # 8. Auto-bowl countdown bar
        self._draw_countdown_bar()

        # 9. HUD
        self._draw_hud()

        # 10. Traditional scoreboard
        self._draw_scoreboard()

        # 11. Stats bar
        self._draw_stats_bar()

        # 12. Feedback
        self._draw_feedback()

        # 13. Event log
        self._draw_log()

    # ── Scene Elements ─────────────────────────────────────────────────────

    def _draw_crowd(self) -> None:
        """Draw colourful crowd with varied seat colours and wave animation."""
        seat_cols = [
            (200, 30, 30), (30, 100, 200), (220, 180, 20),
            (30, 160, 80), (180, 30, 180), (220, 100, 20),
        ]
        # Lower stands
        for i in range(56):
            col = seat_cols[i % len(seat_cols)]
            h   = 28 + (i % 5) * 6
            pygame.draw.rect(self._screen, col, (i * 20, PITCH_BOTTOM + 6, 18, h))
        # Upper stands
        for i in range(56):
            col = seat_cols[(i + 2) % len(seat_cols)]
            h   = 20 + (i % 4) * 5
            pygame.draw.rect(self._screen, col, (i * 20, 58 + (i % 3) * 8, 18, h))
        # Crowd wave (arms raised — oval shapes along lower stand)
        t = pygame.time.get_ticks() / 1000.0
        for i in range(20):
            wave_h = int(8 + 6 * math.sin(t * 2 + i * 0.5))
            pygame.draw.ellipse(self._screen, (240, 220, 180),
                                (i * 55 + 2, PITCH_BOTTOM + 5, 22, wave_h))


    def _draw_grass(self) -> None:
        pygame.draw.rect(self._screen, C_GRASS_DARK, (0, PITCH_BOTTOM, W, H - PITCH_BOTTOM))
        pygame.draw.rect(self._screen, C_GRASS_DARK, (0, 110, W, PITCH_TOP - 110))
        seg = (PITCH_BOTTOM - PITCH_TOP) // 8
        for i in range(8):
            col = C_GRASS_DARK if i % 2 == 0 else C_GRASS_LITE
            pygame.draw.rect(self._screen, col, (0, PITCH_TOP + i * seg, W, seg + 1))

    def _draw_clouds(self) -> None:
        """Draw softly moving clouds in sky."""
        for c in self._clouds:
            cx, cy, cw, ch = int(c["x"]), int(c["y"]), c["w"], c["h"]
            # Main cloud body (several overlapping ellipses)
            for ox, oy, rw, rh in [
                (0,       0,       cw,      ch),
                (cw//4,  -ch//3,  cw//2,   ch//2),
                (-cw//6, -ch//4,  cw//2,   ch//2),
            ]:
                pygame.draw.ellipse(self._screen, (200, 210, 230),
                                    (cx + ox, cy + oy, rw, rh))

    def _draw_pitch(self) -> None:
        """Draw textured pitch with crease markings and scuff marks."""
        pygame.draw.rect(self._screen, C_PITCH, (60, PITCH_TOP, W - 120, PITCH_BOTTOM - PITCH_TOP))
        pygame.draw.rect(self._screen, C_PITCH_LINE, (60, PITCH_TOP, W - 120, PITCH_BOTTOM - PITCH_TOP), 2)

        # Pitch wear / scuff patches at good-length zone (~400-500 px)
        for sx, sy, sw, sh, alpha in [
            (400, PITCH_TOP + 30, 90, 20, 50),
            (430, PITCH_BOTTOM - 40, 80, 18, 40),
            (360, PITCH_TOP + 50, 50, 12, 35),
            (490, PITCH_BOTTOM - 55, 60, 14, 45),
        ]:
            scuff = pygame.Surface((sw, sh), pygame.SRCALPHA)
            scuff.fill((140, 120, 90, alpha))
            self._screen.blit(scuff, (sx, sy))

        # Ball pitch marks — small dark ovals
        for mx2, my2 in [(420, PITCH_Y - 4), (460, PITCH_Y - 3), (380, PITCH_Y - 5)]:
            pygame.draw.ellipse(self._screen, (160, 140, 100), (mx2, my2, 14, 6))

        pygame.draw.line(self._screen, C_PITCH_LINE, (130, PITCH_TOP + 10), (130, PITCH_BOTTOM - 10), 2)
        pygame.draw.line(self._screen, C_PITCH_LINE,
                         (CREASE_X - 10, PITCH_TOP + 10), (CREASE_X - 10, PITCH_BOTTOM - 10), 2)
        pygame.draw.line(self._screen, C_PITCH_LINE, (60, PITCH_TOP + 10), (W - 60, PITCH_TOP + 10), 1)
        pygame.draw.line(self._screen, C_PITCH_LINE, (60, PITCH_BOTTOM - 10), (W - 60, PITCH_BOTTOM - 10), 1)

        # Draw stumps (or fallen if struck)
        if not self._stumps_fallen:
            self._draw_stumps(130, PITCH_BOTTOM - 10, small=True)
            self._draw_stumps(CREASE_X - 10, PITCH_BOTTOM - 10, small=False)
        else:
            # Only bowling-end stumps stand; batting-end show as toppled
            self._draw_stumps(130, PITCH_BOTTOM - 10, small=True)

    def _draw_fielders(self) -> None:
        """Draw realistic fielder silhouettes at standard cricket positions."""
        positions = [
            (CREASE_X + 90, PITCH_Y - 30),   # slip cordon
            (CREASE_X + 70, PITCH_TOP + 15),  # gully
            (250, PITCH_TOP + 20),             # mid-on
            (700, PITCH_TOP + 18),             # cover
            (250, PITCH_BOTTOM - 5),           # mid-off
            (700, PITCH_BOTTOM - 5),           # mid-wicket
        ]
        for fx, fy in positions:
            # Body
            pygame.draw.rect(self._screen, (28, 28, 48), (fx - 7, fy - 16, 14, 26), border_radius=2)
            # Head
            pygame.draw.circle(self._screen, (45, 35, 25), (fx, fy - 24), 8)
            # Legs
            pygame.draw.rect(self._screen, (35, 30, 20), (fx - 6, fy + 10, 5, 16))
            pygame.draw.rect(self._screen, (35, 30, 20), (fx + 1, fy + 10, 5, 16))

    def _draw_stumps(self, x: int, base_y: int, small: bool = False) -> None:
        gap = 8 if not small else 6
        h   = 50 if not small else 38
        w   = 4  if not small else 3
        col = (220, 210, 180)
        for i in range(3):
            sx = x - gap + i * gap
            pygame.draw.rect(self._screen, col, (sx - w // 2, base_y - h, w, h))
        pygame.draw.rect(self._screen, (240, 220, 160), (x - gap - 2, base_y - h - 3, gap * 2 + 6, 3))

    def _draw_machine(self) -> None:
        mx, my = MACHINE_X, MACHINE_Y
        running = self._machine.get_status()["running"]

        # Tripod base
        pygame.draw.polygon(self._screen, (70, 75, 100),
                            [(mx - 22, my + 42), (mx + 22, my + 42), (mx, my + 8)])
        # Body box with gradient look
        pygame.draw.rect(self._screen, (55, 65, 105), (mx - 20, my - 12, 40, 34), border_radius=6)
        pygame.draw.rect(self._screen, (80, 95, 145), (mx - 18, my - 10, 36, 8), border_radius=4)

        # Nozzle arm
        pygame.draw.rect(self._screen, (100, 115, 165), (mx + 12, my - 6, 30, 12), border_radius=5)
        # Nozzle tip (emitter)
        pygame.draw.circle(self._screen, (60, 70, 120), (mx + 42, my), 7)
        pygame.draw.circle(self._screen, (120, 140, 200) if running else (60, 65, 90),
                           (mx + 42, my), 4)

        # Spinning wheels (animated angle)
        wheel_col = (200, 60, 60) if running else (90, 90, 110)
        for wy in (my + 6, my - 6):
            pygame.draw.circle(self._screen, wheel_col, (mx, wy), 14)
            pygame.draw.circle(self._screen, (30, 30, 50), (mx, wy), 5)
            # Spoke lines
            for spoke in range(4):
                angle = math.radians(self._wheel_angle + spoke * 90)
                ex    = mx + int(math.cos(angle) * 11)
                ey    = wy + int(math.sin(angle) * 11)
                pygame.draw.line(self._screen, (150, 50, 50), (mx, wy), (ex, ey), 2)

        # Labels
        for i, txt in enumerate(["BOWLING", "MACHINE"]):
            s = self._font_tiny.render(txt, True, C_MUTED)
            self._screen.blit(s, (mx - 26, my + 48 + i * 14))

    def _draw_batsman(self) -> None:
        bx = BAT_X + 28
        by = self._bat_y
        # Body
        pygame.draw.rect(self._screen, (30, 30, 50), (bx - 14, by - 20, 28, 50), border_radius=3)
        # Helmet
        pygame.draw.circle(self._screen, (50, 40, 30), (bx, by - 32), 14)
        pygame.draw.arc(self._screen, (20, 20, 40),
                        pygame.Rect(bx - 18, by - 50, 36, 30), 0, math.pi, 6)
        # Visor
        pygame.draw.arc(self._screen, (10, 150, 220),
                        pygame.Rect(bx - 14, by - 44, 28, 18), math.pi, 2 * math.pi, 3)
        # Legs + pads
        for dx, pad_dx in [(-14, -14), (2, 3)]:
            pygame.draw.rect(self._screen, (40, 35, 25), (bx + dx, by + 28, 12, 35))
            pygame.draw.rect(self._screen, (200, 195, 185), (bx + pad_dx, by + 28, 11, 30), border_radius=2)
        # Shoes
        pygame.draw.rect(self._screen, (15, 15, 15), (bx - 18, by + 58, 16, 8))
        pygame.draw.rect(self._screen, (15, 15, 15), (bx + 2,  by + 58, 16, 8))
        # Bat
        self._draw_bat(bx - 28, by)

    def _draw_bat(self, bx: int, by: int) -> None:
        pygame.draw.rect(self._screen, C_BAT, (bx - 7, by, BAT_W, BAT_H), border_radius=3)
        pygame.draw.rect(self._screen, C_BAT_HANDLE, (bx - 3, by - 30, 6, 32), border_radius=2)
        for i in range(5):
            pygame.draw.line(self._screen, (80, 50, 20),
                             (bx - 3, by - 28 + i * 6), (bx + 3, by - 28 + i * 6), 1)

    def _draw_ball(self) -> None:
        if not self._ball.alive:
            return
        bx, by     = self._ball.draw_pos
        by_draw    = by + int(self._ball.lateral_offset)
        by_draw    = max(62, min(H - 20, by_draw))
        r          = self._ball.radius

        # Dynamic shadow on pitch surface
        if PITCH_TOP < by < PITCH_BOTTOM + 80:
            shadow_al = max(0, int(90 - abs(by - PITCH_Y) * 0.8))
            sh_w      = max(4, r * 2 + int(abs(by - PITCH_Y) * 0.3))
            sh = pygame.Surface((sh_w, 8), pygame.SRCALPHA)
            sh.fill((0, 0, 0, shadow_al))
            self._screen.blit(sh, (bx - sh_w // 2, PITCH_Y - 4))

        # Ball body
        pygame.draw.circle(self._screen, C_BALL, (bx, by_draw), r)
        # Highlight sheen
        pygame.draw.circle(self._screen, (230, 80, 80), (bx - 3, by_draw - 3), r // 3)
        # Inner dark seam line — rotates with ball
        angle_rad = math.radians(self._ball.seam_angle)
        sx1 = bx + int(math.cos(angle_rad) * r)
        sy1 = by_draw + int(math.sin(angle_rad) * r)
        sx2 = bx - int(math.cos(angle_rad) * r)
        sy2 = by_draw - int(math.sin(angle_rad) * r)
        pygame.draw.line(self._screen, C_BALL_SEAM, (sx1, sy1), (sx2, sy2), 2)
        # Cross-seam (perpendicular)
        perp = angle_rad + math.pi / 2
        px1  = bx + int(math.cos(perp) * (r - 2))
        py1  = by_draw + int(math.sin(perp) * (r - 2))
        px2  = bx - int(math.cos(perp) * (r - 2))
        py2  = by_draw - int(math.sin(perp) * (r - 2))
        pygame.draw.line(self._screen, C_BALL_SEAM, (px1, py1), (px2, py2), 1)
        # Outer arc for 3-D feel
        pygame.draw.circle(self._screen, (150, 15, 15), (bx, by_draw), r, 2)

    def _draw_stump_pieces(self) -> None:
        """Animate stumps flying through the air when wicket is struck."""
        for sp in self._stump_pieces:
            x, y = int(sp["x"]), int(sp["y"])
            # Draw a small rotated rectangle (stump piece)
            surf = pygame.Surface((5, 22), pygame.SRCALPHA)
            surf.fill((220, 210, 175))
            rotated = pygame.transform.rotate(surf, sp["angle"])
            self._screen.blit(rotated, (x - rotated.get_width() // 2,
                                        y - rotated.get_height() // 2))

    def _draw_countdown_bar(self) -> None:
        """Thin strip below HUD showing time until next auto-bowl."""
        if self._countdown_frac <= 0:
            return
        bar_w  = int(W * self._countdown_frac)
        bar_h  = 4
        bar_y  = 60
        pygame.draw.rect(self._screen, (30, 30, 55), (0, bar_y, W, bar_h))
        col_r  = int(50 + 200 * self._countdown_frac)
        col_g  = int(200 - 170 * self._countdown_frac)
        pygame.draw.rect(self._screen, (col_r, col_g, 60), (0, bar_y, bar_w, bar_h))

    # ── HUD ────────────────────────────────────────────────────────────────

    def _draw_hud(self) -> None:
        hud = pygame.Surface((W, 60), pygame.SRCALPHA)
        hud.fill((5, 10, 30, 215))
        self._screen.blit(hud, (0, 0))

        status    = self._machine.get_status()
        ball_type = status["ball_type"]
        speed     = status["speed"]
        running   = status["running"]

        # Title
        title = self._font_med.render("🏏 CRICKET BOWLING MACHINE", True, C_YELLOW)
        self._screen.blit(title, (10, 10))

        # Ball type badge
        bt_col  = TYPE_COLOURS.get(ball_type, C_WHITE)
        bt_surf = self._font_hud.render(f"⚾ {ball_type}", True, bt_col)
        self._screen.blit(bt_surf, (380, 10))

        # Speed badge
        sp_col  = {"SLOW": C_GREEN, "MEDIUM": C_YELLOW, "FAST": C_RED}.get(speed, C_WHITE)
        sp_surf = self._font_hud.render(f"⚡ {speed}", True, sp_col)
        self._screen.blit(sp_surf, (540, 10))

        # Difficulty badge
        dc = DIFFICULTY_COLOURS.get(self._difficulty, C_WHITE)
        df = self._font_hud.render(f"🎯 {self._difficulty}", True, dc)
        self._screen.blit(df, (670, 10))

        # Machine state
        st_col  = C_GREEN if running else C_RED
        st_surf = self._font_hud.render(
            "● RUNNING" if running else "■ STOPPED", True, st_col)
        self._screen.blit(st_surf, (800, 10))

        # Hint sub-row
        hint = self._font_tiny.render(
            "← → Bat  |  SPACE Bowl  |  Q Quit  |  🎙 say: fast · bouncer · yorker · spin · easy · hard",
            True, C_MUTED)
        self._screen.blit(hint, (10, 42))

        # Mic indicator
        mic_col  = C_GREEN if self._listening else C_MUTED
        mic_text = "🎙 Listening…" if self._listening else f"🎙 {self._mic_status}"
        mc       = self._font_tiny.render(mic_text, True, mic_col)
        self._screen.blit(mc, (W - 165, 42))

    def _draw_scoreboard(self) -> None:
        """Traditional cricket TV scoreboard panel (top-right corner)."""
        sb_w, sb_h = 220, 90
        sb_x, sb_y = W - sb_w - 4, 64

        # Panel background
        panel = pygame.Surface((sb_w, sb_h), pygame.SRCALPHA)
        panel.fill((5, 10, 30, 235))
        self._screen.blit(panel, (sb_x, sb_y))
        pygame.draw.rect(self._screen, C_YELLOW, (sb_x, sb_y, sb_w, sb_h), 2, border_radius=6)

        # Header
        hdr = self._font_tiny.render("SCOREBOARD", True, C_YELLOW)
        self._screen.blit(hdr, (sb_x + sb_w // 2 - hdr.get_width() // 2, sb_y + 5))

        # Main score: RUNS / WICKETS
        score_str = f"{self._score}/{self._wickets}"
        sc = self._font_big.render(score_str, True, C_WHITE)
        self._screen.blit(sc, (sb_x + 10, sb_y + 22))

        # Overs
        ov_str = f"({self._stats.overs_str()} ov)"
        ov     = self._font_small.render(ov_str, True, C_CYAN)
        self._screen.blit(ov, (sb_x + sc.get_width() + 16, sb_y + 30))

        # Run rate
        rr = self._font_tiny.render(f"RR: {self._stats.run_rate:.1f}  SR: {self._stats.strike_rate:.0f}%",
                                    True, C_MUTED)
        self._screen.blit(rr, (sb_x + 10, sb_y + 66))

    def _draw_stats_bar(self) -> None:
        """Bottom stats strip."""
        bar = pygame.Surface((W, 34), pygame.SRCALPHA)
        bar.fill((5, 10, 30, 200))
        self._screen.blit(bar, (0, H - 34))

        st = self._stats
        items = [
            (f"🏆 SCORE: {self._score}", C_CYAN),
            (f"🏏 BALLS: {st.balls}", C_TEXT),
            (f"📅 OVERS: {st.overs_str()}", C_TEXT),
            (f"📈 RUN RATE: {st.run_rate}", C_YELLOW),
            (f"💥 STRIKE RATE: {st.strike_rate}%", C_ORANGE),
            (f"🌟 HIGH SCORE: {st.high_score}", C_YELLOW),
            (f"❌ MISSES: {st.misses}", C_RED),
        ]
        x = 12
        for label, col in items:
            surf = self._font_stat.render(label, True, col)
            self._screen.blit(surf, (x, H - 30))
            x += surf.get_width() + 26

    def _draw_feedback(self) -> None:
        if self._feedback_timer <= 0:
            return
        alpha    = min(255, self._feedback_timer * 6)
        msg_surf = self._font_big.render(self._feedback_msg, True, C_YELLOW)
        msg_surf.set_alpha(alpha)
        rect = msg_surf.get_rect(center=(W // 2, H // 2 - 50))

        # Glow behind text
        glow = pygame.Surface((rect.w + 30, rect.h + 22), pygame.SRCALPHA)
        glow.fill((255, 215, 0, max(0, alpha // 5)))
        self._screen.blit(glow, (rect.x - 15, rect.y - 11))
        self._screen.blit(msg_surf, rect)

    def _draw_log(self) -> None:
        log_bg = pygame.Surface((560, 120), pygame.SRCALPHA)
        log_bg.fill((4, 6, 18, 175))
        self._screen.blit(log_bg, (8, H - 160))

        for i, entry in enumerate(self._message_log[-6:]):
            if "HIT" in entry or "✅" in entry:
                col = C_GREEN
            elif "🎙" in entry:
                col = C_CYAN
            elif "❌" in entry or "Miss" in entry:
                col = C_RED
            else:
                col = C_MUTED
            s = self._font_tiny.render(entry[:76], True, col)
            self._screen.blit(s, (14, H - 155 + i * 19))

    # ════════════════════════════════════════════════════════════════════════
    # Game-Over Screen
    # ════════════════════════════════════════════════════════════════════════

    def _draw_game_over(self) -> None:
        self._screen.blit(self._bg_surf, (0, 0))

        # Dark overlay
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self._screen.blit(ov, (0, 0))

        panel = pygame.Surface((680, 420), pygame.SRCALPHA)
        panel.fill((5, 10, 30, 230))
        px, py = (W - 680) // 2, (H - 420) // 2
        self._screen.blit(panel, (px, py))
        pygame.draw.rect(self._screen, C_YELLOW, (px, py, 680, 420), 2, border_radius=12)

        go = self._font_title.render("GAME OVER", True, C_YELLOW)
        self._screen.blit(go, (px + 340 - go.get_width() // 2, py + 30))

        st = self._stats
        lines = [
            (f"🏆  Final Score: {self._score}", C_CYAN, self._font_big),
            (f"🏏  Balls Faced: {st.balls}", C_TEXT, self._font_med),
            (f"📅  Overs: {st.overs_str()}", C_TEXT, self._font_med),
            (f"📈  Run Rate: {st.run_rate} / over", C_YELLOW, self._font_med),
            (f"💥  Strike Rate: {st.strike_rate}%", C_ORANGE, self._font_med),
            (f"🌟  High Score: {st.high_score}", C_YELLOW, self._font_med),
        ]
        for i, (text, col, fnt) in enumerate(lines):
            s = fnt.render(text, True, col)
            self._screen.blit(s, (px + 340 - s.get_width() // 2, py + 100 + i * 46))

        # New high score banner
        if self._score >= st.high_score and self._score > 0:
            hs = self._font_sub.render("🎉 NEW HIGH SCORE!", True, C_YELLOW)
            pygame.draw.rect(self._screen, (100, 80, 0),
                             (px + 190, py + 382, 300, 28), border_radius=5)
            self._screen.blit(hs, (px + 340 - hs.get_width() // 2, py + 384))

        # Restart hint
        t    = pygame.time.get_ticks() / 1000.0
        a    = int(128 + 127 * math.sin(t * 2.5))
        hint = self._font_med.render("▶  Press ENTER to Play Again", True, (a, 255, a))
        self._screen.blit(hint, (px + 340 - hint.get_width() // 2, py + 360))

    # ════════════════════════════════════════════════════════════════════════
    # Helpers
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _make_gradient(w: int, h: int, top: tuple, bot: tuple) -> pygame.Surface:
        surf = pygame.Surface((w, h))
        for y in range(h):
            t = y / h
            r = int(top[0] + (bot[0] - top[0]) * t)
            g = int(top[1] + (bot[1] - top[1]) * t)
            b = int(top[2] + (bot[2] - top[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (w, y))
        return surf
