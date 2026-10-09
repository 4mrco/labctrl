import argparse
import tkinter as tk
from core.database import init_db
from core.services import load_config, save_config, run_boot_operations

class AppController:
    def __init__(self, root, initial_mode):
        self.root = root
        self.mode = initial_mode
        self.current_app = None
        self.boot_results = None
        self.boot_completed = False
        
        # Load theme colors
        self.config = load_config()
        
        self.switch_mode(self.mode)
        
    def switch_mode(self, new_mode):
        if self.current_app:
            if hasattr(self.current_app, 'destroy'):
                try:
                    self.current_app.destroy()
                except:
                    pass
            for widget in self.root.winfo_children():
                widget.destroy()
            
        self.mode = new_mode
        
        # Save to config so it persists on restart
        if self.config.get("modo_ui") != self.mode:
            self.config["modo_ui"] = self.mode
            save_config(self.config)
            
        if self.mode == "kiosk":
            self.setup_kiosk()
        else:
            self.setup_dashboard()
            
    def setup_kiosk(self):
        from core.config import TEMAS
        from ui.kiosk import KioskFrame
        
        self.root.title("LabCTRL — Auto Registro")
        self.root.configure(bg=TEMAS["default"]["bg"])
        self.root.geometry("1200x800")
        
        def _maximize(e=None):
            self.root.attributes("-fullscreen", False)
            try:
                self.root.state("zoomed")
            except Exception:
                try:
                    self.root.attributes("-zoomed", True)
                except Exception:
                    pass

        is_full = self.config.get("kiosk_fullscreen", False)
        if is_full:
            self.root.attributes("-fullscreen", True)
            self.root.bind("<Escape>", _maximize)
        else:
            self.root.attributes("-fullscreen", False)
            _maximize()
            self.root.unbind("<Escape>")
        
        self.current_app = KioskFrame(self.root, on_switch_mode=lambda: self.switch_mode("dashboard"))
        self.current_app.pack(fill="both", expand=True)
        
        # In kiosk, boot operations run silently in background
        if not self.boot_completed:
            self.root.after(500, self.run_boot_silently)
            
    def run_boot_silently(self):
        self.boot_results = run_boot_operations(self.config)
        self.boot_completed = True
        
    def setup_dashboard(self):
        from core.config import TEMAS
        from ui.app_window import App
        
        self.root.title("LabCTRL — Dashboard")
        tema = self.config.get("tema", "claro")
        try:
            bg = TEMAS[tema]["bg"]
        except KeyError:
            bg = "#F5F6FA"
        self.root.configure(bg=bg)
        self.root.geometry("1024x768")
        self.root.attributes("-fullscreen", False)
        self.root.unbind("<Escape>")
        
        self.current_app = App(self.root, on_switch_mode=lambda: self.switch_mode("kiosk"))
        # Note: App currently packs its own children to root, so `App(self.root)` modifies root directly.
        # But wait, App uses self.root natively. If it doesn't subclass Frame, `destroy()` might be tricky.
        # Let's check if `App` has a `destroy` method or how to clean it up.
        
        if not self.boot_completed:
            # First boot in dashboard
            self.root.after(500, self.current_app._boot_checks)
            self.boot_completed = True
        elif self.boot_results:
            # We switched from kiosk to dashboard, show held results
            self.show_held_boot_results()
            
    def show_held_boot_results(self):
        # We process self.boot_results and show toasts via Dashboard
        from ui.dialogs import mostrar_toast
        res = self.boot_results
        
        if res.get("orfaos"):
            msg = f"{len(res['orfaos'])} registro(s) órfão(s) encerrado(s) silenciosamente. Use Ctrl+Z para reverter."
            mostrar_toast(self.root, msg)
            
        for b in res.get("backups", []):
            mostrar_toast(self.root, f"Backup das {b}h realizado (silencioso)!")
            
        if res.get("relogio"):
            mostrar_toast(self.root, "Atenção: Relógio parece atrasado (verificado no Kiosk)")
            
        self.boot_results = None

def main():
    init_db()
    parser = argparse.ArgumentParser(description="LabCTRL")
    parser.add_argument("--mode", choices=["kiosk", "dashboard"], help="UI mode to start")
    args = parser.parse_args()
    
    config = load_config()
    mode = args.mode or config.get("modo_ui", "dashboard")
    
    root = tk.Tk()
    controller = AppController(root, mode)
    root.mainloop()

if __name__ == "__main__":
    main()
