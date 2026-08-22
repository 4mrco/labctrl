"""
Controle de Laboratório
"""

import sqlite3
import csv
import json
import os
import logging
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from collections import defaultdict

import tkinter as tk
from tkinter import ttk, messagebox

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    filename="lab.log",
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE    = os.path.join(BASE_DIR, "config.json")
DB_FILE        = os.path.join(BASE_DIR, "lab.db")
SCHEMA_VERSION = 3

BOLSISTAS_INICIAIS = [
    "Francisco Jônathan Lima Paula", "Raimundo Nonato Odilson",
    "Antônio Francisco Gomes de Oliveira", "Pedro Carolino Neto",
    "Gustavo Emanoel Dutra", "Antonio Martins Neto",
    "Francisco Breno Gomes Melo", "Samara Nascimento de Lima",
    "Sabrina Nascimento de Lima", "Anna Alícya Magalhães Cruz",
    "João Pedro Batista Barbosa", "Pedro Rian Martins Fialho",
    "Vinícius Cavalcante Marques", "Luiz Miguel Rodrigues de Souza",
    "Caio Bendó de Lima", "Andrey Barbosa",
    "Edmilson Felipe Pereira Almeida", "Mateus Fernandes Sousa",
    "João Pedro Sousa Marques", "Daniel de Araujo", "Marco Aurelio",
]

TEMAS = {
    "dark":  {"bg": "#1E1F22", "fg": "#FFFFFF", "field": "#313338", "select": "#404249",
              "ativo_bg": "#2A3B5A", "row_a": "#2B2D31", "row_b": "#25272B"},
    "light": {"bg": "#F5F5F5", "fg": "#000000", "field": "#FFFFFF", "select": "#E0E0E0",
              "ativo_bg": "#D0E0F0", "row_a": "#FFFFFF", "row_b": "#F8F8F8"},
}

COL_NAMES = ("Nome", "Matrícula", "Entrada", "Saída", "Tempo", "Máquina")


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"theme": "light", "exported_months": [], "ultimo_bolsista": None, "open_export_folder": True}
    cfg = json.load(open(CONFIG_FILE, "r"))
    cfg.setdefault("exported_months", [])
    cfg.setdefault("ultimo_bolsista", None)
    cfg.setdefault("open_export_folder", True)
    return cfg


def save_config(cfg: dict) -> None:
    json.dump(cfg, open(CONFIG_FILE, "w"))


# ─────────────────────────────────────────────
# EXPORT UTILITIES
# ─────────────────────────────────────────────

EXPORT_DIR = os.path.join(BASE_DIR, "exports")


def get_export_dir() -> str:
    """Get the base export directory, creating it if needed."""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    return EXPORT_DIR


def get_month_export_dir(mes: str | None = None) -> str:
    """Get the export directory for a specific month (YYYY-MM format).

    Creates the directory if it doesn't exist.
    """
    if mes is None:
        mes = agora().strftime("%Y-%m")
    month_dir = os.path.join(EXPORT_DIR, mes)
    os.makedirs(month_dir, exist_ok=True)
    return month_dir


# ─────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error("Erro no banco: %s", e)
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

            CREATE TABLE IF NOT EXISTS alunos (
                matricula TEXT PRIMARY KEY,
                nome      TEXT,
                tipo      TEXT DEFAULT 'aluno'
            );
            CREATE TABLE IF NOT EXISTS registros (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT,
                nome      TEXT,
                data      TEXT,
                entrada   TEXT,
                saida     TEXT,
                maquina   TEXT,
                bolsista  TEXT,
                status    TEXT,
                ignorar   INTEGER DEFAULT 0,
                exportado INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS bolsistas (nome TEXT PRIMARY KEY);

            CREATE INDEX IF NOT EXISTS idx_registros_data
                ON registros(data);
            CREATE INDEX IF NOT EXISTS idx_registros_matricula
                ON registros(matricula);
        """)
        for nome in BOLSISTAS_INICIAIS:
            c.execute("INSERT OR IGNORE INTO bolsistas VALUES (?)", (nome,))
        _migrar_schema(c)


def _migrar_schema(c) -> None:
    row = c.execute("SELECT version FROM schema_version").fetchone()
    versao_atual = row[0] if row else 0
    if versao_atual < 2:
        try:
            c.execute("ALTER TABLE alunos ADD COLUMN tipo TEXT DEFAULT 'aluno'")
        except Exception:
            pass
    if versao_atual < 3:
        try:
            c.execute("ALTER TABLE registros ADD COLUMN exportado INTEGER DEFAULT 0")
        except Exception:
            pass
    if versao_atual < SCHEMA_VERSION:
        c.execute("DELETE FROM schema_version")
        c.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))


# ── Alunos ──

def buscar_aluno(matricula: str) -> tuple | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT nome, tipo FROM alunos WHERE matricula=?", (matricula,)
        ).fetchone()


def inserir_aluno(matricula: str, nome: str, tipo: str = "aluno") -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO alunos VALUES (?,?,?)", (matricula, nome, tipo))


def buscar_todos_alunos() -> list[tuple]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT matricula, nome, tipo FROM alunos ORDER BY nome"
        ).fetchall()


def atualizar_aluno(matricula: str, novo_nome: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE alunos SET nome=? WHERE matricula=?", (novo_nome, matricula))
        conn.execute("UPDATE registros SET nome=? WHERE matricula=?", (novo_nome, matricula))


def deletar_aluno(matricula: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM alunos WHERE matricula=?", (matricula,))


# ── Registros ──

def inserir_registro(matricula, nome, data, hora, maquina, bolsista) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO registros
               (matricula,nome,data,entrada,maquina,bolsista,status)
               VALUES (?,?,?,?,?,?,'ATIVO')""",
            (matricula, nome, data, hora, maquina, bolsista),
        )


def finalizar_registro(rid: int, hora_saida: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE registros SET saida=?, status='FINALIZADO' WHERE id=?",
            (hora_saida, rid),
        )


def buscar_registro_ativo(matricula: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id FROM registros
               WHERE matricula=? AND status='ATIVO'
               ORDER BY id DESC LIMIT 1""",
            (matricula,),
        ).fetchone()
    return row[0] if row else None


def buscar_registro_por_id(rid: int) -> tuple | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT id,nome,matricula,data,entrada,saida,maquina,bolsista,status
               FROM registros WHERE id=?""",
            (rid,),
        ).fetchone()


def atualizar_registro(rid: int, data: str, entrada: str, saida: str, maquina: str) -> None:
    status = "FINALIZADO" if saida else "ATIVO"
    with get_conn() as conn:
        conn.execute(
            "UPDATE registros SET data=?,entrada=?,saida=?,maquina=?,status=? WHERE id=?",
            (data, entrada, saida or None, maquina, status, rid),
        )


def deletar_registro(rid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM registros WHERE id=?", (rid,))


def restaurar_registro_db(campos: dict) -> None:
    """Recria um registro deletado com os campos originais, incluindo o id original."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO registros
               (id,matricula,nome,data,entrada,saida,maquina,bolsista,status)
               VALUES (:id,:matricula,:nome,:data,:entrada,:saida,:maquina,:bolsista,:status)""",
            campos,
        )


def buscar_registros_por_mes(mes: str) -> list[tuple]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT id,nome,matricula,data,entrada,saida,maquina,bolsista,status
               FROM registros WHERE data LIKE ? ORDER BY id DESC""",
            (f"%/{mes}",),
        ).fetchall()


def buscar_registros_orfaos() -> list[tuple]:
    hoje = datetime.now().strftime("%d/%m/%Y")
    with get_conn() as conn:
        return conn.execute(
            """SELECT id, nome, matricula, data, entrada FROM registros
               WHERE status='ATIVO' AND data != ?""",
            (hoje,),
        ).fetchall()


def contar_registros_hoje(hoje: str) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM registros WHERE data=?", (hoje,)
        ).fetchone()[0]


def contar_ativos() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM registros WHERE status='ATIVO'"
        ).fetchone()[0]


def buscar_meses() -> list[str]:
    with get_conn() as conn:
        datas = [r[0] for r in conn.execute(
            "SELECT DISTINCT data FROM registros"
        ).fetchall()]
    meses = sorted(set(d[3:] for d in datas), reverse=True)
    return meses or [datetime.now().strftime("%m/%Y")]


# ── Export queries ──

def buscar_export_mes(mes: str) -> list[tuple]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT data,entrada,saida,nome,matricula,maquina,bolsista
               FROM registros WHERE data LIKE ? ORDER BY data, entrada""",
            (f"%/{mes}",),
        ).fetchall()


def buscar_export_dia(dia: str) -> list[tuple]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT data,entrada,saida,nome,matricula,maquina,bolsista
               FROM registros WHERE data=? ORDER BY entrada""",
            (dia,),
        ).fetchall()


def buscar_export_ontem() -> tuple[list[tuple], str]:
    """Retorna (dados, label_data) do dia anterior."""
    ontem = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
    with get_conn() as conn:
        dados = conn.execute(
            """SELECT data,entrada,saida,nome,matricula,maquina,bolsista
               FROM registros WHERE data=? ORDER BY entrada""",
            (ontem,),
        ).fetchall()
    return dados, ontem


def buscar_export_semana(datas: list[str]) -> list[tuple]:
    ph = ",".join("?" * len(datas))
    with get_conn() as conn:
        return conn.execute(
            f"""SELECT data,entrada,saida,nome,matricula,maquina,bolsista
                FROM registros WHERE data IN ({ph}) ORDER BY data, entrada""",
            datas,
        ).fetchall()


# ── Bolsistas ──

def buscar_bolsistas() -> list[str]:
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT nome FROM bolsistas").fetchall()]


def inserir_bolsista(nome: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO bolsistas VALUES (?)", (nome,))


def deletar_bolsista(nome: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM bolsistas WHERE nome=?", (nome,))


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def agora() -> datetime:
    return datetime.now()


def calcular_tempo(entrada: str, saida: str, data: str) -> str:
    fmt = "%d/%m/%Y %H:%M"
    try:
        delta = (
            datetime.strptime(f"{data} {saida}", fmt)
            - datetime.strptime(f"{data} {entrada}", fmt)
        )
        m = int(delta.total_seconds() // 60)
        return f"{m // 60:02}:{m % 60:02}"
    except Exception:
        return ""


def mes_anterior() -> str:
    hoje = date.today()
    if hoje.month == 1:
        return f"12/{hoje.year - 1}"
    return f"{hoje.month - 1:02}/{hoje.year}"


PORTUGUESE_CONNECTORS = {"da", "de", "do", "das", "dos", "e"}


def normalizar_nome(nome: str) -> str:
    """Normalize a name: capitalize first letter of each word, keep connectors lowercase."""
    if not nome:
        return nome
    # Remove extra spaces and split
    palavras = nome.strip().split()
    if not palavras:
        return nome
    resultado = []
    for i, palavra in enumerate(palavras):
        palavra_lower = palavra.lower()
        # First word always capitalized, or non-connectors
        if i == 0 or palavra_lower not in PORTUGUESE_CONNECTORS:
            resultado.append(palavra.capitalize())
        else:
            resultado.append(palavra_lower)
    return " ".join(resultado)


def datas_semana_atual() -> list[str]:
    hoje    = date.today()
    segunda = hoje - timedelta(days=hoje.weekday())
    return [(segunda + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(7)]


def gerar_id_servidor(nome: str) -> str:
    slug = nome.strip().lower().replace(" ", "-")
    return f"SRV-{slug}"


def calcular_estatisticas(dados: list[tuple]) -> dict:
    minutos_por_pessoa: dict[str, int] = defaultdict(int)
    visitas_por_pessoa: dict[str, int] = defaultdict(int)
    uso_maquinas:       dict[str, int] = defaultdict(int)
    horas_entrada:      dict[int, int]  = defaultdict(int)

    for data, entrada, saida, nome, matricula, maquina, _ in dados:
        chave = f"{nome} ({matricula})"
        visitas_por_pessoa[chave] += 1
        if maquina and maquina not in ("-", ""):
            uso_maquinas[maquina] += 1
        if entrada:
            try:
                horas_entrada[int(entrada.split(":")[0])] += 1
            except Exception:
                pass
        if saida and entrada and data:
            try:
                fmt = "%d/%m/%Y %H:%M"
                delta = (
                    datetime.strptime(f"{data} {saida}", fmt)
                    - datetime.strptime(f"{data} {entrada}", fmt)
                )
                minutos_por_pessoa[chave] += int(delta.total_seconds() // 60)
            except Exception:
                pass

    return {
        "total_visitas":      sum(visitas_por_pessoa.values()),
        "total_pessoas":      len(visitas_por_pessoa),
        "visitas_por_pessoa": sorted(visitas_por_pessoa.items(), key=lambda x: -x[1]),
        "horas_por_pessoa": {
            k: f"{v // 60}h{v % 60:02}m"
            for k, v in sorted(minutos_por_pessoa.items(), key=lambda x: -x[1])
        },
        "maquina_mais_usada": (
            max(uso_maquinas, key=uso_maquinas.get) if uso_maquinas else "-"
        ),
        "horario_pico": (
            f"{max(horas_entrada, key=horas_entrada.get):02}:00"
            if horas_entrada else "-"
        ),
    }


# ─────────────────────────────────────────────
# DIALOG UTILITIES
# ─────────────────────────────────────────────

def center_dialog(win: tk.Toplevel, parent: tk.Tk | tk.Toplevel):
    """Center dialog window relative to its parent window."""
    win.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    wx, wh = win.winfo_width(), win.winfo_height()
    x = px + (pw - wx) // 2
    y = py + (ph - wh) // 2
    win.geometry(f"+{x}+{y}")


def setup_dialog(win: tk.Toplevel, parent: tk.Tk | tk.Toplevel, min_width: int = 300, min_height: int = 120,
                 resizable: tuple[bool, bool] = (True, True), escape_close: bool = True):
    """Configure common dialog properties: position, grab, focus handling.

    Args:
        win: The Toplevel window to configure
        parent: The parent window
        min_width: Minimum width for the dialog
        min_height: Minimum height for the dialog
        resizable: Tuple of (width_resizable, height_resizable)
        escape_close: Whether Escape key should close the dialog
    """
    win.transient(parent)
    win.resizable(*resizable)
    win.minsize(min_width, min_height)

    # Escape key handling
    if escape_close:
        win.bind("<Escape>", lambda e: win.destroy())

    # Center and grab after window is mapped (visible)
    mapped = [False]  # Use list to allow modification in closure
    def on_map(event=None):
        if mapped[0]:
            return
        mapped[0] = True
        center_dialog(win, parent)
        try:
            win.grab_set()
        except tk.TclError:
            pass  # Window already destroyed or grab failed

    win.bind("<Map>", on_map, add='+')


def focus_first_field(*fields):
    """Set focus to the first editable field and select its content if applicable."""
    if fields:
        first = fields[0]
        first.focus_set()
        if isinstance(first, tk.Entry):
            first.select_range(0, tk.END)


def bind_enter_to_button(widget: tk.Widget, button: tk.Button):
    """Bind Enter key in widget to trigger button click."""
    widget.bind("<Return>", lambda e: button.invoke())
    widget.bind("<KP_Enter>", lambda e: button.invoke())


def center_messagebox(win: tk.Tk | tk.Toplevel):
    """Reposition a messagebox to be centered over the parent window."""
    # messagebox uses the parent's geometry, but we can still fix positioning
    pass  # messagebox already centers over parent when parent is specified


# ─────────────────────────────────────────────
# APLICAÇÃO (UI)
# ─────────────────────────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("")
        self.root.minsize(820, 400)
        self.config = load_config()

        # estado de ordenação por coluna
        self._sort_state: dict = {}
        self._status_job = None
        # pilha de undo: lista de dicts {tipo, ...dados para reverter}
        self._undo_stack: list[dict] = []
        # tema escuro ativo
        self._tema_escuro: bool = True

        self._build_ui()
        self._build_menu()
        self._rebuild_abas()
        self._aplicar_tema()
        self._atualizar_lista()
        self._tick_relogio()

        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        self.root.bind_all("<Control-z>", self._on_ctrl_z)
        self.root.after(500, self._verificar_export_pendente)
        self.root.after(800, self._verificar_orfaos)

    # ── UI base ──────────────────────────────

    def _build_ui(self):
        # HEADER
        self.header = tk.Frame(self.root, height=40)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        # Header title
        self.lbl_title = tk.Label(self.header, text="LabCTRL", font=("Segoe UI", 12, "bold"))
        self.lbl_title.pack(side="left", padx=12)

        # Separator line
        self.sep_header = tk.Frame(self.root, height=1)
        self.sep_header.pack(fill="x", side="top")

        # Filter buttons with integrated counters
        self.var_filtro = tk.StringVar(value="Hoje")
        self._btns_filtro = {}
        self._filter_frame = tk.Frame(self.header)
        self._filter_frame.pack(side="left", padx=2)

        
        def make_filter_button(text, width=10, command=None):
            return tk.Button(
                self._filter_frame, text=text, width=width,
                command=command, bd=0, highlightthickness=0, pady=1,
            )

        self._btns_filtro["Hoje"] = make_filter_button(
            "Hoje", 14, command=lambda: self._set_filtro("Hoje")
        )
        self._btns_filtro["Hoje"].pack(side="left", padx=2)

        self._btns_filtro["Ativos"] = make_filter_button(
            "Ativos", 14, command=lambda: self._set_filtro("Ativos")
        )
        self._btns_filtro["Ativos"].pack(side="left", padx=2)

        # Month selector: split button with month on left, dropdown arrow on right
        self._month_btn = tk.Button(
            self.header, text="", width=12, anchor="center",
            bd=0, highlightthickness=0, pady=1
        )
        self._month_btn.pack(side="left", padx=2)

        # Dropdown arrow button - compact, same style as month button
        self._month_dropdown_btn = tk.Button(
            self.header, text="▾", width=1,
            bd=0, highlightthickness=0, pady=1
        )
        self._month_dropdown_btn.pack(side="left", padx=(0, 2))

        # Create month menu
        self._month_menu = tk.Menu(self.header, tearoff=0, bd=0,)
        self._month_dropdown_btn.config(command=lambda: self._show_month_menu())

        self.lbl_clock = tk.Label(self.header, text="")
        self.lbl_clock.pack(side="right", padx=12)

        
        # CONTROLS TOOLBAR
        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(fill="x", padx=12, pady=8)

        # Matrícula entry with placeholder
        self.entry_matricula = tk.Entry(self.toolbar, width=16, bd=0, highlightthickness=0)
        self.entry_matricula.pack(side="left", padx=(0, 8))
        self.entry_matricula.bind("<Return>", self.registrar_entrada)
        self.entry_matricula.bind("<KP_Enter>", self.registrar_entrada)
        self.entry_matricula.bind("<Tab>", self._focus_maquina)
        self.entry_matricula.bind("<KeyRelease>", self._validate_matricula)
        self.entry_matricula.focus()

        # Placeholder handling - entry uses normal text variable, placeholder drawn manually
        self._ph_matricula = tk.StringVar(value="Matrícula")
        self.entry_matricula.configure(textvariable=self._ph_matricula, fg="#B5BAC1")
        self.entry_matricula.bind("<FocusIn>", lambda e: self._on_entry_focus(e))
        self.entry_matricula.bind("<FocusOut>", lambda e: self._on_entry_focus_out(e))

        # Máquina combobox
        self.combo_maquina = ttk.Combobox(
            self.toolbar, values=["-", "ML"] + [f"{i:02}" for i in range(1, 21)],
            width=6, state="normal",
        )
        self.combo_maquina.set("-")
        self.combo_maquina.bind("<Return>", self.registrar_entrada)
        self.combo_maquina.bind("<KP_Enter>", self.registrar_entrada)
        self.combo_maquina.bind("<Tab>", self._focus_bolsista)
        self.combo_maquina.bind("<FocusIn>", self._on_maquina_focus_in)
        self.combo_maquina.bind("<KeyRelease>", self._validate_maquina)
        self.combo_maquina.pack(side="left", padx=8)

        # Bolsista combobox
        bolsistas = buscar_bolsistas()
        self.combo_bolsista = ttk.Combobox(
            self.toolbar, values=bolsistas, width=28, state="readonly"
        )
        ultimo = self.config.get("ultimo_bolsista")
        if ultimo and ultimo in bolsistas:
            self.combo_bolsista.set(ultimo)
        elif bolsistas:
            self.combo_bolsista.set(bolsistas[0])
        self.combo_bolsista.bind("<<ComboboxSelected>>", self._on_bolsista_change)
        self.combo_bolsista.bind("<Return>", self.registrar_entrada)
        self.combo_bolsista.bind("<KP_Enter>", self.registrar_entrada)
        self.combo_bolsista.bind("<Tab>", self._focus_matricula_from_bolsista)
        self.combo_bolsista.bind("<FocusIn>", self._on_bolsista_focus_in)
        self.combo_bolsista.pack(side="left", padx=8)

        # ENTRADA button
        self.btn_entrada = tk.Button(self.toolbar, text="ENTRADA",
                                     command=self.registrar_entrada, width=10,
                                     bd=0, highlightthickness=0)
        self.btn_entrada.pack(side="left", padx=(12, 0))

        # ── MENU POPUP ──────────────────────────
        self.btn_menu = tk.Button(self.header, text="⋮", width=1, relief="flat", bd=0, highlightthickness=0, font=(None, -20), command=self._abrir_menu)
        self.btn_menu.pack(side="right", padx=8)

        # MAIN CONTENT - Tree frame
        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        self.tree = ttk.Treeview(self.tree_frame, columns=COL_NAMES, show="headings")
        for col in COL_NAMES:
            self.tree.heading(
                col, text=col,
                command=lambda c=col: self._ordenar(c),
            )
        self.tree.pack(fill="both", expand=True, side="left")

        # Tree scrollbar
        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.pack(fill="y", side="right")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<BackSpace>", lambda e: self._saida_selecionado())

        # Click on tree to clear selection if on empty area
        self.tree.bind("<Button-1>", self._on_root_click)

        # BOTTOM STATUS BAR
        self.bottom_bar = tk.Frame(self.root, height=26)
        self.bottom_bar.pack(fill="x", side="bottom")
        self.bottom_bar.pack_propagate(False)

        self.lbl_selecionados = tk.Label(self.bottom_bar, text="Selecionados: 0", anchor="w", padx=8)
        self.lbl_selecionados.pack(side="left")

        self.lbl_registros = tk.Label(self.bottom_bar, text="Registros: 0", anchor="w", padx=8)
        self.lbl_registros.pack(side="left")

        self.lbl_status = tk.Label(self.bottom_bar, text="Pronto", anchor="w", padx=8)
        self.lbl_status.pack(side="left", padx=12)

        # Bottom bar action buttons
        self.btn_saida = tk.Button(self.bottom_bar, text="Registrar Saída",
                                   command=self._saida_selecionado, state="disabled", width=12,
                                   bd=0, highlightthickness=0)
        self.btn_saida.pack(side="right", padx=6)

        self.btn_desfazer = tk.Button(self.bottom_bar, text="↶",
                                      command=self._desfazer, width=3,
                                      bd=0, highlightthickness=0)
        self.btn_desfazer.pack(side="right", padx=4)

    def _on_entry_focus(self, event):
        if self._ph_matricula.get() == "Matrícula":
            self._ph_matricula.set("")
            self.entry_matricula.configure(fg="#FFFFFF")

    def _on_entry_focus_out(self, event):
        if not self._ph_matricula.get():
            self._ph_matricula.set("Matrícula")
            self.entry_matricula.configure(fg="#B5BAC1")

    def _focus_maquina(self, event):
        self.combo_maquina.focus()
        self.combo_maquina.selection_range(0, tk.END)
        return "break"

    def _focus_bolsista(self, event):
        self.combo_bolsista.focus()
        self.combo_bolsista.selection_range(0, tk.END)
        return "break"

    def _focus_matricula_from_bolsista(self, event):
        self.entry_matricula.focus()
        self.entry_matricula.selection_range(0, tk.END)
        return "break"

    def _on_maquina_focus_in(self, event):
        self.combo_maquina.selection_range(0, tk.END)

    def _on_bolsista_focus_in(self, event):
        self.combo_bolsista.selection_range(0, tk.END)

    def _validate_matricula(self, event):
        """Filter matricula input to allow only digits, max 6 chars."""
        valor = self.entry_matricula.get()
        if valor == "" or valor.isdigit():
            if len(valor) > 6:
                self.entry_matricula.delete(0, tk.END)
                self.entry_matricula.insert(0, valor[:6])
        else:
            # Remove non-digits
            cleaned = "".join(c for c in valor if c.isdigit())
            self.entry_matricula.delete(0, tk.END)
            self.entry_matricula.insert(0, cleaned[:6])

    def _validate_maquina(self, event):
        """Filter maquina input to allow only valid values as user types."""
        valor = self.combo_maquina.get().upper()
        valid_values = ["-", "ML"] + [f"{i:02}" for i in range(1, 21)]
        # Allow valid values or partial input for ML
        if valor in valid_values or valor == "":
            return True
        if valor.startswith("ML"):
            return True  # Allow "ML" to be typed
        # Check if it's a valid number being typed
        if valor.isdigit():
            try:
                num = int(valor)
                if 1 <= num <= 20:
                    return True  # Allow valid machine numbers
                elif num < 1:
                    self.combo_maquina.set("-")  # Clamp to "-"
                else:
                    self.combo_maquina.set("20")  # Clamp to "20"
            except:
                self.combo_maquina.set("-")
        elif len(valor) > 1 and valor[:-1].isdigit() and valor[-1].isdigit():
            # Still typing a number, allow it
            return True
        else:
            # Invalid input, reset to last valid
            self.combo_maquina.set("-")
        return True

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Editar selecionado",  command=self._editar_registro)
        self.menu.add_command(label="Remover selecionado", command=self._remover_registro)
        self.menu.add_separator()

        export_menu = tk.Menu(self.menu, tearoff=0)
        export_menu.add_command(label="Dia",    command=self._exportar_dia)
        export_menu.add_command(label="Ontem",  command=self._exportar_ontem)
        export_menu.add_command(label="Semana", command=self._exportar_semana)
        export_menu.add_command(label="Mês",    command=self._exportar_mes)
        self.menu.add_cascade(label="Exportar", menu=export_menu)
        

        copiar_menu = tk.Menu(self.menu, tearoff=0)
        copiar_menu.add_command(label="Hoje",        command=lambda: self._copiar_periodo("Hoje"))
        copiar_menu.add_command(label="Ontem",       command=lambda: self._copiar_periodo("Ontem"))
        copiar_menu.add_command(label="Semana",      command=lambda: self._copiar_periodo("Semana"))
        copiar_menu.add_command(label="Mês",         command=lambda: self._copiar_periodo("Mês"))
        copiar_menu.add_command(label="Personalizado", command=self._abrir_copiar_personalizado)
        self.menu.add_cascade(label="Copiar Dados", menu=copiar_menu)
        self.menu.add_separator()
        
        self.menu.add_command(label="Visualizar DB", command=self._visualizar_db)
        self.menu.add_separator()
        self.menu.add_command(label="Bolsistas",           command=self._abrir_bolsistas)
        self.menu.add_command(label="Alunos / Servidores", command=self._abrir_alunos)
        self.menu.add_separator()
        self.menu.add_command(label="Alternar Tema",       command=self._toggle_tema)
        self.menu.add_separator()
        self.menu.add_command(label="Sobre",               command=self._sobre)

    def _abrir_menu(self):
        """Open the menu using the button's screen position."""
        self.menu.tk_popup(self.btn_menu.winfo_rootx(), self.btn_menu.winfo_rooty() + 20)

    def _sobre(self):
        """Open the about dialog."""
        t = TEMAS[self.config["theme"]]
        bg, fg, field = t["bg"], t["fg"], t["field"]

        win = tk.Toplevel(self.root)
        win.title("Sobre")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=400, min_height=200, resizable=(False, False), escape_close=True)

        # Title
        tk.Label(win, text="LabCTRL", font=(None, 14, "bold"),
                 bg=bg, fg=fg).pack(pady=(15, 5))

        # Subtitle
        tk.Label(win, text="Sistema de Controle de Acesso de Laboratório",
                 bg=bg, fg=fg).pack(pady=(0, 10))

        # Content - Text widget for selectable text (styled like a label)
        texto = (
            "Desenvolvido por Marco Aurélio do curso de Engenharia de Computação em 2026.1 durante a Bolsa de Iniciação Acadêmica, "
            "com o objetivo de substituir o processo antigo de controle de acesso realizado em papel e transcrito manualmente para planilhas.\n\n"
            "Este sistema encontra-se em desenvolvimento contínuo. Caso futuramente receba novas "
            "funcionalidades, correções ou passe a ser mantido por outras pessoas, preservar estas informações e registrar os novos responsáveis pela manutenção.\n\n"
            "Autor: Marco (@4mrco)\n"
            "Contato: marco.aurelio@alu.ufc.br"
        )
        text_widget = tk.Text(win, wrap="word", bg=bg, fg=fg, relief="flat",
                              highlightthickness=0, font=(None, 9), padx=5, pady=5, bd=0)
        text_widget.pack(padx=15, pady=10)
        text_widget.insert("1.0", texto)
        text_widget.configure(state="disabled", cursor="")  # Disabled but selectable

        # Close button
        close_btn = tk.Button(win, text="Fechar", width=10, command=win.destroy,
                  bg="#35383e", fg=fg, bd=0, highlightthickness=0)
        close_btn.pack(pady=(0, 15))
        bind_enter_to_button(win, close_btn)

    # ── Filtro ───────────────────────────────

    def _set_filtro(self, opcao: str):
        self.var_filtro.set(opcao)
        # Reset month to current when selecting Hoje or Ativos filters
        if opcao in ("Hoje", "Ativos"):
            self._reset_month_to_current()
        self._aplicar_tema()  # Re-color filter buttons
        self._atualizar_lista()

    def _reset_month_to_current(self):
        """Reset month button and key to current month."""
        hoje = agora().strftime("%d/%m/%Y")
        mes_atual = hoje[3:]
        for f in self._meses_formatados():
            if self._parse_mes_combo(f) == mes_atual:
                self._month_btn.config(text=f)
                self._current_month_key = f
                break

    # ── Popup entrada sem matrícula ──────────

    def _popup_sem_matricula(self) -> tuple[str, str] | None:
        """Retorna (nome, tipo) ou None se cancelado."""
        t = TEMAS[self.config["theme"]]
        bg, fg, field = t["bg"], t["fg"], t["field"]
        win = tk.Toplevel(self.root)
        win.title("Entrada sem matrícula")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=320, min_height=140)

        tk.Label(win, text="Nome:", bg=bg, fg=fg).grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        entry_nome = tk.Entry(win, width=28, bd=0, highlightthickness=0, bg=field, fg=fg)
        entry_nome.grid(row=0, column=1, padx=10, pady=(12, 4))

        tk.Label(win, text="Tipo:", bg=bg, fg=fg).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        var_tipo = tk.StringVar(value="Aluno")
        frame_tipo = tk.Frame(win, bg=bg)
        frame_tipo.grid(row=1, column=1, sticky="w", padx=10, pady=4)
        tk.Radiobutton(frame_tipo, text="Aluno",    variable=var_tipo, value="Aluno", bd=0, highlightthickness=0,
                       bg=bg, fg=fg).pack(side="left")
        tk.Radiobutton(frame_tipo, text="Servidor", variable=var_tipo, value="Servidor", bd=0, highlightthickness=0,
                       bg=bg, fg=fg).pack(side="left")

        resultado = {"valor": None}

        def confirmar(event=None):
            nome = entry_nome.get().strip()
            if not nome:
                return
            resultado["valor"] = (nome, var_tipo.get())
            win.destroy()

        entry_nome.bind("<Return>", confirmar)
        win.bind("<Return>", confirmar)
        win.bind("<KP_Enter>", confirmar)
        select_btn = "#35383e"
        tk.Button(win, text="Salvar", command=confirmar, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg).grid(row=2, column=0, columnspan=2, pady=(4, 12))
        focus_first_field(entry_nome)
        win.wait_window()
        self._focus_matricula()
        return resultado["valor"]

    def status(self, msg: str, erro: bool = False):
        if self._status_job:
            self.root.after_cancel(self._status_job)

        t = TEMAS[self.config["theme"]]
        cor = "#c0392b" if erro else t["fg"]

        self.lbl_status.config(text=msg, fg=cor)

        self._status_job = self.root.after(
            4000,
            lambda: self.lbl_status.config(text="")
        )
    # ── Mês formatting ─────────────────────────

    def _meses_formatados(self) -> list[str]:
        """Return months in format 'Junho 2026' for combobox."""
        meses_num = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
                     "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
                     "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
        raw_meses = buscar_meses()
        return [f"{meses_num.get(m[:2], m[:2])} {m[3:]}" for m in raw_meses]

    def _parse_mes_combo(self, texto: str) -> str:
        """Convert 'Junho 2026' back to '06/2026' format."""
        meses_num = {"Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04",
                     "Maio": "05", "Junho": "06", "Julho": "07", "Agosto": "08",
                     "Setembro": "09", "Outubro": "10", "Novembro": "11", "Dezembro": "12"}
        partes = texto.split()
        return f"{meses_num.get(partes[0], partes[0])}/{partes[1]}"

    # ── Abas (simplified) ───────────────────

    def _rebuild_abas(self):
        """Initialize month button and populate menu, then clear sort state."""
        meses = self._meses_formatados()
        self._populate_month_menu(meses)

        # Select current month if available, update button text
        hoje = agora().strftime("%d/%m/%Y")
        mes_atual = hoje[3:]
        for f in meses:
            if self._parse_mes_combo(f) == mes_atual:
                self._month_btn.config(text=f)
                self._current_month_key = f
                break
        if not hasattr(self, '_current_month_key') and meses:
            self._month_btn.config(text=meses[0])
            self._current_month_key = meses[0]

        self._sort_state.clear()
        self._atualizar_lista()
        self._month_btn.config(command=self._set_month_to_current)

    def _mes_ativo(self) -> str:
        """Return the currently selected month in DD/MM/YYYY format (using current day)."""
        if hasattr(self, '_current_month_key') and self._current_month_key:
            return self._parse_mes_combo(self._current_month_key)
        return agora().strftime("%m/%Y")

    def _populate_month_menu(self, meses):
        """Populate the month selection menu."""
        self._month_menu.delete(0, tk.END)
        for m in meses:
            self._month_menu.add_command(label=m, command=lambda sel=m: self._select_month(sel))

    def _show_month_menu(self):
        """Display the month selection menu."""
        self._month_menu.tk_popup(self._month_dropdown_btn.winfo_rootx(),
                                   self._month_dropdown_btn.winfo_rooty() + 20)

    def _select_month(self, month_name):
        """Handle month selection from menu."""
        self._month_btn.config(text=month_name)
        self._current_month_key = month_name
        self.var_filtro.set("Mês")  # Ensure month filter is active
        self._atualizar_lista()

    def _set_month_to_current(self):
        """Set month selector to current month and refresh."""
        hoje = agora().strftime("%d/%m/%Y")
        mes_atual = hoje[3:]
        for f in self._meses_formatados():
            if self._parse_mes_combo(f) == mes_atual:
                self._month_btn.config(text=f)
                self._current_month_key = f
                break
        self.var_filtro.set("Mês")  # Ensure month filter is active
        self._atualizar_lista()

    # ── Ordenação por coluna ─────────────────

    def _ordenar(self, col: str, evento=None):
        if not hasattr(self, '_current_month_key') or not self._current_month_key:
            return
        reverse = False
        estado = self._sort_state.get("current")
        if estado and estado[0] == col:
            reverse = not estado[1]
        self._sort_state["current"] = (col, reverse)

        idx = COL_NAMES.index(col)
        items = [(self.tree.item(i)["values"][idx] or "", i) for i in self.tree.get_children()]
        items.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)

        for order, (_, item) in enumerate(items):
            self.tree.move(item, "", order)

        for c in COL_NAMES:
            arrow = (" ↓" if reverse else " ↑") if c == col else ""
            self.tree.heading(c, text=c + arrow,
                            command=lambda cc=c: self._ordenar(cc))

    # ── Ordenação por coluna ─────────────────

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if sel:
            tags = self.tree.item(sel[0])["tags"]
            status = tags[1] if len(tags) > 1 else ""
            self.btn_saida.configure(state="normal" if status == "ATIVO" else "disabled")
            self.lbl_selecionados.config(text=f"Selecionados: {len(sel)}")
        else:
            self.btn_saida.configure(state="disabled")
            self.lbl_selecionados.config(text="Selecionados: 0")

    def _on_root_click(self, event=None):
        """Clear tree selection when clicking on empty area of tree."""
        if not event:
            return
        try:
            # identify() takes x, y as separate arguments
            region = self.tree.identify("item", event.x, event.y)
            if region == "nothing":  # Clicked on empty area
                self.tree.selection_remove(self.tree.selection())
        except (tk.TclError, TypeError):
            pass  # Ignore errors during click handling

    def _on_double_click(self, event=None):
        item = self.tree.identify_row(event.y)
        if item:
            rid = int(self.tree.item(item)["tags"][0])
            self._abrir_form_edicao(rid)

    def _saida_selecionado(self):
        sel = self.tree.selection()
        if not sel:
            return

        # Get all selected records that are active
        reg_items = []
        for item in sel:
            rid = int(self.tree.item(item)["tags"][0])
            reg = buscar_registro_por_id(rid)
            if reg and reg[8] == "ATIVO":  # Only active records
                reg_items.append((rid, reg[1], item))

        if not reg_items:
            return

        # Confirmation for multiple records
        if len(reg_items) > 1:
            if not messagebox.askyesno(
                "Confirmar Saída",
                f"Tem certeza que deseja registrar saída para {len(reg_items)} aluno(s)?",
                parent=self.root
            ):
                return

        # Perform all operations
        self._registrar_saida_batch(reg_items)

    def _registrar_saida_por_rid(self, rid: int):
        """Register exit for a single record (helper for backward compatibility)."""
        reg = buscar_registro_por_id(rid)
        if not reg or reg[8] != "ATIVO":
            return
        self._registrar_saida_batch([(rid, reg[1], None)])

    def _registrar_saida_batch(self, reg_items: list):
        """Register exit for multiple records atomically."""
        undo_entries = []
        success = True

        for rid, nome, item in reg_items:
            try:
                finalizar_registro(rid, agora().strftime("%H:%M"))
                undo_entries.append({"tipo": "saida", "rid": rid, "nome": nome})
            except Exception as e:
                log.error("Falha ao registrar saída de %s: %s", nome, e)
                success = False
                break

        if success:
            # Atomically save all undo entries
            for entry in undo_entries:
                self._push_undo(entry)
            self.status(f"Saída de {len(reg_items)} aluno(s) registrada(s).")
        else:
            # Rollback on error
            self.status("Erro ao registrar saída.", erro=True)

        # Always refresh UI
        self._atualizar_lista()
        self._focus_matricula()

    def _registrar_saida(self, matricula: str):
        rid = buscar_registro_ativo(matricula)
        if rid:
            try:
                nome = (buscar_aluno(matricula) or (matricula,))[0]
                finalizar_registro(rid, agora().strftime("%H:%M"))
                self._push_undo({"tipo": "saida", "rid": rid, "nome": nome})
                self.status(f"Saída de {nome} registrada.")
            except Exception as e:
                log.error("Falha ao registrar saída: %s", e)
                self.status("Erro ao registrar saída.", erro=True)
        self._atualizar_lista()
        self._focus_matricula()

    def _push_undo(self, acao: dict):
        self._undo_stack.append(acao)

    def _focus_matricula(self):
        """Retorna foco para entry_matricula com texto selecionado se houver."""
        self.entry_matricula.focus()
        mat = self._ph_matricula.get()
        # Only select if it's actual input (not placeholder)
        if mat and mat != "Matrícula":
            self.entry_matricula.select_range(0, tk.END)

    def _on_ctrl_z(self, event=None):
        """Handler para Ctrl+Z global que protege widgets de texto."""
        widget = self.root.focus_get()
        # Protege widgets Entry e Text para não interferir em edição
        if isinstance(widget, (tk.Entry, tk.Text)):
            return
        self._desfazer()
        self.status("Última ação desfeita (Ctrl+Z).")

    def _on_bolsista_change(self, event=None):
        """Salva o bolsista selecionado ao mudar a escolha."""
        selecionado = self.combo_bolsista.get()
        if selecionado:
            self.config["ultimo_bolsista"] = selecionado
            save_config(self.config)

    def _desfazer(self):
        if not self._undo_stack:
            self.status("Nada para desfazer.", erro=True)
            return

        acao = self._undo_stack.pop()
        tipo = acao["tipo"]

        try:
            if tipo == "entrada":
                # desfaz: deleta o registro inserido
                deletar_registro(acao["rid"])
                self.status(f"Entrada de {acao['nome']} desfeita.")

            elif tipo == "saida":
                # desfaz: volta status ATIVO, apaga saída
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE registros SET saida=NULL, status='ATIVO' WHERE id=?",
                        (acao["rid"],),
                    )
                self.status(f"Saída de {acao['nome']} desfeita.")

            elif tipo == "remocao":
                # desfaz: recria o registro deletado
                restaurar_registro_db(acao["campos"])
                self.status(f"Remoção de {acao['nome']} desfeita.")

            elif tipo == "edicao":
                # desfaz: restaura valores anteriores
                c = acao["antes"]
                atualizar_registro(c["id"], c["data"], c["entrada"],
                                   c["saida"] or "", c["maquina"] or "")
                self.status(f"Edição de {acao['nome']} desfeita.")

        except Exception as e:
            log.error("Falha no undo: %s", e)
            self.status("Erro ao desfazer.", erro=True)
            return

        self._rebuild_abas()
        self._atualizar_lista()
        self._focus_matricula()

    def _fluxo_entrada(self, matricula: str | None, nome: str) -> bool:
        if matricula:
            rid_ativo = buscar_registro_ativo(matricula)
            if rid_ativo:
                resp = messagebox.askyesno(
                    "Já dentro",
                    f"{nome} já tem entrada ativa.\nRegistrar saída agora?",
                    parent=self.root
                )
                if resp:
                    finalizar_registro(rid_ativo, agora().strftime("%H:%M"))
                    self._push_undo({"tipo": "saida", "rid": rid_ativo, "nome": nome})
                    self.status(f"Saída de {nome} registrada.")
                    self._atualizar_lista()
                return False

        now = agora()
        try:
            inserir_registro(
                matricula, nome,
                now.strftime("%d/%m/%Y"), now.strftime("%H:%M"),
                self.combo_maquina.get(), self.combo_bolsista.get(),
            )
        except Exception as e:
            log.error("Falha ao inserir registro: %s", e)
            self.status("Erro ao registrar entrada.", erro=True)
            return False

        # Descobre o id do registro recém-inserido
        with get_conn() as conn:
            rid = conn.execute(
                "SELECT id FROM registros WHERE matricula IS ? AND nome=? ORDER BY id DESC LIMIT 1",
                (matricula, nome),
            ).fetchone()[0]

        self._push_undo({"tipo": "entrada", "rid": rid, "nome": nome})
        self.status(f"Entrada de {nome} registrada às {now.strftime('%H:%M')}.")
        return True
    
    def registrar_entrada(self, event=None):
        matricula = self.entry_matricula.get().strip()
        # Handle placeholder text
        if matricula == "Matrícula" or matricula == "":
            matricula = ""

        if not matricula:
            res = self._popup_sem_matricula()
            if not res:
                return
            nome, tipo = res
            mat_db = None if tipo == "Aluno" else "SERVIDOR"
            if self._fluxo_entrada(mat_db, nome):
                self._rebuild_abas()
                self._ph_matricula.set("Matrícula")
            self._focus_matricula()
            return

        resultado = buscar_aluno(matricula)
        if not resultado:
            nome = self._pedir_input("Novo aluno", "Nome completo:")
            if not nome:
                return
            nome = normalizar_nome(nome)
            try:
                inserir_aluno(matricula, nome, tipo="aluno")
            except Exception as e:
                log.error("Falha ao inserir aluno: %s", e)
                self.status("Erro ao cadastrar aluno.", erro=True)
                return
        else:
            nome = resultado[0]

        if self._fluxo_entrada(matricula, nome):
            self._rebuild_abas()
            # Reset fields for next registration
            self._ph_matricula.set("")
            self.combo_maquina.set("-")
            self.entry_matricula.focus()
            self.entry_matricula.selection_range(0, tk.END)
        else:
            # Only reset to placeholder if registration failed
            self._ph_matricula.set("Matrícula")
            self._focus_matricula()

    def _remover_registro(self):
        tree = self.tree
        sel  = tree.selection()
        if not sel:
            return
        rid = int(tree.item(sel[0])["tags"][0])
        reg = buscar_registro_por_id(rid)
        if not reg:
            return
        if messagebox.askyesno("Confirmar", "Remover registro?", parent=self.root):
            try:
                # Guarda snapshot antes de deletar
                self._push_undo({
                    "tipo":  "remocao",
                    "nome":  reg[1],
                    "campos": {
                        "id": reg[0], "nome": reg[1], "matricula": reg[2],
                        "data": reg[3], "entrada": reg[4], "saida": reg[5],
                        "maquina": reg[6], "bolsista": reg[7], "status": reg[8],
                    },
                })
                deletar_registro(rid)
                self.status("Registro removido.")
                self._focus_matricula()
            except Exception as e:
                self._undo_stack.pop()  # descarta o undo se falhou
                log.error("Falha ao remover: %s", e)
                self.status("Erro ao remover registro.", erro=True)
            self._rebuild_abas()
            self._atualizar_lista()

    def registrar_servidor(self):
        nome = self._pedir_input("Servidor", "Nome completo:")
        if not nome:
            return

        matricula = gerar_id_servidor(nome)
        if not buscar_aluno(matricula):
            try:
                inserir_aluno(matricula, nome, tipo="servidor")
            except Exception as e:
                log.error("Falha ao inserir servidor: %s", e)
                self.status("Erro ao cadastrar servidor.", erro=True)
                return

        if self._fluxo_entrada(matricula, nome):
            self._rebuild_abas()
            self._atualizar_lista()

    # ── Atualização da lista ──────────────────

    def _atualizar_lista(self):
        t = TEMAS[self.config["theme"]]
        hoje = agora().strftime("%d/%m/%Y")

        # Get selected month from the current_month_key
        if hasattr(self, '_current_month_key') and self._current_month_key:
            mes = self._parse_mes_combo(self._current_month_key)
        else:
            return

        # Clear and configure tree
        self.tree.delete(*self.tree.get_children())

        self.tree.tag_configure("ATIVO", background=t["ativo_bg"])
        self.tree.tag_configure("FINALIZADO", background=t["bg"])

        registros = buscar_registros_por_mes(mes)

        # Sort by entrada (column index 4): oldest first (empty last)
        registros = sorted(registros, key=lambda r: r[4] if r[4] else "99:99")

        # Apply filters based on var_filtro
        filtro = self.var_filtro.get() if hasattr(self, 'var_filtro') else "Mês"
        if filtro == "Hoje":
            registros = [r for r in registros if r[3] == hoje]
        elif filtro == "Ativos":
            registros = [r for r in registros if r[8] == "ATIVO"]

        # Populate with zebra striping
        for i, r in enumerate(registros):
            rid, nome, matricula, data, entrada, saida, maquina, bolsista, status = r
            tempo = calcular_tempo(entrada, saida, data) if saida else ""

            if not matricula:
                mat_exib = ""
            elif matricula == "SERVIDOR":
                mat_exib = "Servidor"
            elif matricula.startswith("SRV-"):
                mat_exib = "servidor"
            else:
                mat_exib = matricula

            # Zebra striping: ATIVO rows get special background, others get zebra
            if status == "ATIVO":
                tags = (str(rid), status)
            else:
                tags = (str(rid), "other", str(i % 2))

            self.tree.insert(
                "", "end",
                values=(nome, mat_exib, entrada, saida or "", tempo, maquina or "-"),
                tags=tags,
            )

        self.lbl_registros.config(text=f"Registros: {len(registros)}")
        self._atualizar_dashboard()

    def _atualizar_dashboard(self):
        hoje   = agora().strftime("%d/%m/%Y")
        total  = contar_registros_hoje(hoje)
        ativos = contar_ativos()
        # Update filter button counts
        self._btns_filtro["Hoje"].config(text=f"Hoje ({total})")
        self._btns_filtro["Ativos"].config(text=f"Ativos ({ativos})")

    def _tick_relogio(self):
        self.lbl_clock.config(text=agora().strftime("%H:%M"))
        self.root.after(1000, self._tick_relogio)

    # ── Tema ─────────────────────────────────

    def _toggle_tema(self):
        self.config["theme"] = "light" if self.config["theme"] == "dark" else "dark"
        save_config(self.config)
        self._tema_escuro = (self.config["theme"] == "dark")
        self._aplicar_tema()
        self._atualizar_lista()

    def _aplicar_tema(self):
        t = TEMAS[self.config["theme"]]
        bg, fg, field, select, row_a, row_b, ativo_bg = (
            t["bg"], t["fg"], t["field"], t["select"], t["row_a"], t["row_b"], t["ativo_bg"]
        )
        select_btn = "#35383e"  # Slightly darker than select for buttons

        style = ttk.Style()
        style.theme_use("default")

        self.root.configure(bg=bg)
        self.header.configure(bg=bg)
        self.toolbar.configure(bg=bg)
        self.tree_frame.configure(bg=bg)
        self.bottom_bar.configure(bg=bg)

        self.sep_header.configure(bg=field)

        self.lbl_title.configure(bg=bg, fg=fg)
        self.lbl_clock.configure(bg=bg, fg=fg)
        self.lbl_selecionados.configure(bg=bg, fg=fg)
        self.lbl_registros.configure(bg=bg, fg=fg)
        self.lbl_status.configure(bg=bg, fg=fg)

        # Filter frame background
        self._filter_frame.configure(bg=bg)

        # Toolbar buttons
        self.btn_entrada.configure(bg=field, fg=fg, activebackground=select, disabledforeground="#888888",
                                   relief="flat", bd=0, highlightthickness=0)
        self.btn_saida.configure(bg=field, fg=fg, activebackground=select, disabledforeground="#888888",
                                 relief="flat", bd=0, highlightthickness=0)
        self.btn_desfazer.configure(bg=field, fg=fg, activebackground=select,
                                     relief="flat", bd=0, highlightthickness=0)

        # Style filter buttons in header
        for nome, btn in self._btns_filtro.items():
            ativo = nome == self.var_filtro.get()
            btn.configure(
                bg=select if ativo else field, fg=fg,
                activebackground=select,
                relief="sunken" if ativo else "raised",
                bd=0, highlightthickness=0,
            )

        # Style month button (like filter buttons but always enabled)
        self._month_btn.configure(
            bg=field, fg=fg, activebackground=select,
            relief="raised", bd=0, highlightthickness=0
        )

        # Style dropdown arrow button - same as month button for unified look
        self._month_dropdown_btn.configure(
            bg=field, fg=fg, activebackground=select,
            relief="raised", bd=0, highlightthickness=0
        )

        # Apply dark theme to month menu
        self._month_menu.config(
            bg=field, fg=fg,
            activebackground=select, activeforeground=fg,
            tearoff=0,
        )

        if not self.entry_matricula.get() or self.entry_matricula.get() == "Matrícula":
            self.entry_matricula.configure(bg=field, fg="#B5BAC1", insertbackground=fg, disabledbackground=field,
                                           bd=0, highlightthickness=0)
        else:
            self.entry_matricula.configure(bg=field, fg=fg, insertbackground=fg, disabledbackground=field,
                                           bd=0, highlightthickness=0)

        # Define a slightly darker selection color for buttons
        select_btn = "#35383e"  # Slightly darker than select (#404249)

        # Configure dark theme for all ttk widgets
        style.configure("TFrame", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=select_btn, foreground=fg, borderwidth=0, highlightthickness=0)
        style.configure("TCombobox",
            fieldbackground=field, background=field, foreground=fg,
            borderwidth=0, highlightthickness=0)
        style.map("TCombobox",
            fieldbackground=[("readonly", field)],
            background=[("readonly", field)],
            foreground=[("readonly", fg)])

        # Apply dark theme to Combobox dropdown via Tk option database
        # The dropdown Listbox is created internally by Tk and must be styled
        # via option_add since ttk.Style doesn't affect it
        self.root.option_add("*TCombobox*Listbox.Background", field)
        self.root.option_add("*TCombobox*Listbox.Foreground", fg)
        self.root.option_add("*TCombobox*Listbox.SelectBackground", select)
        self.root.option_add("*TCombobox*Listbox.SelectForeground", fg)

        style.configure("Treeview",
            background=bg, foreground=fg, fieldbackground=field,
            borderwidth=0, highlightthickness=0)
        style.map("Treeview",
            background=[("selected", select)])
        style.configure("Treeview.Heading",
            background=field, foreground=fg, borderwidth=0, highlightthickness=0)
        style.map("Treeview.Heading",
            background=[("active", field)])

        # Configure vertical scrollbar
        style.configure("Vertical.TScrollbar",
            background=field, troughcolor=bg, arrowcolor=fg, borderwidth=0, highlightthickness=0)
        style.map("Vertical.TScrollbar",
            background=[("active", select)],
            arrowcolor=[("active", select)])
        self.tree_scroll.configure(style="Vertical.TScrollbar")

        # Configure menu button
        self.btn_menu.configure(bg=field, fg=fg, activebackground=select, relief="flat")

        # Configure menus with dark theme
        self.menu.configure(background=bg, foreground=fg,
                           activebackground=select, activeforeground=fg,
                           bd=0, relief="flat")
        # Reconfigure export_menu - it's a child of self.menu
        for item in self.menu.winfo_children():
            if isinstance(item, tk.Menu):
                item.configure(background=bg, foreground=fg,
                              activebackground=select, activeforeground=fg,
                              bd=0, relief="flat")

        self.tree.tag_configure("0", background=row_a)
        self.tree.tag_configure("1", background=row_b)
        self.tree.tag_configure("ATIVO", background=ativo_bg)
        self.tree.tag_configure("FINALIZADO", background=bg)

    def _ao_fechar(self):
        ativos = contar_ativos()
        if ativos > 0:
            resp = messagebox.askyesno(
                "Atenção",
                f"Há {ativos} pessoa(s) ainda dentro do laboratório.\n"
                "Deseja mesmo fechar o sistema?",
                parent=self.root
            )
            if not resp:
                return
        self.root.destroy()

    # ── Verificações no startup ───────────────

    def _verificar_export_pendente(self):
        mes_ant = mes_anterior()
        if mes_ant in self.config["exported_months"]:
            return
        if not buscar_export_mes(mes_ant):
            return
        if messagebox.askyesno("Export pendente",
                f"O mês {mes_ant} ainda não foi exportado.\n\nExportar agora?",
                parent=self.root):
            self._exportar_mes(mes_ant)

    def _verificar_orfaos(self):
        orfaos = buscar_registros_orfaos()
        if not orfaos:
            return
        nomes = "\n".join(f"  • {r[1]}  —  {r[3]} às {r[4]}" for r in orfaos)
        resp  = messagebox.askyesno(
            "Registros em aberto",
            f"Há {len(orfaos)} registro(s) de dias anteriores sem saída:\n\n"
            f"{nomes}\n\nFechar todos agora?",
            parent=self.root
        )
        if resp:
            for r in orfaos:
                finalizar_registro(r[0], None)
            self._atualizar_lista()
            self.status(f"{len(orfaos)} registro(s) órfão(s) encerrado(s).")

    # ── Export ───────────────────────────────

    def _fazer_export(self, dados: list[tuple], label: str, titulo: str,
                      marcar_mes: str | None = None):
        if not dados:
            messagebox.showinfo("Exportar", f"Nenhum registro para {titulo}.", parent=self.root)
            return

        def _fmt_matricula(m):
            if not m:
                return ""
            if m == "SERVIDOR":
                return "Servidor"
            return m

        dados_norm = [
            (data, entrada, saida, nome, _fmt_matricula(mat), maquina, bolsista)
            for data, entrada, saida, nome, mat, maquina, bolsista in dados
        ]

        stats        = calcular_estatisticas(dados_norm)
        nome_arquivo = f"lab_{label}.csv"

        # Determine month for folder name from the first record's date
        if dados:
            primeira_data = dados[0][0]  # First record's date
            mes_pasta = primeira_data.split("/")[1] + "-" + primeira_data.split("/")[0]  # MM-YYYY -> YYYY-MM
        else:
            mes_pasta = agora().strftime("%Y-%m")

        month_dir = get_month_export_dir(mes_pasta)
        caminho = os.path.join(month_dir, nome_arquivo)
        try:
            with open(caminho, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([f"Relatório do Laboratório — {titulo}"])
                w.writerow([
                    f"Total de visitas: {stats['total_visitas']}",
                    f"Pessoas distintas: {stats['total_pessoas']}",
                    f"Máquina mais usada: {stats['maquina_mais_usada']}",
                    f"Horário de pico: {stats['horario_pico']}",
                ])
                w.writerow([])
                w.writerow(["Resumo por pessoa"])
                w.writerow(["Nome (Matrícula)", "Visitas", "Tempo total"])
                for pessoa, visitas in stats["visitas_por_pessoa"]:
                    tempo = stats["horas_por_pessoa"].get(pessoa, "-")
                    w.writerow([pessoa, visitas, tempo])
                w.writerow([])
                w.writerow(["Registros detalhados"])
                w.writerow(["Data", "Entrada", "Saída", "Nome",
                            "Matrícula", "Máquina(Nº)", "Bolsista presente"])
                w.writerows(dados_norm)
        except Exception as e:
            log.error("Falha ao exportar: %s", e)
            self.status("Erro ao exportar.", erro=True)
            return

        if marcar_mes and marcar_mes not in self.config["exported_months"]:
            self.config["exported_months"].append(marcar_mes)
            save_config(self.config)

        self.status(f"Exportado: {nome_arquivo}")
        export_folder = os.path.dirname(os.path.abspath(caminho))

        # Show success dialog with option to open folder
        def abrir_pasta():
            import subprocess
            try:
                subprocess.Popen(["xdg-open", export_folder])
            except Exception:
                pass

        t = TEMAS[self.config["theme"]]
        info_win = tk.Toplevel(self.root)
        info_win.title("Exportado")
        info_win.configure(bg=t["bg"])
        setup_dialog(info_win, self.root, min_width=300, min_height=120, resizable=(False, False), escape_close=True)

        tk.Label(info_win, text=f"Arquivo salvo:\n{nome_arquivo}", bg=t["bg"], fg=t["fg"],
                 justify="center").pack(pady=10)

        btn_frame = tk.Frame(info_win, bg=t["bg"])
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Abrir Pasta", command=abrir_pasta,
                  bg="#35383e", fg=t["fg"], bd=0, highlightthickness=0).pack(side="left", padx=5)
        tk.Button(btn_frame, text="OK", command=info_win.destroy,
                  bg="#35383e", fg=t["fg"], bd=0, highlightthickness=0).pack(side="left", padx=5)

    def _exportar_dia(self):
        dia = agora().strftime("%d/%m/%Y")
        self._fazer_export(
            buscar_export_dia(dia),
            label=dia.replace("/", "_"),
            titulo=f"Dia {dia}",
        )

    def _exportar_ontem(self):
        dados, ontem = buscar_export_ontem()
        self._fazer_export(
            dados,
            label=ontem.replace("/", "_"),
            titulo=f"Dia {ontem}",
        )

    def _exportar_semana(self):
        datas   = datas_semana_atual()
        hoje    = date.today()
        segunda = hoje - timedelta(days=hoje.weekday())
        domingo = segunda + timedelta(days=6)
        self._fazer_export(
            buscar_export_semana(datas),
            label=f"semana_{segunda.strftime('%d%m')}_{domingo.strftime('%d%m_%Y')}",
            titulo=f"Semana {segunda.strftime('%d/%m')} – {domingo.strftime('%d/%m/%Y')}",
        )

    def _exportar_mes(self, mes: str | None = None):
        if mes is None:
            mes = self._mes_ativo()
        self._fazer_export(
            buscar_export_mes(mes),
            label=mes.replace("/", "_"),
            titulo=f"Mês {mes}",
            marcar_mes=mes,
        )

    # ── Copiar Dados ───────────────────────────────

    def _gerar_csv(self, dados: list[tuple]) -> str:
        """Gera CSV com cabeçalho e dados na ordem exigida."""
        linhas = ["Data,Horário Entrada,Horário Saída,Nome,Matrícula,Máquina (Nº),Nome do bolsista presente"]
        for data, entrada, saida, nome, mat, maquina, bolsista in dados:
            mat_fmt = "" if not mat or mat == "SERVIDOR" else mat
            linhas.append(f"{data},{entrada},{saida or ''},{nome},{mat_fmt},{maquina or ''},{bolsista or ''}")
        return "\n".join(linhas)

    def _copiar_periodo(self, periodo: str):
        if periodo == "Hoje":
            dados = buscar_export_dia(agora().strftime("%d/%m/%Y"))
        elif periodo == "Ontem":
            dados, _ = buscar_export_ontem()
        elif periodo == "Semana":
            dados = buscar_export_semana(datas_semana_atual())
        elif periodo == "Mês":
            dados = buscar_export_mes(self._mes_ativo())
        else:
            return
        if dados:
            # Copiar dados na mesma ordem do CSV (sem cabeçalho)
            linhas = []
            for data, entrada, saida, nome, matricula, maquina, bolsista in dados:
                mat_fmt = "" if not matricula or matricula == "SERVIDOR" else matricula
                linhas.append(f"{data}\t{entrada}\t{saida or ''}\t{nome}\t{mat_fmt}\t{maquina or ''}\t{bolsista or ''}")
            texto = "\n".join(linhas)
            self.root.clipboard_clear()
            self.root.clipboard_append(texto)
            messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência", parent=self.root)

    def _abrir_copiar_personalizado(self):
        t = TEMAS[self.config["theme"]]
        bg, fg, field, select = t["bg"], t["fg"], t["field"], t["select"]
        win = tk.Toplevel(self.root)
        win.title("Copiar dados para planilha")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=500, min_height=400, resizable=(False, False), escape_close=True)

        var_periodo = tk.StringVar(value=self._mes_ativo())
        periodo_cb = ttk.Combobox(win, textvariable=var_periodo, values=buscar_meses(), width=15, state="readonly")
        periodo_cb.grid(row=0, column=0, columnspan=2, padx=10, pady=(12, 4))

        frame_alunos = tk.Frame(win, bg=bg)
        frame_alunos.grid(row=1, column=0, columnspan=2, padx=10, pady=4, sticky="nsew")
        win.grid_columnconfigure(1, weight=1)
        win.grid_rowconfigure(1, weight=1)

        canvas = tk.Canvas(frame_alunos, bg=bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_alunos, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=bg)

        # Enable mousewheel scrolling (works on Linux via Button-4/Button-5)
        def on_mousewheel(event):
            if event.num == 4:  # Mouse wheel up
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:  # Mouse wheel down
                canvas.yview_scroll(1, "units")

        def bind_mousewheel(widget):
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel(child)

        scroll_frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling - bind at window level for reliable capture
        win.bind("<Button-4>", on_mousewheel)
        win.bind("<Button-5>", on_mousewheel)

        var_todos = tk.IntVar()
        var_alunos = {}
        aluno_cbs = []
        var_por_data = {}  # Track IntVars per data

        def toggle_todos():
            val = var_todos.get()
            for var in var_alunos.values():
                var.set(val)

        def toggle_dia(data, var_dia):
            val = var_dia.get()
            for mat in var_por_data.get(data, []):
                if mat in var_alunos:
                    var_alunos[mat].set(val)

        # Big separator and top "TODOS"
        tk.Frame(scroll_frame, height=1, bg="#444").pack(fill="x", pady=(0, 8))
        tk.Checkbutton(scroll_frame, text="TODOS", variable=var_todos, command=toggle_todos, bd=0, highlightthickness=0,
                       bg=bg, fg=fg, selectcolor=select, activebackground=select,
                       activeforeground=fg, relief="flat").pack(anchor="center")

        def atualizar_alunos():
            for cb in aluno_cbs:
                cb.destroy()
            aluno_cbs.clear()
            var_alunos.clear()

            periodo = var_periodo.get()
            with get_conn() as conn:
                # Período está no formato MM/YYYY
                mes_ano = periodo.split("/")
                # Query includes data, entrada, saida, nome, matricula (newest first)
                registros = conn.execute(
                    "SELECT data, entrada, saida, nome, matricula FROM registros WHERE substr(data, 4, 2) = ? AND substr(data, 7, 4) = ? ORDER BY data DESC, entrada DESC",
                    (mes_ano[0], mes_ano[1])
                ).fetchall()

            # Group by data, with multiple registros per aluno
            ultima_data = None
            mats_por_data = {}
            for data, entrada, saida, nome, mat in registros:
                # Track matriculas per data
                if data not in mats_por_data:
                    mats_por_data[data] = []
                mats_por_data[data].append(mat)

                # Handle None values - replace with empty space
                entrada = entrada or " "
                saida = saida or " "

                # Add date divider with "Todos esta dia" checkbox
                if data != ultima_data:
                    divider = tk.Label(scroll_frame, text=data, bg=bg, fg=fg, font=("Arial", 9, "bold"))
                    divider.pack(anchor="w", pady=(8, 2))

                    # "Todos esta dia" checkbox
                    var_dia = tk.IntVar()
                    var_por_data[data] = []
                    cb_dia = tk.Checkbutton(scroll_frame, text="TODOS (DIA)", variable=var_dia, bd=0, highlightthickness=0,
                                            bg=bg, fg=fg, selectcolor=select, activebackground=select,
                                            activeforeground=fg, relief="flat", command=lambda d=data, v=var_dia: toggle_dia(d, v))
                    cb_dia.pack(anchor="center")
                    # Separator below "todos (dia)"
                    tk.Frame(scroll_frame, height=1, bg="#333").pack(fill="x", pady=(4, 2))
                    ultima_data = data

                var = tk.IntVar()
                var_alunos[mat] = var
                var_por_data[data].append(mat)
                # Create a frame with fixed-width columns and | delimiters
                row_frame = tk.Frame(scroll_frame, bg=bg)
                row_frame.pack(anchor="w")
                tk.Label(row_frame, text="|", width=1, bg=bg, fg=fg).pack(side="left")
                cb_widget = tk.Checkbutton(row_frame, text="", variable=var, bd=0, highlightthickness=0,
                                           bg=bg, fg=fg, selectcolor=select, activebackground=select,
                                           activeforeground=fg, relief="flat")
                cb_widget.pack(side="left")
                tk.Label(row_frame, text="|", width=1, bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text=f"{entrada or ' '}", width=8, anchor="center", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text="|", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text=f"{saida or ' '}", width=8, anchor="center", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text="|", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text=nome, width=25, anchor="w", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text="|", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text=mat, width=12, anchor="center", bg=bg, fg=fg).pack(side="left")
                tk.Label(row_frame, text="|", width=1, bg=bg, fg=fg).pack(side="left")
                aluno_cbs.append(row_frame)

        periodo_cb.bind("<<ComboboxSelected>>", lambda _: (atualizar_alunos(), var_todos.set(0)))
        atualizar_alunos()

        def copiar():
            periodo = var_periodo.get()
            matriculas = [m for m, v in var_alunos.items() if v.get()]

            if var_todos.get():
                dados = buscar_export_mes(periodo)
            elif not matriculas:
                messagebox.showwarning("Aviso", "Selecione ao menos um aluno.", parent=win)
                return
            else:
                with get_conn() as conn:
                    dados = conn.execute(
                        f"SELECT data,entrada,saida,nome,matricula,maquina,bolsista FROM registros WHERE matricula IN ({','.join('?'*len(matriculas))}) ORDER BY data, entrada",
                        matriculas
                    ).fetchall()

            if not dados:
                messagebox.showinfo("Copiar Dados", f"Nenhum registro para o período.", parent=win)
                return

            csv = self._gerar_csv(dados)
            self.root.clipboard_clear()
            self.root.clipboard_append(csv)
            win.destroy()
            messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência", parent=self.root)

        select_btn = "#35383e"
        tk.Button(win, text="COPIAR CSV", command=copiar, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg).grid(row=2, column=0, columnspan=2, pady=12)
        win.bind("<Return>", lambda _: copiar())
        win.bind("<KP_Enter>", lambda _: copiar())

    # ── Janelas auxiliares ────────────────────

    def _visualizar_db(self):
        t = TEMAS[self.config["theme"]]
        bg, fg, field, select = t["bg"], t["fg"], t["field"], t["select"]
        win = tk.Toplevel(self.root)
        win.title("Banco de Dados")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=600, min_height=400, resizable=(True, True), escape_close=True)

        top_bar = tk.Frame(win, bg=bg)
        top_bar.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(top_bar, text="🔍", bg=bg, fg=fg).pack(side="left")
        var_busca = tk.StringVar()
        tk.Entry(top_bar, textvariable=var_busca, width=30, bd=0, highlightthickness=0,
                 bg=field, fg=fg).pack(side="left", padx=4)

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=6, pady=4)

        cols  = ("Nome", "Matrícula", "Data", "Entrada", "Saída", "Máquina", "Bolsista")
        trees: dict[str, ttk.Treeview] = {}
        todos: dict[str, list[tuple]]  = {}

        for mes in buscar_meses():
            frame = tk.Frame(nb, bg=bg)
            nb.add(frame, text=mes)
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for col in cols:
                tree.heading(col, text=col)
            tree.pack(fill="both", expand=True)
            style_db = ttk.Style()
            style_db.theme_use("default")
            style_db.configure("Treeview", background=field, foreground=fg,
                               fieldbackground=field, borderwidth=0, highlightthickness=0)
            style_db.map("Treeview", background=[("selected", select)])
            style_db.configure("Treeview.Heading", background=field, foreground=fg,
                               borderwidth=0, highlightthickness=0)
            trees[mes] = tree

            dados = buscar_registros_por_mes(mes)
            todos[mes] = []
            for r in dados:
                _, nome, matricula, data, entrada, saida, maquina, bolsista, _ = r
                # Handle matricula like main list does
                if not matricula:
                    mat_exib = ""
                elif matricula == "SERVIDOR":
                    mat_exib = "Servidor"
                elif matricula.startswith("SRV-"):
                    mat_exib = "servidor"
                else:
                    mat_exib = matricula
                row = (nome, mat_exib, data, entrada, saida or "", maquina or "-", bolsista or "")
                todos[mes].append(row)
                tree.insert("", "end", values=row)

        def filtrar(*_):
            tab = nb.select()
            if not tab:
                return
            mes   = nb.tab(tab, "text")
            tree  = trees[mes]
            termo = var_busca.get().lower()
            tree.delete(*tree.get_children())
            for row in todos[mes]:
                if termo in row[0].lower() or termo in str(row[1]).lower():
                    tree.insert("", "end", values=row)

        var_busca.trace_add("write", filtrar)
        nb.bind("<<NotebookTabChanged>>", lambda _: filtrar())

    def _abrir_bolsistas(self):
        t = TEMAS[self.config["theme"]]
        bg, fg, field = t["bg"], t["fg"], t["field"]
        select_btn = "#35383e"
        win = tk.Toplevel(self.root)
        win.title("Bolsistas")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=300, min_height=250, resizable=(True, True), escape_close=True)

        lista = tk.Listbox(win, bg=field, fg=fg,
                          highlightthickness=0, bd=0)
        lista.pack(fill="both", expand=True)
        for b in buscar_bolsistas():
            lista.insert(tk.END, b)

        def adicionar():
            nome = self._pedir_input("Adicionar", "Nome:")
            if nome:
                inserir_bolsista(nome)
                lista.insert(tk.END, nome)
                self.combo_bolsista["values"] = buscar_bolsistas()

        def remover():
            sel = lista.curselection()
            if sel:
                nome = lista.get(sel)
                deletar_bolsista(nome)
                lista.delete(sel)
                self.combo_bolsista["values"] = buscar_bolsistas()
                self._focus_matricula()

        tk.Button(win, text="Adicionar", command=adicionar, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg).pack()
        tk.Button(win, text="Remover",   command=remover, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg).pack()

    def _abrir_alunos(self):
        t = TEMAS[self.config["theme"]]
        bg, fg, field = t["bg"], t["fg"], t["field"]
        select_btn = "#35383e"
        win = tk.Toplevel(self.root)
        win.title("Alunos e Servidores")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=500, min_height=350, resizable=(True, True), escape_close=True)

        # Search frame
        search_frame = tk.Frame(win, bg=bg)
        search_frame.pack(fill="x", padx=5, pady=(5, 0))
        tk.Label(search_frame, text="Filtrar (nome ou matrícula):", bg=bg, fg=fg).pack(side="left")
        filtro_var = tk.StringVar()
        filtro_var.trace_add("write", lambda *_: recarregar())
        filtro_entry = tk.Entry(search_frame, textvariable=filtro_var, bd=0, highlightthickness=0,
                                bg=field, fg=fg)
        filtro_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        filtro_entry.focus()

        cols = ("Matrícula / ID", "Nome", "Tipo")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
        style_alunos = ttk.Style()
        style_alunos.theme_use("default")
        style_alunos.configure("Treeview", background=field, foreground=fg,
                               fieldbackground=field, borderwidth=0, highlightthickness=0)
        style_alunos.map("Treeview", background=[("selected", select_btn)])
        for col in cols:
            tree.heading(col, text=col)
        tree.column("Matrícula / ID", width=160)
        tree.column("Nome",           width=260)
        tree.column("Tipo",           width=80)
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        def recarregar():
            tree.delete(*tree.get_children())
            filtro = filtro_var.get().lower()
            for mat, nome, tipo in buscar_todos_alunos():
                if filtro in mat.lower() or filtro in nome.lower():
                    tree.insert("", "end", values=(mat, nome, tipo), tags=(mat,))

        recarregar()

        def editar():
            sel = tree.selection()
            if not sel:
                return
            matricula = tree.item(sel)["tags"][0]
            novo_nome = self._pedir_input(f"Editar — {matricula}", "Novo nome:")
            if novo_nome:
                atualizar_aluno(matricula, novo_nome)
                recarregar()
                self._atualizar_lista()

        def remover():
            sel = tree.selection()
            if not sel:
                return
            matricula, nome, _ = tree.item(sel)["values"]
            if messagebox.askyesno("Confirmar",
                    f"Remover {nome}?\n(registros associados não serão apagados)",
                    parent=self.root):
                deletar_aluno(matricula)
                recarregar()
                self._focus_matricula()

        btn_frame = tk.Frame(win, bg=bg)
        btn_frame.pack(pady=(0, 8))
        tk.Button(btn_frame, text="Editar nome", command=editar, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Remover",     command=remover, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg).pack(side="left", padx=5)

    def _editar_registro(self):
        tree = self.tree
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecione um registro primeiro.", parent=self.root)
            return
        rid = int(tree.item(sel[0])["tags"][0])
        self._abrir_form_edicao(rid)

    def _abrir_form_edicao(self, rid: int):
        reg = buscar_registro_por_id(rid)
        if not reg:
            return
        _, nome, _, data, entrada, saida, maquina, _, _ = reg

        t = TEMAS[self.config["theme"]]
        bg, fg, field = t["bg"], t["fg"], t["field"]
        win = tk.Toplevel(self.root)
        win.title(f"Editar — {nome}")
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=350, min_height=180, resizable=(False, False), escape_close=True)

        campos = {}
        ordem_campos = []  # Track field order for keyboard navigation

        defs   = [
            ("Nome",                  nome),
            ("Data (DD/MM/AAAA)",   data),
            ("Entrada (HH:MM)",     entrada),
            ("Saída (HH:MM)",       saida or ""),
            ("Máquina",             maquina or ""),
        ]
        for i, (label, valor) in enumerate(defs):
            tk.Label(win, text=label, bg=bg, fg=fg).grid(row=i, column=0, sticky="w", padx=10, pady=4)
            e = tk.Entry(win, width=20, bd=0, highlightthickness=0, bg=field, fg=fg)
            e.insert(0, valor)
            e.grid(row=i, column=1, padx=10, pady=4)
            campos[label] = e
            ordem_campos.append(e)

        def format_hora_on_save(valor):
            """Format hora on save/focus-out: accepts 1-4 digits or HH:MM."""
            if not valor:
                return valor
            nums = "".join(c for c in valor if c.isdigit())
            if len(nums) == 4:
                return f"{nums[:2]}:{nums[2:]}"
            elif len(nums) == 3:
                return f"0{nums[:1]}:{nums[1:]}"
            elif len(nums) == 2:
                return f"{nums}:00"  # 99 -> 99:00
            elif len(nums) == 1:
                return f"0{nums}:00"  # 9 -> 09:00
            return valor

        def format_maquina_on_save(valor):
            """Pad single digit machine number only on save/focus-out."""
            if not valor:
                return valor
            # Extract only digits
            nums = "".join(c for c in valor if c.isdigit())
            if len(nums) == 1:
                return nums.zfill(2)
            return valor

        def focus_proximo(event):
            atual = ordem_campos.index(event.widget)
            proximo = (atual + 1) % len(ordem_campos)
            ordem_campos[proximo].focus()
            return "break"

        def focus_anterior(event):
            atual = ordem_campos.index(event.widget)
            anterior = (atual - 1) % len(ordem_campos)
            ordem_campos[anterior].focus()
            return "break"

        selection_on_focus = {}

        def on_focus_in(event):
            """Select all on focus for hora fields, remember for backspace."""
            widget = event.widget
            if label := next((l for l, c in campos.items() if c == widget), None):
                if label in ("Entrada (HH:MM)", "Saída (HH:MM)"):
                    widget.select_from(0)
                    widget.select_to(tk.END)
                    selection_on_focus[widget] = True

        def on_click_move(event):
            """User clicked/moved - next backspace should delete char, not all."""
            widget = event.widget
            if label := next((l for l, c in campos.items() if c == widget), None):
                if label in ("Entrada (HH:MM)", "Saída (HH:MM)"):
                    selection_on_focus.pop(widget, None)

        def clear_hora_on_backspace(event):
            """Clear hour field: if selection exists (from focus), clear all; else normal delete."""
            widget = event.widget
            if label := next((l for l, c in campos.items() if c == widget), None):
                if label in ("Entrada (HH:MM)", "Saída (HH:MM)"):
                    if selection_on_focus.get(widget):
                        # Selection from focus - clear all
                        widget.delete(0, tk.END)
                        selection_on_focus.pop(widget)
                        return "break"
                    # Normal backspace behavior

        for campo in ordem_campos:
            campo.bind("<Tab>", focus_proximo)
            campo.bind("<Shift-Tab>", focus_anterior)
            campo.bind("<Down>", focus_proximo)
            campo.bind("<Up>", focus_anterior)
            if campo in (campos.get("Entrada (HH:MM)"), campos.get("Saída (HH:MM)")):
                campo.bind("<FocusIn>", on_focus_in)
                campo.bind("<Button-1>", on_click_move)
                campo.bind("<ButtonRelease-1>", on_click_move)
                campo.bind("<KeyRelease>", on_click_move)
                campo.bind("<BackSpace>", clear_hora_on_backspace)

        def format_fields_on_focus_out(event):
            """Format hora and maquina fields when they lose focus."""
            widget = event.widget
            valor = widget.get().strip()
            if not valor:
                return
            # Use after to ensure the widget has lost focus
            def aplicar_formatacao():
                if not widget.winfo_ismapped():
                    return
                if widget == campos["Entrada (HH:MM)"]:
                    widget.delete(0, tk.END)
                    widget.insert(0, format_hora_on_save(valor))
                elif widget == campos["Saída (HH:MM)"]:
                    widget.delete(0, tk.END)
                    widget.insert(0, format_hora_on_save(valor))
                elif widget == campos["Máquina"]:
                    widget.delete(0, tk.END)
                    widget.insert(0, format_maquina_on_save(valor))
            win.after(10, aplicar_formatacao)

        # Bind focus-out formatting
        for label in ["Entrada (HH:MM)", "Saída (HH:MM)", "Máquina"]:
            campos[label].bind("<FocusOut>", format_fields_on_focus_out)

        def salvar():
            # Get values and apply formatting
            nova_data    = campos["Data (DD/MM/AAAA)"].get().strip()
            nova_entrada = format_hora_on_save(campos["Entrada (HH:MM)"].get().strip())
            nova_saida   = format_hora_on_save(campos["Saída (HH:MM)"].get().strip()) if campos["Saída (HH:MM)"].get().strip() else ""
            nova_maquina = format_maquina_on_save(campos["Máquina"].get().strip())

            # Update fields with formatted values
            campos["Entrada (HH:MM)"].delete(0, tk.END)
            campos["Entrada (HH:MM)"].insert(0, nova_entrada)
            if nova_saida:
                campos["Saída (HH:MM)"].delete(0, tk.END)
                campos["Saída (HH:MM)"].insert(0, nova_saida)
            if nova_maquina:
                campos["Máquina"].delete(0, tk.END)
                campos["Máquina"].insert(0, nova_maquina)

            try:
                datetime.strptime(nova_data, "%d/%m/%Y")
                dt_entrada = datetime.strptime(nova_entrada, "%H:%M")
                if nova_saida:
                    dt_saida = datetime.strptime(nova_saida, "%H:%M")
                    if dt_saida <= dt_entrada:
                        messagebox.showerror("Horário inválido",
                            "A saída deve ser posterior à entrada.", parent=self.root)
                        return
            except ValueError:
                messagebox.showerror("Formato inválido",
                    "Use DD/MM/AAAA para data e HH:MM para horários.", parent=self.root)
                return
            novo_nome = campos["Nome"].get().strip()
            try:
                self._push_undo({
                    "tipo": "edicao",
                    "nome": nome,
                    "antes": {
                        "id": rid, "data": data, "entrada": entrada,
                        "saida": saida, "maquina": maquina, "nome": nome,
                    },
                })
                atualizar_registro(rid, nova_data, nova_entrada, nova_saida, nova_maquina)
                if novo_nome != nome:
                    atualizar_aluno(reg[2], novo_nome)  # reg[2] is matricula
                self.status(f"Registro de {novo_nome} atualizado.")
            except Exception as e:
                log.error("Falha ao atualizar: %s", e)
                self.status("Erro ao salvar alterações.", erro=True)
                return
            win.destroy()
            self._rebuild_abas()
            self._atualizar_lista()

        select_btn = "#35383e"  # Slightly darker than select
        tk.Button(win, text="Salvar", command=salvar, bd=0, highlightthickness=0,
                  bg=select_btn, fg=t["fg"]).grid(row=len(defs), column=0, columnspan=2, pady=10)
        focus_first_field(campos["Nome"])
        bind_enter_to_button(campos["Nome"], win.winfo_children()[-1])
        win.bind("<Return>", lambda _: salvar())
        win.bind("<KP_Enter>", lambda _: salvar())

    def _pedir_input(self, titulo: str, mensagem: str) -> str | None:
        t = TEMAS[self.config["theme"]]
        bg, fg, field = t["bg"], t["fg"], t["field"]
        win = tk.Toplevel(self.root)
        win.title(titulo)
        win.configure(bg=bg)
        setup_dialog(win, self.root, min_width=300, min_height=100, escape_close=True)

        tk.Label(win, text=mensagem, bg=bg, fg=fg).pack(padx=10, pady=(10, 0))

        entry = tk.Entry(win, bd=0, highlightthickness=0, bg=field, fg=fg)
        entry.pack(padx=10, pady=5)

        resultado = {"valor": None}

        def confirmar():
            resultado["valor"] = entry.get().strip() or None
            win.destroy()

        entry.bind("<Return>", lambda _: confirmar())
        select_btn = "#35383e"
        ok_btn = tk.Button(win, text="OK", command=confirmar, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg)
        ok_btn.pack(pady=(0, 10))
        focus_first_field(entry)
        bind_enter_to_button(entry, ok_btn)
        win.wait_window()
        return resultado["valor"]


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    App(root)
    root.mainloop()
