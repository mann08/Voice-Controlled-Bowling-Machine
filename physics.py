"""
physics.py
----------
Ball physics engine for the cricket bowling machine simulation.

Handles:
  - Position + velocity per frame
  - Gravity effect (downward acceleration)
  - Bounce (when ball hits pitch Y level)
  - Lateral swing (LEFT_SWING / RIGHT_SWING)
  - Spin curve (sinusoidal lateral drift)
  - Per-delivery-type initial conditions

Each ball type gets specific launch parameters:

  NORMAL     — medium speed, gentle arc
  FAST       — high speed, flat trajectory
  SLOW       — slow speed, noticeable arc
  BOUNCER    — medium speed, launches upward → high bounce
  YORKER     — high speed, near-ground, barely bounces
  SPIN       — slow-medium speed, lateral sinusoidal drift
  LEFT_SWING — medium speed, constant leftward drift
  RIGHT_SWING— medium speed, constant rightward drift
"""

import math


# ── Constants ──────────────────────────────────────────────────────────────
GRAVITY      = 0.20     # pixels per frame² — downward pull
BOUNCE_DAMP  = 0.50     # velocity retained after bounce (energy loss)
MIN_BOUNCE_V = 1.5      # below this vy we kill vertical velocity (stops jiggle)


class Ball:
    """
    Simulates a cricket ball in 2D screen space.

    Coordinate space
    ----------------
    Origin (0,0) is top-left.
    x increases rightward (ball travels right, toward batsman).
    y increases downward  (gravity pulls +y).

    Parameters
    ----------
    start_x   : float — initial x position (bowling machine nozzle)
    start_y   : float — initial y position
    pitch_y   : float — y-coordinate of the pitch surface (ball bounces here)
    screen_w  : int   — screen width  (ball resets when x > screen_w)
    """

    def __init__(self, start_x: float, start_y: float,
                 pitch_y: float, screen_w: int):
        self.start_x  = start_x
        self.start_y  = start_y
        self.pitch_y  = pitch_y
        self.screen_w = screen_w

        # Current state
        self.x   = start_x
        self.y   = start_y
        self.vx  = 0.0       # horizontal velocity (pixels/frame)
        self.vy  = 0.0       # vertical velocity   (pixels/frame)
        self.vx_lateral = 0.0  # lateral (sideways) velocity
        self.alive  = False  # False = waiting to be bowled
        self.radius = 10

        # Visual rotation for seam animation
        self.seam_angle      = 0.0    # degrees; drives the animated seam line
        self.rotation_speed  = 0.0    # degrees per frame

        # Spin / swing auxiliary state
        self._time        = 0.0    # frame counter for sinusoidal drift
        self._spin_enabled  = False
        self._swing_dir     = 0    # -1 left, 0 none, +1 right
        self._ball_type     = "NORMAL"
        self._bounce_count  = 0    # how many times the ball has bounced

    # ── Public API ─────────────────────────────────────────────────────────

    def reset(self, ball_type: str = "NORMAL",
              initial_y_offset: float = 0.0) -> None:
        """
        Re-launch the ball with parameters suited to the given delivery type.

        Parameters
        ----------
        ball_type      : one of the recognised type strings
        initial_y_offset: extra y shift (0 = default launch height)
        """
        self._ball_type    = ball_type.upper()
        self._time         = 0.0
        self._bounce_count = 0
        self.alive         = True
        self.x             = self.start_x
        self.vx_lateral    = 0.0
        self.seam_angle    = 0.0

        # Per-type seam rotation speed (degrees/frame)
        _rot = {
            "FAST":        8.0,
            "SLOW":        3.5,
            "BOUNCER":     6.0,
            "YORKER":      9.0,
            "SPIN":       12.0,   # fast visual spin
            "LEFT_SWING":  5.0,
            "RIGHT_SWING": 5.0,
            "NORMAL":      4.5,
        }
        self.rotation_speed = _rot.get(self._ball_type, 4.5)

        # ── Per-type launch parameters ─────────────────────────────────────
        if self._ball_type == "FAST":
            # Flat, very fast
            self.y  = self.start_y
            self.vx = 14.0
            self.vy = -1.5    # slight upward to arc naturally
            self._spin_enabled = False
            self._swing_dir    = 0

        elif self._ball_type == "SLOW":
            # High looping arc
            self.y  = self.start_y
            self.vx = 5.5
            self.vy = -5.0    # more upward → higher arc
            self._spin_enabled = False
            self._swing_dir    = 0

        elif self._ball_type == "BOUNCER":
            # Medium pace with aggressive upward launch — pops off pitch
            self.y  = self.pitch_y   # starts at pitch level
            self.vx = 9.0
            self.vy = -11.0   # strong upward → bounces high off pitch
            self._spin_enabled = False
            self._swing_dir    = 0

        elif self._ball_type == "YORKER":
            # Very fast, barely off the ground
            self.y  = self.pitch_y - 5.0
            self.vx = 13.0
            self.vy = -0.5    # nearly horizontal
            self._spin_enabled = False
            self._swing_dir    = 0

        elif self._ball_type == "SPIN":
            # Slow with sinusoidal lateral drift (off-spin effect)
            self.y  = self.start_y
            self.vx = 6.0
            self.vy = -3.0
            self._spin_enabled = True
            self._swing_dir    = 0

        elif self._ball_type == "LEFT_SWING":
            # Medium pace, constant leftward drift
            self.y  = self.start_y
            self.vx = 8.5
            self.vy = -2.5
            self._spin_enabled = False
            self._swing_dir    = -1   # drift left in screen-y terms

        elif self._ball_type == "RIGHT_SWING":
            # Medium pace, constant rightward drift
            self.y  = self.start_y
            self.vx = 8.5
            self.vy = -2.5
            self._spin_enabled = False
            self._swing_dir    = 1    # drift right

        else:
            # NORMAL — gentle medium arc
            self.y  = self.start_y
            self.vx = 9.0
            self.vy = -2.0
            self._spin_enabled = False
            self._swing_dir    = 0

    def update(self) -> None:
        """
        Advance one frame: apply physics and update position.

        Order of operations:
          1. Apply gravity to vy
          2. Apply lateral swing / spin drift to vx_lateral
          3. Update position
          4. Handle pitch bounce
          5. Kill ball if off-screen
        """
        if not self.alive:
            return

        self._time += 1.0

        # 0. Seam rotation
        self.seam_angle = (self.seam_angle + self.rotation_speed) % 360

        # 1. Gravity
        self.vy += GRAVITY

        # Air drag (ball decelerates slightly as it travels)
        self.vx *= 0.9995

        # 2. Lateral drift ─────────────────────────────────────────────────
        if self._spin_enabled:
            # Sinusoidal drift — amplitude grows slightly with time
            amplitude = 1.8
            self.vx_lateral = amplitude * math.sin(self._time * 0.12)
        elif self._swing_dir != 0:
            # Constant lateral push (increases slightly over flight)
            self.vx_lateral = self._swing_dir * min(0.06 * self._time, 3.5)
        else:
            self.vx_lateral = 0.0

        # 3. Update position
        self.x += self.vx
        self.y += self.vy
        # Lateral drift is applied vertically in screen space
        # (ball moves left/right toward the batsman's body line)
        # We encode lateral drift as a separate draw-offset below;
        # store it as y_lateral for 2-D rendering.
        self.y_lateral = getattr(self, '_y_lateral_acc', 0.0) + self.vx_lateral
        self._y_lateral_acc = self.y_lateral

        # 4. Pitch bounce
        if self.y >= self.pitch_y:
            self.y  = self.pitch_y
            self.vy = -self.vy * BOUNCE_DAMP   # reverse + dampen

            if abs(self.vy) < MIN_BOUNCE_V:
                self.vy = 0.0                  # stop bouncing

            self._bounce_count += 1

        # 5. Off-screen check — ball reached or passed the right edge
        if self.x > self.screen_w + 40:
            self.alive = False

    # ── Properties ─────────────────────────────────────────────────────────

    def get_rect(self) -> tuple[int, int, int, int]:
        """
        Return (x, y, width, height) for collision detection.

        The y displayed on screen is self.y for vertical position,
        and we add lateral drift to a separate perpendicular axis.
        For collision purposes we use the screen-draw y.
        """
        draw_x = int(self.x)
        draw_y = int(self.y)
        d = self.radius * 2
        return (draw_x - self.radius, draw_y - self.radius, d, d)

    @property
    def draw_pos(self) -> tuple[int, int]:
        """Screen coordinates for drawing the ball centre."""
        return (int(self.x), int(self.y))

    @property
    def lateral_offset(self) -> float:
        """
        How many pixels the ball has drifted laterally.
        Used by the renderer to shift the ball's draw-y.
        """
        return getattr(self, '_y_lateral_acc', 0.0)
