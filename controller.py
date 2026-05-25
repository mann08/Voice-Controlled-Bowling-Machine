"""
controller.py
-------------
Controller — maps text commands to BowlingMachine actions.

OOP Concept: Command Pattern via dictionary dispatch.
Extended to handle cricket-specific delivery types:
    fast, slow, bouncer, yorker, spin, left swing, right swing
"""

from machine import BowlingMachine


class Controller:
    """
    Maps textual / voice commands to BowlingMachine actions.

    Usage
    -----
        ctrl = Controller(machine)
        response = ctrl.handle("bouncer")
        print(response)   # → "Delivery type set to BOUNCER (speed: MEDIUM)."
    """

    def __init__(self, machine: BowlingMachine):
        self._machine = machine

        # ── Command → handler mapping ──────────────────────────────────────
        # Dictionary dispatch avoids long if/elif chains and is easy to extend.
        self._commands: dict = {

            # ── Start / Stop ───────────────────────────────────────────────
            "start":          lambda: self._machine.start(),
            "stop":           lambda: self._machine.stop(),
            "pause":          lambda: self._machine.stop(),
            "halt":           lambda: self._machine.stop(),

            # ── Reset ──────────────────────────────────────────────────────
            "reset":          lambda: self._machine.reset(),
            "restart":        lambda: self._machine.reset(),

            # ── Speed — relative ───────────────────────────────────────────
            "increase speed": lambda: self._machine.increase_speed(),
            "speed up":       lambda: self._machine.increase_speed(),
            "faster":         lambda: self._machine.increase_speed(),
            "decrease speed": lambda: self._machine.decrease_speed(),
            "slow down":      lambda: self._machine.decrease_speed(),
            "slower":         lambda: self._machine.decrease_speed(),
            "reduce speed":   lambda: self._machine.decrease_speed(),

            # ── Direction ──────────────────────────────────────────────────
            "left":           lambda: self._machine.set_direction("LEFT"),
            "go left":        lambda: self._machine.set_direction("LEFT"),
            "right":          lambda: self._machine.set_direction("RIGHT"),
            "go right":       lambda: self._machine.set_direction("RIGHT"),
            "straight":       lambda: self._machine.set_direction("STRAIGHT"),
            "center":         lambda: self._machine.set_direction("STRAIGHT"),
            "centre":         lambda: self._machine.set_direction("STRAIGHT"),

            # ── Spin (flag toggle) ─────────────────────────────────────────
            "spin on":        lambda: self._machine.spin_on(),
            "enable spin":    lambda: self._machine.spin_on(),
            "no spin":        lambda: self._machine.spin_off(),
            "spin off":       lambda: self._machine.spin_off(),
            "disable spin":   lambda: self._machine.spin_off(),

            # ── Ball Delivery Types (NEW — voice commands) ─────────────────
            "fast":           lambda: self._machine.set_ball_type("FAST"),
            "slow":           lambda: self._machine.set_ball_type("SLOW"),
            "bouncer":        lambda: self._machine.set_ball_type("BOUNCER"),
            "yorker":         lambda: self._machine.set_ball_type("YORKER"),
            "spin":           lambda: self._machine.set_ball_type("SPIN"),
            "left swing":     lambda: self._machine.set_ball_type("LEFT_SWING"),
            "right swing":    lambda: self._machine.set_ball_type("RIGHT_SWING"),
            "normal":         lambda: self._machine.set_ball_type("NORMAL"),
            "medium":         lambda: self._machine.set_ball_type("NORMAL"),

            # ── Difficulty (handled in pygame_game but kept here for CLI/GUI fallback)
            "easy":           lambda: "Difficulty set to EASY.",
            "hard":           lambda: "Difficulty set to HARD.",


            # ── Bowl ───────────────────────────────────────────────────────
            "bowl":           lambda: self._machine.bowl(),
            "throw":          lambda: self._machine.bowl(),
            "fire":           lambda: self._machine.bowl(),

            # ── Status ─────────────────────────────────────────────────────
            "status":         lambda: self._machine.get_status_text(),
        }

    # ── Public API ─────────────────────────────────────────────────────────

    def handle(self, raw_command: str) -> str:
        """
        Process a raw command string and return a response message.

        Uses two-stage matching:
          1. Exact O(1) dictionary lookup.
          2. Substring scan — handles partial recognition
             e.g. "please say bouncer" still matches "bouncer".
        """
        if not raw_command or not raw_command.strip():
            return "Empty command. Please say something."

        cmd = raw_command.lower().strip()

        # Stage 1 — exact match
        if cmd in self._commands:
            return self._commands[cmd]()

        # Stage 2 — substring match (handles noisy ASR output)
        for key, action in self._commands.items():
            if key in cmd:
                return action()

        return (f"Unknown command: '{raw_command}'. "
                "Try: start, stop, fast, slow, bouncer, yorker, spin, "
                "left swing, right swing…")

    def get_command_list(self) -> list[str]:
        """Return sorted list of all recognised phrases."""
        return sorted(self._commands.keys())
