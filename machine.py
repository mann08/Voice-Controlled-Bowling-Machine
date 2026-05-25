"""
machine.py
----------
BowlingMachine class — simulates the hardware state of the bowling machine.

OOP Concept: Encapsulation — all machine state is private and accessed
only through well-defined public methods.

Extended from the original to support cricket-specific ball types:
    NORMAL, FAST, SLOW, BOUNCER, YORKER, SPIN, LEFT_SWING, RIGHT_SWING
"""

# ── Allowed constant values ────────────────────────────────────────────────
SPEED_LEVELS = ["SLOW", "MEDIUM", "FAST"]
DIRECTIONS   = ["LEFT", "STRAIGHT", "RIGHT"]

# Cricket ball delivery types
BALL_TYPES = [
    "NORMAL",
    "FAST",
    "SLOW",
    "BOUNCER",
    "YORKER",
    "SPIN",
    "LEFT_SWING",
    "RIGHT_SWING",
]


class BowlingMachine:
    """
    Represents the bowling machine hardware state.

    Attributes
    ----------
    _speed      : str   — speed level (SLOW / MEDIUM / FAST)
    _direction  : str   — direction   (LEFT / STRAIGHT / RIGHT)
    _spin       : bool  — spin flag
    _running    : bool  — machine active?
    _ball_count : int   — total balls bowled
    _ball_type  : str   — current delivery type
    """

    def __init__(self):
        """Initialise with safe defaults."""
        self._speed      = "MEDIUM"
        self._direction  = "STRAIGHT"
        self._spin       = False
        self._running    = False
        self._ball_count = 0
        self._ball_type  = "NORMAL"     # ← NEW: delivery type

    # ── Core control ───────────────────────────────────────────────────────

    def start(self) -> str:
        """Start the bowling machine."""
        if self._running:
            return "Machine is already running."
        self._running = True
        return (f"Machine STARTED — Type: {self._ball_type}, "
                f"Speed: {self._speed}, Direction: {self._direction}.")

    def stop(self) -> str:
        """Stop the bowling machine."""
        if not self._running:
            return "Machine is already stopped."
        self._running = False
        return "Machine STOPPED."

    def reset(self) -> str:
        """Reset all settings to factory defaults."""
        self._speed      = "MEDIUM"
        self._direction  = "STRAIGHT"
        self._spin       = False
        self._running    = False
        self._ball_count = 0
        self._ball_type  = "NORMAL"
        return "Machine RESET — Medium speed, Straight, Normal delivery."

    # ── Speed control ──────────────────────────────────────────────────────

    def increase_speed(self) -> str:
        """Increase speed one level (SLOW → MEDIUM → FAST)."""
        idx = SPEED_LEVELS.index(self._speed)
        if idx == len(SPEED_LEVELS) - 1:
            return f"Already at maximum speed: {self._speed}."
        self._speed = SPEED_LEVELS[idx + 1]
        return f"Speed increased to {self._speed}."

    def decrease_speed(self) -> str:
        """Decrease speed one level (FAST → MEDIUM → SLOW)."""
        idx = SPEED_LEVELS.index(self._speed)
        if idx == 0:
            return f"Already at minimum speed: {self._speed}."
        self._speed = SPEED_LEVELS[idx - 1]
        return f"Speed decreased to {self._speed}."

    def set_speed(self, level: str) -> str:
        """Directly set speed level."""
        level = level.upper()
        if level not in SPEED_LEVELS:
            return f"Invalid speed '{level}'. Choose from {SPEED_LEVELS}."
        self._speed = level
        return f"Speed set to {self._speed}."

    # ── Direction control ──────────────────────────────────────────────────

    def set_direction(self, direction: str) -> str:
        """Set bowling direction."""
        direction = direction.upper()
        if direction not in DIRECTIONS:
            return f"Invalid direction '{direction}'."
        self._direction = direction
        return f"Direction set to {self._direction}."

    # ── Spin control ───────────────────────────────────────────────────────

    def spin_on(self) -> str:
        if self._spin:
            return "Spin is already ON."
        self._spin = True
        return "Spin ENABLED."

    def spin_off(self) -> str:
        if not self._spin:
            return "Spin is already OFF."
        self._spin = False
        return "Spin DISABLED."

    # ── Ball type control (NEW) ────────────────────────────────────────────

    def set_ball_type(self, ball_type: str) -> str:
        """
        Set the delivery type.

        Parameters
        ----------
        ball_type : str — one of BALL_TYPES (case-insensitive)
        """
        bt = ball_type.upper().replace(" ", "_")
        if bt not in BALL_TYPES:
            return (f"Unknown ball type '{ball_type}'. "
                    f"Choose from: {', '.join(BALL_TYPES)}.")
        self._ball_type = bt

        # Auto-adjust speed preset for the delivery type
        presets = {
            "FAST":        "FAST",
            "SLOW":        "SLOW",
            "BOUNCER":     "MEDIUM",
            "YORKER":      "FAST",
            "SPIN":        "SLOW",
            "LEFT_SWING":  "MEDIUM",
            "RIGHT_SWING": "MEDIUM",
            "NORMAL":      "MEDIUM",
        }
        self._speed = presets.get(bt, self._speed)

        return f"Delivery type set to {self._ball_type} (speed: {self._speed})."

    # ── Bowl simulation ────────────────────────────────────────────────────

    def bowl(self) -> str:
        """Simulate bowling one ball."""
        if not self._running:
            return "Cannot bowl — machine is not running. Say 'start' first."
        self._ball_count += 1
        return (f"Ball #{self._ball_count}: {self._ball_type} | "
                f"Speed: {self._speed} | Direction: {self._direction}.")

    # ── Status ─────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return full machine state as a dictionary."""
        return {
            "running":    self._running,
            "speed":      self._speed,
            "direction":  self._direction,
            "spin":       self._spin,
            "ball_count": self._ball_count,
            "ball_type":  self._ball_type,      # ← NEW key
        }

    def get_status_text(self) -> str:
        """Return human-readable status string."""
        state = "RUNNING" if self._running else "STOPPED"
        spin  = "ON"      if self._spin    else "OFF"
        return (f"Status — {state} | Type: {self._ball_type} | "
                f"Speed: {self._speed} | Dir: {self._direction} | "
                f"Spin: {spin} | Balls: {self._ball_count}")
