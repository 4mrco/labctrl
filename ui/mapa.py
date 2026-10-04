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
CW, CH = 782, 530

TIMEOUT_MS = 60_000

# Colors
_t = TEMAS["default"]
BG       = _t["bg"]
FG       = _t["fg"]
FIELD    = _t["field"]
SELECT   = _t["select"]
PC_FREE       = "#1E4D8C"  # bright blue for free PCs (clearly available)
PC_OCCUPIED   = "#1A1A2E"  # very dark navy for occupied PCs (clearly taken)
ML_FREE       = "#1A6B3C"  # bright green for free ML slots (clearly available)
ML_OCCUPIED   = "#0F2218"  # very dark green for occupied ML slots (clearly taken)
PC_FREE_RING  = "#5B9BD5"  # light blue ring outline for free PCs
ML_FREE_RING  = "#4EC97B"  # light green ring outline for free ML slots
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
            self._tooltip.transient(self)
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

        def _cleanup_tooltip(e=None):
            if self._tooltip:
                self._tooltip.destroy()
                self._tooltip = None

        lbl_info.bind("<Enter>", on_enter)
        lbl_info.bind("<Leave>", on_leave)
        self.bind("<Destroy>", _cleanup_tooltip, add="+")
                 
        tk.Button(bottom, text="Definir depois", command=self._sem_maquina,
                  bd=0, highlightthickness=0, bg=FIELD, fg=FG,
                  padx=20, pady=6, font=("Arial", 10)).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center before <Map> fires so geometry is already set when grab is acquired
        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        wx, wh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - wx) // 2}+{py + (ph - wh) // 2}")

        self._timeout_job = self.after(TIMEOUT_MS, self._on_timeout)

        # Grab only after the window is mapped — same pattern as setup_dialog
        _grabbed = [False]
        def _on_map(event=None):
            if _grabbed[0]:
                return
            try:
                self.grab_set()
                self.focus_force()   # força o WM a dar foco ao mapa (focus_set só pede dentro da app)
                self.lift()
                _grabbed[0] = True
            except tk.TclError:
                if self.winfo_exists():
                    self.after(30, _on_map)

        self.bind("<Map>", _on_map, add="+")

        def _on_mapa_destroy(event):
            if event.widget is not self:
                return
            try:
                if hasattr(parent, "_from_dialog"):
                    parent.after(80, parent._from_dialog)
            except tk.TclError:
                pass

        self.bind("<Destroy>", _on_mapa_destroy, add="+")

    # ── Drawing ───────────────────────────────────────────────────

    def _draw_map(self):
        c = self.canvas

        # ── Teacher / Server desk (top-right) — L-shaped ─
        # Seamless L-shape polygon to avoid inner dividing lines
        c.create_polygon(
            663, 5,    # Top-left of vertical stem
            713, 5,    # Top-right of vertical stem
            713, 90,   # Bottom-right corner
            543, 90,   # Bottom-left corner
            543, 40,   # Top-left of horizontal foot
            663, 40,   # Inner corner
            fill=DESK_CLR, outline="#555", width=1
        )
        # Bolsista reference stays on horizontal portion, moved to the right inner corner
        self._draw_bolsista(c, 638, 65)

        # ── Shortcuts Helper Text (top-left) ─
        c.create_text(
            69, 23,
            text="Pressione 1–9 para máquinas 01–09\nPressione M ou L para mesa livre",
            fill=TEXT_LIGHT, font=("Arial", 11), anchor="nw", justify="left"
        )

        # ════════════════════════════════════════════
        # LEFT COLUMN
        # ════════════════════════════════════════════

        # Table 1: ML zone (top-left)
        self._draw_table(c, 69, 145, 276, 86, "Mesa 1 — Notebook (ML)")
        ml_left_slots = [(115, 174), (207, 174), (299, 174)]
        self._draw_ml_slots(c, ml_left_slots, ["ML-1", "ML-2", "ML-3"], tx=69, ty=145, tw=276)

        # Table 2: PCs 04, 05, 06 (mid-left)
        self._draw_table(c, 69, 272, 276, 86, "Mesa 2")
        self._draw_pc(c, 115, 300, "04")
        self._draw_pc(c, 207, 300, "05")
        self._draw_pc(c, 299, 300, "06")

        # Table 3: PCs 10, 11, 12 (bottom-left)
        self._draw_table(c, 69, 398, 276, 86, "Mesa 3")
        self._draw_pc(c, 115, 427, "10")
        self._draw_pc(c, 207, 427, "11")
        self._draw_pc(c, 299, 427, "12")

        # ════════════════════════════════════════════
        # RIGHT COLUMN
        # ════════════════════════════════════════════

        # Table 4: PCs 01, 02, 03 (top-right)
        self._draw_table(c, 437, 145, 276, 86, "Mesa 4")
        self._draw_pc(c, 483, 174, "01")
        self._draw_pc(c, 575, 174, "02")
        self._draw_pc(c, 667, 174, "03")

        # Table 5: ML zone (mid-right)
        self._draw_table(c, 437, 272, 276, 86, "Mesa 5 — Notebook (ML)")
        ml_right_slots = [(483, 300), (575, 300), (667, 300)]
        self._draw_ml_slots(c, ml_right_slots, ["ML-4", "ML-5", "ML-6"], tx=437, ty=272, tw=276)

        # Table 6: PCs 07, 08, 09 (bottom-right)
        self._draw_table(c, 437, 398, 276, 86, "Mesa 6")
        self._draw_pc(c, 483, 427, "07")
        self._draw_pc(c, 575, 427, "08")
        self._draw_pc(c, 667, 427, "09")



    def _draw_table(self, c: tk.Canvas, x, y, w, h, label: str):
        """Draw a table rectangle."""
        c.create_rectangle(x, y, x + w, y + h, fill=FIELD, outline="#555", width=1)

    def _draw_bolsista(self, c: tk.Canvas, cx, cy):
        """Draw the Bolsista square station (visual reference only, unselectable)."""
        # Square bounding box (30x30 => r=15)
        c.create_rectangle(cx - 15, cy - 15, cx + 15, cy + 15, fill=BOLS_CLR, outline="#555", width=2)

    def _draw_pc(self, c: tk.Canvas, cx, cy, label: str):
        """Draw a PC station. Free machines have a bright ring; occupied are dark."""
        occupied = label in self._ocupadas
        fill = PC_OCCUPIED if occupied else PC_FREE
        outline = HOVER if occupied else PC_FREE_RING
        width = 2 if occupied else 3
        text_color = TEXT_LIGHT

        # For free PCs: draw a subtle outer ring to make them stand out
        if not occupied:
            c.create_oval(*_center(cx, cy, PC_R + 4),
                          fill="", outline=PC_FREE_RING, width=1)

        # Draw circle FIRST, then text ON TOP (correct z-order)
        cid = c.create_oval(*_center(cx, cy, PC_R), fill=fill, outline=outline, width=width)
        tid = c.create_text(cx, cy, text=label, fill=text_color,
                            font=("Arial", 10, "bold"))

        # All stations are selectable (occupied included)
        self._items[cid] = label
        self._items[tid] = label
        self._circles[cid] = {"fill": fill, "outline": outline}
        self._oval_to_text[cid] = tid

    def _draw_ml_slots(self, c: tk.Canvas, positions: list[tuple], labels: list[str], tx: int, ty: int, tw: int):
        """Draw 3 ML slot circles. Free slots have a bright ring; occupied are dark."""
        for i, (cx, cy) in enumerate(positions):
            label = labels[i]
            occupied = label in self._ocupadas
            
            # Backward compatibility with generic "ML" records
            if not occupied and self._ml_count > 0:
                occupied = True
                self._ml_count -= 1
                
            fill = ML_OCCUPIED if occupied else ML_FREE
            outline = HOVER if occupied else ML_FREE_RING
            width = 2 if occupied else 3
            text_color = TEXT_LIGHT

            # For free ML slots: draw a subtle outer ring
            if not occupied:
                c.create_oval(*_center(cx, cy, ML_SLOT_R + 4),
                              fill="", outline=ML_FREE_RING, width=1)

            cid = c.create_oval(*_center(cx, cy, ML_SLOT_R), fill=fill, outline=outline, width=width)
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
                self._cancel_timeout()
                self.result = machine
                self.destroy()

    def _on_key(self, event):
        """Keyboard shortcuts: digits select PC, M/L selects ML, Escape closes."""
        ch = event.char.upper()
        if ch == "\x1b":  # Escape
            self._on_close()
            return
        if ch in ("M", "L"):
            self._cancel_timeout()
            self.result = "ML"
            self.destroy()
            return
        if ch.isdigit():
            num = int(ch)
            if 1 <= num <= 9:
                label = f"{num:02}"
                self._cancel_timeout()
                self.result = label
                self.destroy()

    def _cancel_timeout(self):
        if getattr(self, "_timeout_job", None):
            try:
                if self.winfo_exists():
                    self.after_cancel(self._timeout_job)
            except Exception:
                pass
            self._timeout_job = None

    def _on_timeout(self):
        self._sem_maquina()

    def _sem_maquina(self):
        """Fallback: no machine."""
        self._cancel_timeout()
        self.result = "-"
        self.destroy()

    def _on_close(self):
        """User closed without selecting."""
        self._cancel_timeout()
        self.result = None
        self.destroy()


def selecionar_maquina(parent, ocupadas: list[str]) -> str | None:
    """Open the map dialog and return the selected machine string, or None if cancelled."""
    dlg = DialogoSelecaoMapa(parent, ocupadas)
    parent.wait_window(dlg)
    return dlg.result
