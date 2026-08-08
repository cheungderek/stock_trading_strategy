"""
strategy_selector.py - interactive strategy selection menu.

Option 1 = VCP (Mark Minervini)        - new
Option 2 = Donchian 20/10 breakout     - existing scanner
Option 3 = Run both side-by-side

Returns a normalized strategy key string after the user picks.
"""
from __future__ import annotations

import sys

STRATEGIES = {
    "1": "vcp",
    "2": "donchian",
    "3": "both",
    "4": "ma_trend",
}

MENU = """\
==========================================================
   Strategy Selection Menu
==========================================================
  Option 1  - VCP (Volatility Contraction, Minervini)
  Option 2  - Donchian 20/10 breakout  (current scanner)
  Option 3  - Run 1+2 side-by-side  (default for daily scan)
  Option 4  - 20-MA Trend Strength
              (consistently above vs blocked by 20-day MA)
  Option 5  - Run all three (1+2+4)
  Option 0  - Exit
----------------------------------------------------------"""


def prompt(arg: str | None = None) -> str:
    """Return the selected strategy code, or raise SystemExit on 0/invalid."""
    if arg is not None:
        key = str(arg).strip()
        if key in {"0", "q", "Q"}:
            raise SystemExit("User exited.")
        if key == "5":
            return "all"
        if key not in STRATEGIES:
            raise SystemExit(f"Invalid strategy option '{key}'. Valid: 1-5.")
        return STRATEGIES[key]

    print(MENU)
    choice = input("Select strategy [1/2/3/4/5/0]: ").strip()
    if choice in {"0", "q", "Q"}:
        raise SystemExit("User exited.")
    if choice == "5":
        return "all"
    if choice not in STRATEGIES:
        print(f"Invalid choice '{choice}'. Try again.")
        return prompt()
    return STRATEGIES[choice]


if __name__ == "__main__":
    key = prompt(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Selected: {key}")
