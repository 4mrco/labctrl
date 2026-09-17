"""
ui/mapa.py — Mapa interativo do laboratório para seleção de máquina.

Exibe um Canvas com a planta do lab: mesas com PCs (01-13),
zonas de notebook (ML) e a mesa do professor/servidor.
Estações ocupadas são marcadas em azul mas continuam selecionáveis.
"""

import tkinter as tk
from core.config import TEMAS


# ── Layout constants ──────────────────────────────────────────────
# Canvas size
CW, CH = 680, 460

# Colors
_t = TEMAS["default"]
BG       = _t["bg"]
FG       = _t["fg"]
FIELD    = _t["field"]
SELECT   = _t["select"]
PC_FREE       = "#2A3B5A"  # base dark blue for free PCs
PC_OCCUPIED   = "#151D2D"  # deeper dark blue for occupied PCs
ML_FREE       = "#2E4A3E"  # base dark green for free ML slots
ML_OCCUPIED   = "#17251F"  # deeper dark green for occupied ML slots
BOLS_CLR      = "#1e2b3c"  # dark blue reference square for Bolsista
HOVER         = "#3A5F9A"  # hover highlight
DESK_CLR      = "#444444"  # teacher desk (gray)
TEXT_LIGHT    = "#FFFFFF"  # white text for all backgrounds (since all are dark)

# Geometry helpers
PC_R = 20                  # uniform PC circle radius
ML_SLOT_R = 20             # ML slot radius (same as PC for uniformity)


def _center(x, y, r):
    """Return bbox for a circle centred at (x, y) with radius r."""
    return x - r, y - r, x + r, y + r


class DialogoSelecaoMapa(tk.Toplevel):
    """Modal map dialog — returns selected machine string or None."""

    def __init__(self, parent, ocupadas: list[str]):
        super().__init__(parent)
        self.title("Selecionar Máquina")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: str | None = None
        self._ocupadas = ocupadas
        self._ml_count = sum(1 for m in ocupadas if m.upper() == "ML")
        self._hover_item = None
        self._oval_to_text: dict[int, int] = {}
        self._ml_table_info: dict[int, tuple] = {}  # oval_id -> (tx, ty, tw)

        # ── Canvas ────────────────────────────────
        self.canvas = tk.Canvas(self, width=CW, height=CH, bg=BG,
                                highlightthickness=0)
        self.canvas.pack(padx=10, pady=(10, 5))

        # ── ML Tooltip ────────────────────────────
        self._ml_tooltip_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="#555", outline="", state="hidden")
        self._ml_tooltip_text = self.canvas.create_text(0, 0, text="MESA LIVRE", fill="white", font=("Arial", 8, "bold"), state="hidden")

        self._items: dict[int, str] = {}   # canvas_id → machine string
        self._circles: dict[int, dict] = {}  # oval_id → {fill, outline}
        self._draw_map()

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_click)

        # ── Keyboard shortcuts ────────────────────
        self.bind("<Key>", self._on_key)

        # ── Bottom bar with fallback button & hint ───────
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=10, pady=(5, 10))
        
        lbl_info = tk.Label(bottom, text="ⓘ", bg=BG, fg="#888", font=("Arial", 12))
        lbl_info.pack(side="left", padx=5)
        
        self._tooltip = None
        
        def on_enter(e):
            self._tooltip = tk.Toplevel(self)
            self._tooltip.overrideredirect(True)
            self._tooltip.geometry(f"+{e.x_root + 15}+{e.y_root + 10}")
            tk.Label(
                self._tooltip,
                text="A seleção de máquina na entrada pode ser alterada em Configurações.",
                bg="#333", fg="white", font=("Arial", 9), padx=5, pady=3,
                relief="solid", borderwidth=1
            ).pack()

        def on_leave(e):
            if self._tooltip:
                self._tooltip.destroy()
                self._tooltip = None

        lbl_info.bind("<Enter>", on_enter)
        lbl_info.bind("<Leave>", on_leave)
                 
        tk.Button(bottom, text="Definir depois", command=self._sem_maquina,
                  bd=0, highlightthickness=0, bg=FIELD, fg=FG,
                  padx=20, pady=6, font=("Arial", 10)).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center on parent
        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        wx, wh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - wx) // 2}+{py + (ph - wh) // 2}")

    # ── Drawing ───────────────────────────────────────────────────

    def _draw_map(self):
        c = self.canvas

        # ── Teacher / Server desk (top-right, blank) ─
        c.create_rectangle(460, 20, 580, 60, fill=DESK_CLR, outline="#555", width=1)
        self._draw_bolsista(c, 540, 40)

        # ══════════════════════════════════════════
        # LEFT COLUMN
        # ══════════════════════════════════════════

        # Table 1: ML zone (top-left)
        self._draw_table(c, 60, 100, 240, 75, "Mesa 1 — Notebook (ML)")
        ml_left_slots = [(100, 125), (180, 125), (260, 125)]
        self._draw_ml_slots(c, ml_left_slots, ["ML-1", "ML-2", "ML-3"], tx=60, ty=100, tw=240)

        # Table 2: PCs 04, 05, 06 (mid-left)
        self._draw_table(c, 60, 210, 240, 75, "Mesa 2")
        self._draw_pc(c, 100, 235, "04")
        self._draw_pc(c, 180, 235, "05")
        self._draw_pc(c, 260, 235, "06")

        # Table 3: PCs 10, 11, 12 (bottom-left)
        self._draw_table(c, 60, 320, 240, 75, "Mesa 3")
        self._draw_pc(c, 100, 345, "10")
        self._draw_pc(c, 180, 345, "11")
        self._draw_pc(c, 260, 345, "12")

        # ══════════════════════════════════════════
        # RIGHT COLUMN
        # ══════════════════════════════════════════

        # Table 4: PCs 01, 02, 03 (top-right)
        self._draw_table(c, 380, 100, 240, 75, "Mesa 4")
        self._draw_pc(c, 420, 125, "01")
        self._draw_pc(c, 500, 125, "02")
        self._draw_pc(c, 580, 125, "03")

        # Table 5: ML zone (mid-right)
        self._draw_table(c, 380, 210, 240, 75, "Mesa 5 — Notebook (ML)")
        ml_right_slots = [(420, 235), (500, 235), (580, 235)]
        self._draw_ml_slots(c, ml_right_slots, ["ML-4", "ML-5", "ML-6"], tx=380, ty=210, tw=240)

        # Table 6: PCs 07, 08, 09 (bottom-right)
        self._draw_table(c, 380, 320, 240, 75, "Mesa 6")
        self._draw_pc(c, 420, 345, "07")
        self._draw_pc(c, 500, 345, "08")
        self._draw_pc(c, 580, 345, "09")



    def _draw_table(self, c: tk.Canvas, x, y, w, h, label: str):
        """Draw a table rectangle."""
        c.create_rectangle(x, y, x + w, y + h, fill=FIELD, outline="#555", width=1)

    def _draw_bolsista(self, c: tk.Canvas, cx, cy):
        """Draw the Bolsista square station (visual reference only, unselectable)."""
        # Square bounding box (30x30 => r=15)
        c.create_rectangle(cx - 15, cy - 15, cx + 15, cy + 15, fill=BOLS_CLR, outline="#555", width=2)

    def _draw_pc(self, c: tk.Canvas, cx, cy, label: str):
        """Draw a PC station. Both states use dark backgrounds."""
        occupied = label in self._ocupadas
        fill = PC_OCCUPIED if occupied else PC_FREE
        outline = HOVER if occupied else "#555"
        text_color = TEXT_LIGHT

        # Draw circle FIRST, then text ON TOP (correct z-order)
        cid = c.create_oval(*_center(cx, cy, PC_R), fill=fill, outline=outline, width=2)
        tid = c.create_text(cx, cy, text=label, fill=text_color,
                            font=("Arial", 10, "bold"))

        # All stations are selectable (occupied included)
        self._items[cid] = label
        self._items[tid] = label
        self._circles[cid] = {"fill": fill, "outline": outline}
        self._oval_to_text[cid] = tid

    def _draw_ml_slots(self, c: tk.Canvas, positions: list[tuple], labels: list[str], tx: int, ty: int, tw: int):
        """Draw 3 ML slot circles. Both states use dark backgrounds."""
        for i, (cx, cy) in enumerate(positions):
            label = labels[i]
            occupied = label in self._ocupadas
            
            # Backward compatibility with generic "ML" records
            if not occupied and self._ml_count > 0:
                occupied = True
                self._ml_count -= 1
                
            fill = ML_OCCUPIED if occupied else ML_FREE
            outline = HOVER if occupied else "#555"
            text_color = TEXT_LIGHT

            cid = c.create_oval(*_center(cx, cy, ML_SLOT_R), fill=fill, outline=outline, width=2)
            tid = c.create_text(cx, cy, text="ML", fill=text_color,
                                font=("Arial", 10, "bold"))

            # All ML slots are selectable
            self._items[cid] = label
            self._items[tid] = label
            self._circles[cid] = {"fill": fill, "outline": outline}
            self._oval_to_text[cid] = tid
            self._ml_table_info[cid] = (tx, ty, tw)

    # ── Interaction ───────────────────────────────────────────────

    def _find_oval_at(self, x, y) -> int | None:
        """Find the interactive oval item closest to (x, y)."""
        items = self.canvas.find_overlapping(x - 3, y - 3, x + 3, y + 3)
        for item_id in reversed(items):  # top-most first
            if item_id in self._items:
                # If it's a text item, find its parent oval
                for oval_id, text_id in self._oval_to_text.items():
                    if item_id == text_id or item_id == oval_id:
                        return oval_id
        return None

    def _on_motion(self, event):
        """Highlight circle under cursor."""
        oval_id = self._find_oval_at(event.x, event.y)

        # Unhover previous
        if self._hover_item and self._hover_item != oval_id:
            info = self._circles.get(self._hover_item)
            if info:
                self.canvas.itemconfigure(self._hover_item, fill=info["fill"],
                                          outline=info["outline"])

        # Hover current
        if oval_id and oval_id in self._circles:
            self.canvas.itemconfigure(oval_id, fill=HOVER, outline=FG)
            self._hover_item = oval_id
            self.config(cursor="hand2")
            
            # ML Tooltip logic
            item_val = str(self._items.get(oval_id, ""))
            if item_val.startswith("ML"):
                info = self._ml_table_info.get(oval_id)
                if info:
                    tx, ty, tw = info
                    cx = tx + tw / 2
                    cy = ty - 10
                    self.canvas.itemconfigure(self._ml_tooltip_text, state="normal")
                    self.canvas.coords(self._ml_tooltip_text, cx, cy)
                    bbox = self.canvas.bbox(self._ml_tooltip_text)
                    if bbox and len(bbox) == 4:
                        self.canvas.coords(self._ml_tooltip_bg, bbox[0]-4, bbox[1]-2, bbox[2]+4, bbox[3]+2)
                        self.canvas.itemconfigure(self._ml_tooltip_bg, state="normal")
            else:
                self.canvas.itemconfigure(self._ml_tooltip_text, state="hidden")
                self.canvas.itemconfigure(self._ml_tooltip_bg, state="hidden")
        else:
            if self._hover_item:
                info = self._circles.get(self._hover_item)
                if info:
                    self.canvas.itemconfigure(self._hover_item, fill=info["fill"],
                                              outline=info["outline"])
                self._hover_item = None
            self.config(cursor="")
            self.canvas.itemconfigure(self._ml_tooltip_text, state="hidden")
            self.canvas.itemconfigure(self._ml_tooltip_bg, state="hidden")

    def _on_click(self, event):
        """Select clicked station."""
        oval_id = self._find_oval_at(event.x, event.y)
        if oval_id:
            machine = self._items.get(oval_id)
            if machine:
                self.result = machine
                self.destroy()

    def _on_key(self, event):
        """Keyboard shortcuts: digits select PC, M/L selects ML, Escape closes."""
        ch = event.char.upper()
        if ch == "\x1b":  # Escape
            self._on_close()
            return
        if ch in ("M", "L"):
            self.result = "ML"
            self.destroy()
            return
        if ch.isdigit():
            num = int(ch)
            if 1 <= num <= 9:
                label = f"{num:02}"
                self.result = label
                self.destroy()

    def _sem_maquina(self):
        """Fallback: no machine."""
        self.result = "-"
        self.destroy()

    def _on_close(self):
        """User closed without selecting."""
        self.result = None
        self.destroy()


def selecionar_maquina(parent, ocupadas: list[str]) -> str | None:
    """Open the map dialog and return the selected machine string, or None if cancelled."""
    dlg = DialogoSelecaoMapa(parent, ocupadas)
    parent.wait_window(dlg)
    return dlg.result
