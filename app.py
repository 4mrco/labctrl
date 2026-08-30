import tkinter as tk
from core.database import init_db
from ui.app_window import App

if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = App(root)
    root.mainloop()
