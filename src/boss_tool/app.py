from __future__ import annotations

import tkinter as tk

from boss_tool.gui import BossToolApp, default_config_store


def main() -> None:
    root = tk.Tk()
    BossToolApp(root, default_config_store())
    root.mainloop()


if __name__ == "__main__":
    main()
