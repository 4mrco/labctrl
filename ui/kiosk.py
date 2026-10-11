"""
ui/kiosk.py — Modo Totem / Kiosk (autoatendimento) do LabCTRL.

O aluno digita a matrícula (6 dígitos, auto-envio), escolhe a máquina no mapa
(clique ou atalhos 1-9 / M / L) e a entrada é registrada. Quem já está dentro
tem a saída registrada na hora; clicar na máquina de uma única pessoa pede
confirmação inline. Aluno desconhecido informa o nome inline (sem modal) e
quem não tem matrícula usa o botão "Sem matrícula" (Aluno / Servidor).

Camada de UI pura: regras de negócio vêm de `core.services`, persistência de
`core.database`, geometria/cores do mapa canônicas do próprio Kiosk. Spec de referência:
kiosk-design-clean.md (sobrescrita: nome inline em vez de modal).

Executar a partir da raiz do projeto:  python3 -m ui.kiosk
"""

import math
import time
import tkinter as tk
from tkinter import font as tkfont

from core.config import TEMAS
from core.database import (
    buscar_aluno, buscar_registro_ativo, buscar_registro_por_id,
    buscar_registros_por_mes, finalizar_registro, inserir_aluno,
)
from core.services import (
    agora, gerar_id_servidor, load_config, load_layout, normalizar_nome,
    processar_entrada, reverter_acao, save_config,
)
from ui.dialogs import popup_sem_matricula, abrir_form_edicao

# ── Map Active Palette & Constants (Kiosk Canonical) ─────────────────────
PC_FREE       = "#1E4D8C"
PC_OCCUPIED   = "#1A1A2E"
ML_FREE       = "#1A6B3C"
ML_OCCUPIED   = "#0F2218"
PC_FREE_RING  = "#5B9BD5"
ML_FREE_RING  = "#4EC97B"
BOLS_CLR      = "#1e2b3c"
HOVER         = "#3A5F9A"
DESK_CLR      = "#444444"

MACHINE_R     = 20
IDLE_TIMEOUT_S = 60

# ── Theme ─────────────────────────────────────────────────────────────────
_T = TEMAS["default"]
BG, FG, FIELD, SELECT, ATIVO_BG = _T["bg"], _T["fg"], _T["field"], _T["select"], _T["ativo_bg"]
TXT_SEC = "#B5BAC1"
TXT_ACCENT = "#A8D8EA"
OUTLINE = "#555555"

# Paleta "dim" (cinza-azulado dessaturado) do mapa em repouso
DIM_TEXT = "#6B7280"
DIM_FREE, DIM_FREE_RING = "#2B303A", "#3C4352"
DIM_OCC, DIM_OCC_RING = "#1F2228", "#343944"
DIM_TABLE, DIM_OUTLINE = "#23252A", "#33363D"
DIM_DESK, DIM_BOLS = "#2B2D32", "#20262F"
DIM_BADGE, DIM_BADGE_OUT = "#2E333D", "#6B7280"

# Feedback / toasts (bg, fg | bg, borda)
FB_STYLES = {
    "idle":   (FIELD, TXT_SEC),
    "active": (ATIVO_BG, "#FFFFFF"),
    "error":  ("#7A2E26", "#FFFFFF"),
    "warn":   ("#6B4E16", "#FFE08A"),
}
TOAST_STYLES = {
    "success": (ATIVO_BG, "#5B9BD5"),
    "exit":    ("#6B2D3A", "#D4A0A0"),
    "error":   ("#C0392B", "#FF8A80"),
}
EXIT_BTN_BG = "#6B2D3A"
CANCEL_BTN_BG = "#2A2224"

WARN_SECONDS = 15
CONFIRM_TIMEOUT_S = 15        # confirmação de saída por clique expira sozinha
UNDO_WINDOW_S = 60            # só a última ação, e só dentro desta janela
DEBOUNCE_S = 1.0              # mesmo guard (1.0s) de registrar_entrada

BOLSISTA_FALLBACK = "Autoatendimento"   # usado se config não tiver ultimo_bolsista
SEM_MAQUINA = "-"
IDLE_MSG = "Digite sua matrícula para começar."
STEP_NAMES = ("Matrícula", "Nome", "Local")
DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo"]

# ── Planta Física (Carregada via layouts/<layout>.json e escalada 1.1x) ──
_LAYOUT_NAME = load_config().get("layout", "lab_informatica")
_LAYOUT = load_layout(_LAYOUT_NAME)
_S = 1.1
CANVAS_W = int(_LAYOUT["width"] * _S)
CANVAS_H = int(_LAYOUT["height"] * _S)
_tw, _th = _LAYOUT["table_size"]
TABLE_W, TABLE_H = int(_tw * _S), int(_th * _S)
TABLES = [(int(x * _S), int(y * _S)) for x, y in _LAYOUT["tables"]]
DESK_POLY = tuple(int(v * _S) for v in _LAYOUT["desk_poly"])
BOLSISTA_POS = (int(_LAYOUT["bolsista_pos"][0] * _S), int(_LAYOUT["bolsista_pos"][1] * _S))
PCS = {label: (int(pos[0] * _S), int(pos[1] * _S)) for label, pos in _LAYOUT["pcs"].items()}
ML_SLOTS = {label: (int(pos[0] * _S), int(pos[1] * _S)) for label, pos in _LAYOUT["ml_slots"].items()}
MACHINES = {**PCS, **ML_SLOTS}

HIT_R = 30            # hitbox de toque (60x60px, spec §7)
BADGE_R = 9           # Ø 18px

# Hover card (fontes maiores p/ leitura no totem)
CARD_W = 250
CARD_NAME_MAX = 30

IDLE, NAME, AWAITING, PANEL, BUSY = "idle", "name", "awaiting", "panel", "busy"
_STEP_OF_STATE = {IDLE: 0, NAME: 1, AWAITING: 2, PANEL: -1}   # BUSY mantém o passo

SLOT_H = 56
ANIM_STEPS = 8
ANIM_MS = 20


def _pick_font_family() -> str:
    try:
        if "Segoe UI" in tkfont.families():
            return "Segoe UI"
    except tk.TclError:
        pass
    return "Arial"


def _bbox(x, y, r):
    return x - r, y - r, x + r, y + r


def _mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class KioskFrame(tk.Frame):
    def __init__(self, parent, on_switch_mode=None):
        self.on_switch_mode = on_switch_mode
        super().__init__(parent, bg=BG)
        self._ff = _pick_font_family()
        self._state = IDLE
        self._step = 0
        self._pending: dict | None = None     # {"matricula", "nome", "novo", "tipo"}
        self._confirm_target: tuple[int, str] | None = None   # (rid, nome)
        self._deadline = 0.0
        self._on_expire = None
        self._clock_job = None
        self._deadline_job = None
        self._flash_job = None
        self._refresh_job = None
        self._toast_job = None
        self._toast_lbl: tk.Label | None = None
        self._focus_job = None
        self._undo_job = None
        self._undo_action: dict | None = None
        self._last_exit_ts = 0.0
        self._fb_text, self._fb_kind = IDLE_MSG, "idle"
        self._occupants: dict[str, list[tuple[str, str, int]]] = {}
        self._circles: dict[str, dict] = {}   # machine → {oval, fill, outline}
        self._hover_machine: str | None = None
        self._map_t = 0.0
        self._awaiting_ready_ts = 0.0                     # 0 = dim (repouso) … 1 = cor plena
        self._map_job = None
        self._orphan_warn_job = None
        self._slot_h = 0
        self._slot_job = None
        self._top_binds: list[tuple[str, str]] = []

        self._build_ui()
        self._apply_buttons()
        self._render_steps()
        self._tick_clock()
        self._refresh_map()
        self._focus_entry()
        self.after(150, self._focus_entry)
        self.after(400, self._focus_entry)

        top = self.winfo_toplevel()
        for seq, handler in (("<Key>", self._on_key),
                             ("<Control-z>", self._desfazer),
                             ("<Control-Z>", self._desfazer)):
            self._top_binds.append((seq, top.bind(seq, handler, add="+")))
        top.bind("<FocusIn>", lambda e: self._focus_entry() if self._state == IDLE else None, add="+")
        # setup_dialog() chama parent._from_dialog() ao fechar modais; só define se
        # a janela hospedeira (ex.: App) ainda não expôs o seu.
        if not hasattr(top, "_from_dialog"):
            top._from_dialog = self._return_focus_to_matricula

    # ── UI ────────────────────────────────────────────────────────────────

    def _f(self, size, weight="normal"):
        return (self._ff, size, weight)

    def _build_ui(self):
        # TOPO
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=30, pady=(18, 0))

        head = tk.Frame(top, bg=BG)
        head.pack(fill="x")
        head.columnconfigure(0, weight=1, uniform="h")
        head.columnconfigure(1, weight=0)
        head.columnconfigure(2, weight=1, uniform="h")
        tk.Label(head, text="BEM-VINDO(A)", bg=BG, fg=FG,
                 font=self._f(32, "bold")).grid(row=0, column=1)

        self.btn_switch = tk.Button(head, text="Dashboard ⇋", command=self.on_switch_mode,
                                    bg=BG, fg=DIM_TEXT, bd=0, highlightthickness=0,
                                    activebackground=BG, activeforeground=FG, cursor="hand2", font=self._f(10))
        if self.on_switch_mode:
            self.btn_switch.grid(row=0, column=0, sticky="w")
            
            self._switch_tooltip = None
            def _show_sw_tip(e):
                _hide_sw_tip()
                self._switch_tooltip = tk.Toplevel(self)
                self._switch_tooltip.overrideredirect(True)
                self._switch_tooltip.attributes("-topmost", True)
                tk.Label(self._switch_tooltip, text="Mudar para interface de dashboard",
                         bg="#333", fg="#FFF", font=("Segoe UI", 9), padx=6, pady=3).pack()
                self._switch_tooltip.geometry(f"+{e.x_root + 10}+{e.y_root + 10}")
            def _hide_sw_tip(e=None):
                if getattr(self, "_switch_tooltip", None):
                    self._switch_tooltip.destroy()
                    self._switch_tooltip = None
            self.btn_switch.bind("<Enter>", _show_sw_tip)
            self.btn_switch.bind("<Leave>", _hide_sw_tip)
            self.btn_switch.bind("<Button-1>", _hide_sw_tip)


        right_frame = tk.Frame(head, bg=BG)
        right_frame.grid(row=0, column=2, sticky="e")
        self._lbl_clock = tk.Label(right_frame, text="", bg=BG, fg=TXT_SEC, font=self._f(14))
        self._lbl_clock.pack(side="left")
        
        self.btn_menu = tk.Menubutton(right_frame, text="⋮", bg=BG, fg=FG, font=self._f(24, "bold"),
                                      activebackground=BG, activeforeground=TXT_ACCENT,
                                      cursor="hand2", bd=0, highlightthickness=0)
        self.btn_menu.pack(side="left", padx=(12, 0))
        
        self.menu_options = tk.Menu(self.btn_menu, tearoff=0, bg=FIELD, fg=FG, activebackground=SELECT, activeforeground=FG, font=self._f(12))
        self.btn_menu["menu"] = self.menu_options
        
        from core.services import load_config, save_config
        self.var_fs = tk.BooleanVar(value=load_config().get("kiosk_fullscreen", False))
        
        def _toggle_fs():
            cfg = load_config()
            cfg["kiosk_fullscreen"] = self.var_fs.get()
            save_config(cfg)
            top = self.winfo_toplevel()
            if self.var_fs.get():
                top.attributes("-fullscreen", True)
            else:
                top.attributes("-fullscreen", False)
                try:
                    top.attributes("-zoomed", True)
                except Exception:
                    try:
                        top.state("zoomed")
                    except Exception:
                        pass
                        
        self.menu_options.add_checkbutton(label="Auto tela-cheia", variable=self.var_fs, command=_toggle_fs)

        # Indicador de passos: Matrícula › Nome › Local
        steps = tk.Frame(top, bg=BG)
        steps.pack(pady=(8, 0))
        self._step_lbls: list[tk.Label] = []
        for i, nome in enumerate(STEP_NAMES):
            if i:
                tk.Label(steps, text="›", bg=BG, fg=DIM_TEXT,
                         font=self._f(14, "bold")).pack(side="left", padx=6)
            lbl = tk.Label(steps, text=f"{i + 1}  {nome}", font=self._f(11, "bold"),
                           padx=14, pady=4)
            lbl.pack(side="left")
            self._step_lbls.append(lbl)

        row2 = tk.Frame(top, bg=BG)
        row2.pack(pady=(14, 0))
        vcmd = (self.register(self._validate_matricula), "%P")
        self._entry = tk.Entry(row2, width=16, bd=0, highlightthickness=0,
                               bg=FIELD, fg=FG, insertbackground=FG,
                               readonlybackground=FIELD,
                               font=self._f(18, "bold"), justify="center",
                               validate="key", validatecommand=vcmd)
        self._entry.pack(ipady=6)
        self._entry.bind("<Return>", self._on_matricula_enter)
        self._entry.bind("<KP_Enter>", self._on_matricula_enter)
        self._entry.bind("<KeyRelease>", self._on_matricula_edited)
        self._entry.bind("<Button-1>", self._on_entry_click, add="+")
        self._entry.bind("<BackSpace>", self._on_entry_backspace)

        # Slot inline (altura animada 0 → SLOT_H): nome do aluno novo OU confirmação de saída
        self._slot_box = tk.Frame(top, bg=BG, height=0)
        self._slot_box.pack(fill="x")

        self._name_inner = tk.Frame(self._slot_box, bg=BG)
        tk.Label(self._name_inner, text="Insira seu nome:", bg=BG, fg=FG,
                 font=self._f(12, "bold")).pack(side="left")
        nvcmd = (self.register(lambda p: len(p) <= 60), "%P")
        self._name_entry = tk.Entry(self._name_inner, width=28, bd=0, highlightthickness=0,
                                    bg=FIELD, fg=FG, insertbackground=FG,
                                    font=self._f(16), validate="key",
                                    validatecommand=nvcmd)
        self._name_entry.pack(side="left", padx=(12, 12), ipady=5)
        self._name_entry.bind("<Return>", lambda e: [self._on_name_saved(), "break"][1])
        self._name_entry.bind("<KP_Enter>", lambda e: [self._on_name_saved(), "break"][1])
        self._name_entry.bind("<BackSpace>", self._on_name_backspace)
        self._btn_name = self._make_button(self._name_inner, "Salvar", self._on_name_saved,
                                           width=8, pady=6)
        self._btn_name.pack(side="left")

        self._panel_inner = tk.Frame(self._slot_box, bg=BG)

        # Feedback (largura fixa, centralizado, com fundo) — acima do mapa
        self._lbl_feedback = tk.Label(top, text="", width=70, bg=FIELD, fg=TXT_SEC,
                                      font=self._f(14, "bold"), pady=8)
        self._lbl_feedback.pack(pady=(8, 0))
        self._render_feedback()

        # BASE (empacotado antes do centro para reservar espaço)
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=30, pady=(5, 16))
        btn_frame = tk.Frame(bottom, bg=BG)
        btn_frame.pack(expand=True)
        self._btn_semmat = self._make_button(btn_frame, "Sem matrícula", self._on_sem_matricula,
                                             width=16)
        self._btn_semmat.pack(side="left", padx=(0, 10))
        self._btn_sem = self._make_button(btn_frame, "Escolher depois", self._sem_maquina, width=18)
        self._btn_sem.pack(side="left", padx=(0, 10))
        self._btn_clear = self._make_button(btn_frame, "Cancelar", self._reset, width=14,
                                            bg=CANCEL_BTN_BG)
        self._btn_clear.pack(side="left")
        self._btn_undo = self._make_button(bottom, "↶", self._desfazer, width=3)
        self._btn_undo.pack(side="right", padx=(0, 10))

        # CENTRO
        middle = tk.Frame(self, bg=BG)
        middle.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(middle, width=CANVAS_W, height=CANVAS_H,
                                bg=BG, highlightthickness=0)
        self.canvas.pack(expand=True)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._hide_card())
        self.canvas.bind("<ButtonRelease-1>", self._on_click)

        self._lbl_shortcuts = tk.Label(middle, text="", bg=BG, fg=DIM_TEXT,
                                       font=self._f(12), height=1, pady=8)
        self._lbl_shortcuts.pack(side="bottom", fill="x")

    def _make_button(self, parent, text, command, width=None, pady=14, bg=None):
        kw = {"width": width} if width else {}
        return tk.Button(parent, text=text, command=command, bd=0, relief="flat",
                         highlightthickness=0, bg=bg or FIELD, fg=FG,
                         activebackground=SELECT, activeforeground=FG,
                         disabledforeground="#6D7178",
                         font=self._f(12, "bold"), padx=24, pady=pady,
                         cursor="hand2", **kw)

    def _apply_buttons(self):
        """Habilita cada botão conforme o estado (fonte única da verdade)."""
        s = self._state
        self._btn_semmat.config(state="normal" if s == IDLE else "disabled")
        self._btn_sem.config(state="normal" if s == AWAITING else "disabled")
        self._btn_clear.config(state="normal" if s in (NAME, AWAITING) else "disabled")
        self._btn_undo.config(state="normal" if (s == IDLE and self._undo_action) else "disabled")
        
        if s == AWAITING:
            self._lbl_shortcuts.config(text="Atalhos: M ou L = Mesa Livre (ou clique no mapa)")
        else:
            self._lbl_shortcuts.config(text="")

    def _render_steps(self):
        cur = self._step
        for i, lbl in enumerate(self._step_lbls):
            if i == cur:
                lbl.config(text=f"{i + 1}  {STEP_NAMES[i]}", bg=ATIVO_BG, fg="#FFFFFF")
            elif 0 <= cur and i < cur:
                lbl.config(text=f"✓  {STEP_NAMES[i]}", bg=BG, fg=TXT_ACCENT)
            else:
                lbl.config(text=f"{i + 1}  {STEP_NAMES[i]}", bg=BG, fg=DIM_TEXT)

    # ── Clock ─────────────────────────────────────────────────────────────

    def _tick_clock(self):
        n = agora()
        self._lbl_clock.config(text=f"{n.strftime('%H:%M')} • {DIAS[n.weekday()]}")
        self._clock_job = self.after(1000, self._tick_clock)

    # ── Feedback ──────────────────────────────────────────────────────────

    def _render_feedback(self, remaining: int | None = None):
        text, kind = self._fb_text, self._fb_kind
        if remaining is not None and remaining <= WARN_SECONDS and kind != "error":
            text = f"{text}   •   {remaining}s"
            kind = "warn"
        bg, fg = FB_STYLES[kind]
        f_size = 12 if len(text) > 50 else 14
        self._lbl_feedback.config(text=text, bg=bg, fg=fg, font=self._f(f_size, "bold"))

    def _set_feedback(self, text, kind="idle"):
        if self._flash_job:
            self.after_cancel(self._flash_job)
            self._flash_job = None
        self._fb_text, self._fb_kind = text, kind
        self._render_feedback()

    def _flash_feedback(self, text, ms=3000):
        """Erro temporário; restaura a mensagem anterior depois."""
        if self._flash_job:
            self.after_cancel(self._flash_job)
        prev = (self._fb_text, self._fb_kind)
        self._fb_text, self._fb_kind = text, "error"
        self._render_feedback()

        def _back():
            self._flash_job = None
            self._fb_text, self._fb_kind = prev
            self._render_feedback()
        self._flash_job = self.after(ms, _back)

    def _busy(self, msg):
        """Feedback imediato antes de operações no banco (força o repaint)."""
        self._set_feedback(msg, "active")
        self.update_idletasks()

    # ── Deadline / countdown ──────────────────────────────────────────────

    def _start_deadline(self, on_expire, seconds: float | None = None):
        self._stop_deadline()
        self._deadline = time.monotonic() + (seconds if seconds is not None else IDLE_TIMEOUT_S)
        self._on_expire = on_expire
        self._tick_deadline()

    def _stop_deadline(self):
        if self._deadline_job:
            self.after_cancel(self._deadline_job)
            self._deadline_job = None

    def _tick_deadline(self):
        rem = self._deadline - time.monotonic()
        if rem <= 0:
            self._deadline_job = None
            cb, self._on_expire = self._on_expire, None
            if cb:
                cb()
            return
        self._render_feedback(math.ceil(rem))
        self._deadline_job = self.after(250, self._tick_deadline)

    # ── State ─────────────────────────────────────────────────────────────

    def _set_state(self, state):
        self._state = state
        if state in _STEP_OF_STATE:
            self._step = _STEP_OF_STATE[state]
        self._animate_map(1.0 if state == AWAITING else 0.0)
        self._apply_buttons()
        self._render_steps()

    # ── Validation (%P) ───────────────────────────────────────────────────

    def _validate_matricula(self, proposed: str) -> bool:
        if proposed != "" and not (proposed.isdigit() and len(proposed) <= 6):
            return False
        if len(proposed) == 6 and self._state == IDLE:
            self.after_idle(self._on_matricula_submitted)
        return True

    def _on_entry_click(self, event=None):
        if self._state == PANEL:
            self._reset()
        elif self._state == NAME:
            self._animate_slot(0)
            self._pending = None
            self._set_state(IDLE)
            self._set_feedback(IDLE_MSG, "idle")
        self._entry.config(state="normal")
        self._entry.focus_set()

    def _on_entry_backspace(self, event=None):
        if self._state == AWAITING:
            self._handle_awaiting_backspace()
            return "break"
        return None

    def _on_name_backspace(self, event=None):
        val = self._name_entry.get()
        if not val or self._name_entry.index("insert") == 0:
            self._animate_slot(0)
            self._pending = None
            self._set_state(IDLE)
            self._set_feedback(IDLE_MSG, "idle")
            self._entry.config(state="normal")
            mat = self._entry.get()
            if mat:
                self._entry.delete(len(mat) - 1, "end")
            self._entry.focus_set()
            self._entry.icursor("end")
            return "break"
        return None

    def _handle_awaiting_backspace(self):
        if getattr(self, "_orphan_warn_job", None):
            self.after_cancel(self._orphan_warn_job)
            self._orphan_warn_job = None
        self._stop_deadline()
        self._pending = None
        self._set_state(IDLE)
        self._set_feedback(IDLE_MSG, "idle")
        mat = self._entry.get()
        if len(mat) == 6:
            self._entry.delete(len(mat) - 1, "end")
        self._entry.focus_set()
        self._entry.icursor("end")

    def _on_matricula_edited(self, event=None):
        if self._state in (NAME, AWAITING) and self._pending:
            mat = self._entry.get().strip()
            if mat == self._pending.get("matricula"):
                return
            if len(mat) < 6 and self._state == AWAITING:
                self._handle_awaiting_backspace()
                return
            self._pending["matricula"] = mat
            if len(mat) == 6:
                aluno = buscar_aluno(mat)
                rid = buscar_registro_ativo(mat)
                if rid:
                    self._register_exit(rid, aluno[0] if aluno else mat)
                    self._reset()
                    self._refresh_map()
                elif aluno:
                    self._pending.update({"nome": aluno[0], "novo": False, "tipo": "aluno"})
                    if self._state == NAME:
                        self._animate_slot(0)
                    self._enter_awaiting()
                else:
                    self._pending.update({"nome": None, "novo": True, "tipo": "aluno"})
                    if self._state == AWAITING:
                        self._enter_name()

    def _on_matricula_enter(self, event=None):
        """Enter na matrícula: em NAME confirma o nome; em IDLE envia a matrícula."""
        if self._state == NAME:
            if not self._name_entry.get().strip():
                self._name_entry.focus_set()
                self._flash_feedback("Digite seu nome para continuar.")
            else:
                self._on_name_saved()
        else:
            self._on_matricula_submitted()
        return "break"


    # ── Inline slot animation (nome / confirmação) ────────────────────────

    def _show_slot(self, which: str):
        for key, frame in (("name", self._name_inner), ("panel", self._panel_inner)):
            if key == which:
                frame.place(relx=0.5, y=SLOT_H // 2, anchor="center")
            else:
                frame.place_forget()
        self._animate_slot(SLOT_H)

    def _animate_slot(self, target: int):
        if self._slot_job:
            self.after_cancel(self._slot_job)
            self._slot_job = None
        step = max(1, SLOT_H // ANIM_STEPS)

        def _step():
            if self._slot_h == target:
                self._slot_job = None
                return
            if self._slot_h < target:
                self._slot_h = min(target, self._slot_h + step)
            else:
                self._slot_h = max(target, self._slot_h - step)
            self._slot_box.config(height=self._slot_h)
            self._slot_job = self.after(ANIM_MS, _step)
        _step()

    # ── Map drawing ───────────────────────────────────────────────────────

    def _animate_map(self, target: float):
        if self._map_job:
            self.after_cancel(self._map_job)
            self._map_job = None
        if abs(self._map_t - target) < 1e-6:
            return
        delta = 1.0 / ANIM_STEPS

        def _step():
            if self._map_t < target:
                self._map_t = min(target, self._map_t + delta)
            else:
                self._map_t = max(target, self._map_t - delta)
            self._draw_map()
            if abs(self._map_t - target) > 1e-6:
                self._map_job = self.after(ANIM_MS, _step)
            else:
                self._map_job = None
        _step()

    def _load_occupants(self):
        """Máquina → [(nome, matrícula, rid)] a partir dos registros ATIVOS do mês."""
        occ: dict[str, list[tuple[str, str, int]]] = {}
        mes = agora().strftime("%m/%Y")
        for rid, nome, mat, _data, _ent, _sai, maq, _bol, status in buscar_registros_por_mes(mes):
            if status != "ATIVO" or not maq or maq == SEM_MAQUINA:
                continue
            occ.setdefault(maq, []).append((nome, mat or "", rid))
        # Compatibilidade: registros genéricos "ML" preenchem slots livres sequencialmente
        generic = occ.pop("ML", [])
        for label in ML_SLOTS:
            if generic and label not in occ:
                occ[label] = [generic.pop(0)]
        self._occupants = occ

    def _refresh_map(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        try:
            self._load_occupants()
        except Exception as e:  # noqa: BLE001
            self._flash_feedback(f"Erro ao ler ocupação: {e}")
        self._draw_map()
        self._refresh_job = self.after(5000, self._refresh_map)

    def _draw_map(self):
        c = self.canvas
        t = self._map_t
        c.delete("all")
        self._circles.clear()
        self._hover_machine = None

        c.create_polygon(*DESK_POLY, fill=_mix(DIM_DESK, DESK_CLR, t),
                         outline=_mix(DIM_OUTLINE, OUTLINE, t), width=1)
        bx, by = BOLSISTA_POS
        c.create_rectangle(bx - 15, by - 15, bx + 15, by + 15,
                           fill=_mix(DIM_BOLS, BOLS_CLR, t),
                           outline=_mix(DIM_OUTLINE, OUTLINE, t), width=2)

        for tx, ty in TABLES:
            c.create_rectangle(tx, ty, tx + TABLE_W, ty + TABLE_H,
                               fill=_mix(DIM_TABLE, FIELD, t),
                               outline=_mix(DIM_OUTLINE, OUTLINE, t), width=1)

        self._draw_legend()

        for label, (cx, cy) in PCS.items():
            self._draw_machine(label, label, cx, cy, MACHINE_R, PC_FREE, PC_OCCUPIED, PC_FREE_RING)
        for label, (cx, cy) in ML_SLOTS.items():
            self._draw_machine(label, "ML", cx, cy, MACHINE_R, ML_FREE, ML_OCCUPIED, ML_FREE_RING)

        # Badges por último (acima dos círculos)
        for label, people in self._occupants.items():
            pos = MACHINES.get(label)
            if pos and people:
                self._draw_badge(label, pos[0], pos[1], len(people))

    def _draw_legend(self):
        """Legenda (Livre / Ocupado / badge), dica de atalhos e estado vazio."""
        c = self.canvas
        t = self._map_t
        txt = _mix(DIM_TEXT, TXT_SEC, t)
        x, y = 76, 24
        c.create_oval(*_bbox(x + 8, y, 8), fill=_mix(DIM_FREE, PC_FREE, t),
                      outline=_mix(DIM_FREE_RING, PC_FREE_RING, t), width=2)
        c.create_text(x + 24, y, text="Livre", anchor="w", fill=txt, font=self._f(11))
        x2 = x + 100
        c.create_oval(*_bbox(x2 + 8, y, 8), fill=_mix(DIM_OCC, PC_OCCUPIED, t),
                      outline=_mix(DIM_OCC_RING, HOVER, t), width=2)
        c.create_text(x2 + 24, y, text="Ocupado", anchor="w", fill=txt, font=self._f(11))
        x3 = x2 + 130
        # Legend for (n) people and empty lab removed per user request

    def _draw_machine(self, label, text, cx, cy, r, free_fill, occ_fill, free_ring):
        c = self.canvas
        t = self._map_t
        occupied = label in self._occupants
        if occupied:
            fill = _mix(DIM_OCC, occ_fill, t)
            outline = _mix(DIM_OCC_RING, HOVER, t)
        else:
            fill = _mix(DIM_FREE, free_fill, t)
            outline = _mix(DIM_FREE_RING, free_ring, t)
        width = 2 if occupied else 3
        if not occupied:
            c.create_oval(*_bbox(cx, cy, r + 4), fill="", outline=outline, width=1)
        oval = c.create_oval(*_bbox(cx, cy, r), fill=fill, outline=outline, width=width)
        c.create_text(cx, cy, text=text, fill=_mix(DIM_TEXT, FG, t), font=self._f(10, "bold"))
        self._circles[label] = {"oval": oval, "fill": fill, "outline": outline}

    def _draw_badge(self, label, cx, cy, count):
        c = self.canvas
        t = self._map_t
        bx, by = cx + 14, cy - 14
        c.create_oval(*_bbox(bx, by, BADGE_R), fill=_mix(DIM_BADGE, ATIVO_BG, t),
                      outline=_mix(DIM_BADGE_OUT, "#FFFFFF", t), width=1)
        c.create_text(bx, by, text=str(count) if count < 10 else "9+",
                      fill=_mix(DIM_TEXT, FG, t), font=self._f(9, "bold"))

    # ── Hover / card ──────────────────────────────────────────────────────

    def _machine_at(self, x, y) -> str | None:
        """Máquina mais próxima dentro do raio de toque (HIT_R), ou None."""
        best, best_d = None, HIT_R
        for label, (cx, cy) in MACHINES.items():
            d = math.hypot(x - cx, y - cy)
            if d <= best_d:
                best, best_d = label, d
        return best

    def _is_interactive(self, label) -> bool:
        if self._state == AWAITING:
            return True
        # Em repouso: máquina com exatamente 1 pessoa → clique pede confirmação de saída
        return self._state == IDLE and len(self._occupants.get(label, [])) == 1

    def _on_motion(self, event):
        label = self._machine_at(event.x, event.y)
        if label == self._hover_machine:
            return
        self._unhighlight()
        self._hover_machine = label
        if label is None:
            self.canvas.config(cursor="")
            self._hide_card()
            return
        if self._is_interactive(label):
            self.canvas.itemconfigure(self._circles[label]["oval"], fill=HOVER, outline=FG)
            self.canvas.config(cursor="hand2")
        else:
            self.canvas.config(cursor="")
        if self._occupants.get(label):
            self._show_card(label)
        else:
            self.canvas.delete("card")

    def _unhighlight(self):
        info = self._circles.get(self._hover_machine) if self._hover_machine else None
        if info:
            self.canvas.itemconfigure(info["oval"], fill=info["fill"], outline=info["outline"])

    def _hide_card(self):
        self.canvas.delete("card")
        self._unhighlight()
        self._hover_machine = None

    def _show_card(self, label):
        c = self.canvas
        c.delete("card")
        people = self._occupants[label]
        shown = people[:2]
        extra = len(people) - len(shown)
        n = len(people)
        title_txt = f"{'Mesa Livre' if label.startswith('ML') else 'PC ' + label} — {n} Ocupante{'s' if n != 1 else ''}"
        h = 40 + 52 * len(shown) + (22 if extra > 0 else 0)

        cx, cy = MACHINES[label]
        x0 = cx + 15
        if x0 + CARD_W > CANVAS_W:        # inversão: abre para a esquerda
            x0 = cx - 15 - CARD_W
        y0 = max(2, cy - 15 - h)
        x1, y1 = x0 + CARD_W, y0 + h

        c.create_rectangle(x0, y0, x1, y1, fill=FIELD, outline=SELECT, width=2, tags="card")
        c.create_text(x0 + 12, y0 + 16, text=title_txt, fill=FG, anchor="w",
                      font=self._f(11, "bold"), tags="card")
        c.create_line(x0 + 1, y0 + 30, x1 - 1, y0 + 30, fill=SELECT, tags="card")
        y = y0 + 48
        for nome, mat, _rid in shown:
            if len(nome) > CARD_NAME_MAX:
                nome = nome[:CARD_NAME_MAX - 1] + "…"
            c.create_text(x0 + 12, y, text=nome, fill=FG, anchor="w",
                          font=self._f(11), tags="card")
            c.create_text(x0 + 12, y + 18, text=f"Matrícula: {mat or '—'}", fill=TXT_ACCENT,
                          anchor="w", font=self._f(10), tags="card")
            y += 52
        if extra > 0:
            c.create_text(x0 + 12, y - 12, text=f"+ {extra} outro{'s' if extra != 1 else ''}",
                          fill=TXT_SEC, anchor="w", font=self._f(10), tags="card")
        c.tag_raise("card")

    # ── Toast (overlay in-window) ─────────────────────────────────────────

    def _toast(self, msg, kind="success", ms=3500):
        bg, border = TOAST_STYLES[kind]
        if self._toast_lbl is None:
            self._toast_lbl = tk.Label(self, fg="#FFFFFF", font=self._f(22, "bold"),
                                       padx=40, pady=18, highlightthickness=3)
        self._toast_lbl.config(text=msg, bg=bg, highlightbackground=border,
                               highlightcolor=border)
        self._toast_lbl.place(in_=self.canvas, relx=0.5, rely=1.0, y=-24, anchor="s")
        self._toast_lbl.lift()
        self._toast_base = msg
        self._toast_deadline = ms / 1000
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._tick_toast()

    def _tick_toast(self):
        if self._toast_lbl is None:
            return
        remaining = int(self._toast_deadline)
        self._toast_lbl.config(text=f"{self._toast_base}  •  {remaining}s")
        self._toast_deadline -= 1
        if self._toast_deadline > 0:
            self._toast_job = self.after(1000, self._tick_toast)
        else:
            self._toast_job = self.after(0, self._hide_toast)

    def _hide_toast(self):
        self._toast_job = None
        if self._toast_lbl is not None:
            self._toast_lbl.place_forget()
            self._toast_lbl.config(text="")

    # ── Undo (somente a última ação, dentro de UNDO_WINDOW_S) ─────────────

    def _push_undo(self, acao: dict):
        self._undo_action = acao
        if self._undo_job:
            self.after_cancel(self._undo_job)
        self._undo_job = self.after(UNDO_WINDOW_S * 1000, self._expire_undo)
        self._apply_buttons()

    def _expire_undo(self):
        self._undo_job = None
        self._undo_action = None
        self._apply_buttons()

    def _desfazer(self, event=None):
        if self._state != IDLE or not self._undo_action:
            return "break" if event else None
        try:
            msg = reverter_acao(self._undo_action)
        except Exception as e:  # noqa: BLE001
            self._flash_feedback(f"Erro ao desfazer: {e}")
            return "break" if event else None
        if self._undo_job:
            self.after_cancel(self._undo_job)
            self._undo_job = None
        self._undo_action = None
        self._apply_buttons()
        self._toast(msg, "success")
        self._refresh_map()
        return "break" if event else None

    # ── Flow ──────────────────────────────────────────────────────────────

    def _focus_entry(self):
        try:
            self._entry.focus_set()
        except tk.TclError:
            pass

    def _bolsista(self) -> str:
        try:
            return load_config().get("ultimo_bolsista") or BOLSISTA_FALLBACK
        except Exception:  # noqa: BLE001
            return BOLSISTA_FALLBACK

    def _on_matricula_submitted(self):
        if self._state != IDLE:
            return
        mat = self._entry.get().strip()
        if mat == "":
            self._on_sem_matricula()
            return
        if len(mat) != 6:
            self._flash_feedback("A matrícula deve ter 6 dígitos.")
            return
        self._set_state(BUSY)
        self._busy("Verificando matrícula…")
        try:
            self._handle_matricula(mat)
        except Exception as e:  # noqa: BLE001
            self._reset()
            self._flash_feedback(f"Erro: {e}")

    def _handle_matricula(self, mat: str):
        aluno = buscar_aluno(mat)

        # Já dentro → saída imediata (sem mapa, sem confirmação)
        rid = buscar_registro_ativo(mat)
        if rid:
            self._register_exit(rid, aluno[0] if aluno else mat)
            self._reset()
            self._refresh_map()
            return

        if aluno:
            self._pending = {"matricula": mat, "nome": aluno[0], "novo": False, "tipo": "aluno"}
            self._enter_awaiting()
        else:
            self._pending = {"matricula": mat, "nome": None, "novo": True, "tipo": "aluno"}
            self._enter_name()

    def _register_exit(self, rid: int, nome: str):
        finalizar_registro(rid, agora().strftime("%H:%M"))
        self._last_exit_ts = time.monotonic()
        self._push_undo({"tipo": "saida", "rid": rid, "nome": nome})
        self._toast(f"Saída registrada: {nome}", "exit")

    # ── Aluno desconhecido: nome inline ───────────────────────────────────

    def _enter_name(self):
        """Matrícula desconhecida: pede o nome inline (linha desliza para baixo)."""
        self._set_state(NAME)
        self._set_feedback("Matrícula não cadastrada. Digite seu nome para continuar.", "active")
        self._name_entry.delete(0, "end")
        self._show_slot("name")
        self._name_entry.focus_set()
        self._start_deadline(self._reset)

    def _on_name_saved(self):
        if self._state != NAME or not self._pending:
            return
        nome = normalizar_nome(self._name_entry.get().strip())
        if not nome:
            self._flash_feedback("Digite seu nome para continuar.")
            return
        mat = self._entry.get().strip()
        if mat == "":
            self._on_sem_matricula()
            return
        if len(mat) != 6:
            self._flash_feedback("A matrícula deve ter 6 dígitos.")
            return
        try:
            existente = buscar_aluno(mat)
            self._pending["matricula"] = mat
            if existente:                       # matrícula corrigida já cadastrada → prevalece
                self._pending.update(nome=existente[0], novo=False)
                if buscar_registro_ativo(mat):
                    ja = existente[0]
                    self._reset()
                    self._flash_feedback(f"{ja} já está dentro do laboratório.")
                    return
            else:
                self._pending["nome"] = nome
        except Exception as e:  # noqa: BLE001
            self._reset()
            self._flash_feedback(f"Erro: {e}")
            return
        self._animate_slot(0)
        self._enter_awaiting()
        self._return_focus_to_matricula()

    def _return_focus_to_matricula(self):
        """Retorna foco ao campo de matrícula após modais liberarem o grab."""
        if self._focus_job:
            self.after_cancel(self._focus_job)

        def _check():
            try:
                if self.winfo_toplevel().grab_current():
                    self._focus_job = self.after(50, _check)
                else:
                    self._focus_job = None
                    self._entry.focus_set()
            except tk.TclError:
                pass
        self._focus_job = self.after(50, _check)

    # ── Sem matrícula (Aluno / Servidor) ──────────────────────────────────

    def _on_sem_matricula(self):
        if self._state != IDLE:
            return
        self._set_state(BUSY)
        try:
            res = popup_sem_matricula(self.winfo_toplevel())
        except Exception as e:  # noqa: BLE001
            self._reset()
            self._flash_feedback(f"Erro: {e}")
            return
        if not res:
            self._reset()
            return
        nome, tipo = res
        self._busy("Verificando cadastro…")
        try:
            if tipo == "Servidor":
                mat = gerar_id_servidor(nome)
                rid = buscar_registro_ativo(mat)
                if rid:                          # servidor já dentro → saída imediata
                    self._register_exit(rid, nome)
                    self._reset()
                    self._refresh_map()
                    return
                self._pending = {"matricula": mat, "nome": nome,
                                 "novo": buscar_aluno(mat) is None, "tipo": "servidor"}
            else:
                self._pending = {"matricula": None, "nome": nome, "novo": False, "tipo": "aluno"}
        except Exception as e:  # noqa: BLE001
            self._reset()
            self._flash_feedback(f"Erro: {e}")
            return
        self._enter_awaiting()

    # ── Escolha da máquina ────────────────────────────────────────────────

    def _enter_awaiting(self):
        self._set_state(AWAITING)
        import time
        self._awaiting_ready_ts = time.monotonic() + 0.5
        self._entry.config(state="normal")
        self._entry.focus_set()                 # teclas de atalho chegam via toplevel
        p = self._pending
        if p["matricula"]:
            msg = f"Matrícula identificada: {p['nome']}. Escolha o local."
        else:
            msg = f"Olá, {p['nome']}! Escolha o local."

        cfg = load_config()
        orfaos = cfg.get("orfaos_sem_saida", [])
        if p.get("matricula") and p["matricula"] in orfaos:
            self._set_feedback("Atenção: você não registrou saída da última vez. Lembre-se ao sair!", "warn")
            def _restore_msg():
                self._orphan_warn_job = None
                if self._state == AWAITING:
                    self._set_feedback(msg, "active")
            if getattr(self, "_orphan_warn_job", None):
                self.after_cancel(self._orphan_warn_job)
            self._orphan_warn_job = self.after(3000, _restore_msg)
        else:
            self._set_feedback(msg, "active")

        self._start_deadline(lambda: self._on_machine_selected(SEM_MAQUINA))

    def _sem_maquina(self):
        if self._state == AWAITING:
            self._on_machine_selected(SEM_MAQUINA)

    def _on_click(self, event):
        label = self._machine_at(event.x, event.y)
        if not label:
            return
        if self._state == AWAITING:
            self._on_machine_selected(label)
        elif self._state == IDLE:
            people = self._occupants.get(label, [])
            if people:
                self._open_occupant_panel(label)

    def _on_key(self, event):
        """Atalhos (somente AWAITING): M/L → mesa livre, 1-9 → PC, BackSpace → volta para IDLE."""
        if self._state != AWAITING:
            return
        if event.keysym == "BackSpace":
            self._handle_awaiting_backspace()
            return "break"
        ch = (event.char or "").upper()
        if ch in ("M", "L"):
            livre = next((s for s in ML_SLOTS if s not in self._occupants), "ML")
            self._on_machine_selected(livre)
            return "break"
        elif ch.isdigit() and 1 <= int(ch) <= 9:
            self._on_machine_selected(f"{int(ch):02}")
            return "break"


    def _on_machine_selected(self, machine: str):
        if self._state != AWAITING or not self._pending:
            return
        import time
        if time.monotonic() < self._awaiting_ready_ts:
            return
        self._stop_deadline()
        self._set_state(BUSY)
        self._busy("Registrando entrada…")
        p = self._pending
        try:
            if p["novo"]:
                inserir_aluno(p["matricula"], p["nome"], p["tipo"])
            res = processar_entrada(p["matricula"], p["nome"], machine, self._bolsista())
            if res["status"] == "ja_ativo":
                self._toast(f"{p['nome']} já está dentro do laboratório.", "error")
            else:
                self._push_undo({"tipo": "entrada", "rid": res["rid"], "nome": p["nome"]})
                if p.get("matricula"):
                    cfg = load_config()
                    orfaos = cfg.get("orfaos_sem_saida", [])
                    if p["matricula"] in orfaos:
                        orfaos.remove(p["matricula"])
                        cfg["orfaos_sem_saida"] = orfaos
                        save_config(cfg)
                destino = "sem máquina" if machine == SEM_MAQUINA else (
                    "Mesa Livre" if machine.startswith("ML") else f"PC {machine}")
                self._toast(f"Entrada registrada: {p['nome']} ({destino}) às {res['hora']}")
        except Exception as e:  # noqa: BLE001
            self._reset()
            self._flash_feedback(f"Erro ao registrar: {e}")
            return
        self._reset()
        self._refresh_map()

    # ── Saída por clique na máquina (confirmação inline) ──────────────────

    def _open_occupant_panel(self, label: str):
        if time.monotonic() - self._last_exit_ts < DEBOUNCE_S:
            return
        
        people = self._occupants.get(label, [])
        if not people:
            return

        for widget in self._panel_inner.winfo_children():
            widget.destroy()

        self._confirm_target = label
        self._set_state(PANEL)
        
        lbl_title = tk.Label(self._panel_inner, text=f"{'Mesa Livre' if label.startswith('ML') else 'PC ' + label}:", 
                             bg=BG, fg=FG, font=self._f(12, "bold"))
        lbl_title.pack(side="left", padx=(0, 16))

        for nome, mat, rid in people:
            frame_person = tk.Frame(self._panel_inner, bg=FIELD, padx=8, pady=4)
            frame_person.pack(side="left", padx=4)
            
            nome_disp = nome if len(nome) <= 15 else nome[:14] + "…"
            tk.Label(frame_person, text=nome_disp, bg=FIELD, fg=FG, font=self._f(11)).pack(side="left", padx=(0, 8))
            
            btn_edit = tk.Button(frame_person, text="Editar", bg=SELECT, fg=FG, bd=0, font=self._f(10),
                                 command=lambda r=rid: self._edit_record(r), cursor="hand2")
            btn_edit.pack(side="left", padx=2)
            
            btn_exit = tk.Button(frame_person, text="Saída", bg=EXIT_BTN_BG, fg="#FFFFFF", bd=0, font=self._f(10),
                                 command=lambda r=rid, n=nome: self._confirm_exit_record(r, n), cursor="hand2")
            btn_exit.pack(side="left", padx=2)

        btn_back = self._make_button(self._panel_inner, "Fechar", self._reset, width=8, pady=4, bg=CANCEL_BTN_BG)
        btn_back.pack(side="left", padx=(12, 0))

        self._entry.config(state="readonly")
        self._show_slot("panel")
        self._set_feedback("Selecione uma ação para o ocupante.", "active")
        self._start_deadline(self._reset, CONFIRM_TIMEOUT_S)

    def _edit_record(self, rid):
        self._stop_deadline()
        
        def _on_success(undo_payload, status_msg, erro):
            if erro:
                self._flash_feedback(f"Erro ao editar: {erro}")
            else:
                if undo_payload:
                    self._push_undo(undo_payload)
                self._toast(status_msg, "success")
            self._reset()
            self._refresh_map()

        abrir_form_edicao(self.winfo_toplevel(), rid, _on_success)

    def _confirm_exit_record(self, rid, nome):
        if time.monotonic() - self._last_exit_ts < DEBOUNCE_S:
            return
        self._stop_deadline()
        self._set_state(BUSY)
        self._busy("Registrando saída…")
        try:
            reg = buscar_registro_por_id(rid)
            if not reg or reg[8] != "ATIVO":
                self._reset()
                self._flash_feedback(f"{nome} já registrou saída.")
                self._refresh_map()
                return
            self._register_exit(rid, nome)
        except Exception as e:  # noqa: BLE001
            self._reset()
            self._flash_feedback(f"Erro ao registrar saída: {e}")
            return
        self._reset()
        self._refresh_map()

    # ── Reset ─────────────────────────────────────────────────────────────

    def _reset(self):
        """Volta ao repouso: limpa campos, estado, timers e foco."""
        if getattr(self, "_orphan_warn_job", None):
            self.after_cancel(self._orphan_warn_job)
            self._orphan_warn_job = None
        self._stop_deadline()
        self._on_expire = None
        self._pending = None
        self._confirm_target = None
        self._set_state(IDLE)
        self._entry.config(state="normal")
        self._entry.delete(0, "end")
        self._name_entry.delete(0, "end")
        self._animate_slot(0)
        self._unhighlight()
        self._hover_machine = None
        self.canvas.config(cursor="")
        self.canvas.delete("card")
        self._set_feedback(IDLE_MSG, "idle")
        self._focus_entry()

    def destroy(self):
        for name in ("_clock_job", "_deadline_job", "_flash_job", "_refresh_job",
                     "_toast_job", "_map_job", "_slot_job", "_focus_job", "_undo_job",
                     "_orphan_warn_job"):
            job = getattr(self, name, None)
            if job:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        try:
            top = self.winfo_toplevel()
            for seq, fid in self._top_binds:
                top.unbind(seq, fid)
        except tk.TclError:
            pass
        super().destroy()


def main():
    from core.database import init_db
    init_db()
    root = tk.Tk()
    root.title("LabCTRL — Kiosk")
    root.geometry("1200x800")
    root.configure(bg=BG)
    app = KioskFrame(root)
    app.pack(fill="both", expand=True)
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
    root.mainloop()


if __name__ == "__main__":
    main()
