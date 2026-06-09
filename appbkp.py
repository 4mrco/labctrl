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
        return {"theme": "light", "exported_months": [], "ultimo_bolsista": None}
    cfg = json.load(open(CONFIG_FILE, "r"))
    cfg.setdefault("exported_months", [])
    cfg.setdefault("ultimo_bolsista", None)
    return cfg


def save_config(cfg: dict) -> None:
    json.dump(cfg, open(CONFIG_FILE, "w"))


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
            """SELECT id,nome,matricula,data,entrada,saida,maquina,status
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
# APLICAÇÃO (UI)
# ─────────────────────────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Controle de Laboratório")
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

        # Dashboard stats in header
        self.lbl_dashboard = tk.Label(self.header, text="")
        self.lbl_dashboard.pack(side="left", padx=16)

        # Filter buttons
        self.var_filtro = tk.StringVar(value="Mês")
        self._btns_filtro = {}
        for opcao in ("Hoje", "Ativos", "Mês"):
            b = tk.Button(
                self.header,
                text=opcao,
                width=7,
                command=lambda o=opcao: self._set_filtro(o),
                relief="flat",
                bd=0,
                highlightthickness=0,
                padx=10,
                pady=4,
                )
            b.pack(side="left", padx=2)
            self._btns_filtro[opcao] = b

        self.lbl_clock = tk.Label(self.header, text="")
        self.lbl_clock.pack(side="right", padx=12)

        
        # CONTROLS TOOLBAR
        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(fill="x", padx=12, pady=8)

        # Matrícula entry with placeholder
        self.entry_matricula = tk.Entry(self.toolbar, width=16)
        self.entry_matricula.pack(side="left", padx=(0, 8))
        self.entry_matricula.bind("<Return>", self.registrar_entrada)
        self.entry_matricula.bind("<Tab>", self._focus_maquina)
        self.entry_matricula.bind("<KeyRelease>", self._validate_matricula)
        self.entry_matricula.focus()

        # Placeholder handling - entry uses normal text variable, placeholder drawn manually
        self._ph_matricula = tk.StringVar(value="Matrícula")
        self.entry_matricula.configure(textvariable=self._ph_matricula, fg="#B5BAC1")
        self.entry_matricula.bind("<FocusIn>", lambda e: self._on_entry_focus(e))
        self.entry_matricula.bind("<FocusOut>", lambda e: self._on_entry_focus_out(e))

        # Month selector - separate row below toolbar
        self.frame_mes = tk.Frame(self.root)
        self.frame_mes.pack(fill="x", padx=12, pady=(0, 4))
        self.lbl_mes = tk.Label(self.frame_mes, text="Mês:", anchor="w")
        self.lbl_mes.pack(side="left", padx=(0, 4))
        self.combo_mes = ttk.Combobox(
            self.frame_mes, values=[], width=14, state="readonly"
        )
        self.combo_mes.pack(side="left", padx=(0, 8))
        self.combo_mes.bind("<<ComboboxSelected>>", self._on_mes_change)

        # Máquina combobox
        self.combo_maquina = ttk.Combobox(
            self.toolbar, values=["-", "ML"] + [f"{i:02}" for i in range(1, 21)],
            width=6, state="normal",
        )
        self.combo_maquina.set("-")
        self.combo_maquina.bind("<Return>", self.registrar_entrada)
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
        self.combo_bolsista.bind("<Tab>", self._focus_matricula_from_bolsista)
        self.combo_bolsista.bind("<FocusIn>", self._on_bolsista_focus_in)
        self.combo_bolsista.pack(side="left", padx=8)

        # ENTRADA button
        self.btn_entrada = tk.Button(self.toolbar, text="ENTRADA",
                                     command=self.registrar_entrada, width=10)
        self.btn_entrada.pack(side="left", padx=(12, 0))

        # ── MENU POPUP ──────────────────────────
        self.btn_menu = tk.Button(self.header, text="≡", width=3, relief="flat")
        self.btn_menu.pack(side="right", padx=8)
        self.btn_menu.bind("<Button-1>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Editar selecionado", command=self._editar_registro)
        self.menu.add_command(label="Remover selecionado", command=self._remover_registro)
        self.menu.add_separator()

        export_menu = tk.Menu(self.menu, tearoff=0)
        export_menu.add_command(label="Dia", command=self._exportar_dia)
        export_menu.add_command(label="Ontem", command=self._exportar_ontem)
        export_menu.add_command(label="Semana", command=self._exportar_semana)
        export_menu.add_command(label="Mês", command=self._exportar_mes)
        self.menu.add_cascade(label="Exportar", menu=export_menu)

        self.menu.add_command(label="Visualizar DB", command=self._visualizar_db)
        self.menu.add_separator()
        self.menu.add_command(label="Bolsistas", command=self._abrir_bolsistas)
        self.menu.add_command(label="Alunos / Servidores", command=self._abrir_alunos)
        self.menu.add_separator()
        self.menu.add_command(label="Alternar Tema", command=self._toggle_tema)

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
        self.btn_saida = tk.Button(
        self.bottom_bar,
        text="Registrar Saída",
        command=self._saida_selecionado,
        state="disabled",
        width=12,
        relief="flat",
        bd=0,
        highlightthickness=0,
        )
        self.btn_saida.pack(side="right", padx=6)

        self.btn_desfazer = tk.Button(
        self.bottom_bar,
        text="↶",
        command=self._desfazer,
        width=3,
        relief="flat",
        bd=0,
        highlightthickness=0,
        )
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

        self.btn_menu.bind(
            "<Button-1>",
            lambda e: self.menu.tk_popup(e.x_root, e.y_root),
        )

    # ── Filtro ───────────────────────────────

    def _set_filtro(self, opcao: str):
        self.var_filtro.set(opcao)
        self._aplicar_tema()  # Re-color filter buttons
        self._atualizar_lista()

    # ── Popup entrada sem matrícula ──────────

    def _popup_sem_matricula(self) -> tuple[str, str] | None:
        """Retorna (nome, tipo) ou None se cancelado."""
        win = tk.Toplevel(self.root)
        win.title("Entrada sem matrícula")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Nome:").grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        entry_nome = tk.Entry(win, width=28)
        entry_nome.grid(row=0, column=1, padx=10, pady=(12, 4))
        entry_nome.focus()

        tk.Label(win, text="Tipo:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        var_tipo = tk.StringVar(value="Aluno")
        frame_tipo = tk.Frame(win)
        frame_tipo.grid(row=1, column=1, sticky="w", padx=10, pady=4)
        tk.Radiobutton(frame_tipo, text="Aluno",    variable=var_tipo, value="Aluno").pack(side="left")
        tk.Radiobutton(frame_tipo, text="Servidor", variable=var_tipo, value="Servidor").pack(side="left")

        resultado = {"valor": None}

        def confirmar(event=None):
            nome = entry_nome.get().strip()
            if not nome:
                return
            resultado["valor"] = (nome, var_tipo.get())
            win.destroy()

        entry_nome.bind("<Return>", confirmar)
        win.bind("<Return>", confirmar)
        tk.Button(win, text="Salvar", command=confirmar).grid(
            row=2, column=0, columnspan=2, pady=(4, 12))
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
            lambda: self.lbl_status.config(text="Pronto")
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
        """Populate month combobox and initialize sort state."""
        self.combo_mes["values"] = self._meses_formatados()
        # Select current month if available
        hoje = agora().strftime("%d/%m/%Y")
        mes_atual = hoje[3:]
        formatted = self._meses_formatados()
        for f in formatted:
            if self._parse_mes_combo(f) == mes_atual:
                self.combo_mes.set(f)
                break
        if not self.combo_mes.get() and formatted:
            self.combo_mes.set(formatted[0])

        self._sort_state.clear()
        self._atualizar_lista()

    def _mes_ativo(self) -> str:
        """Return the currently selected month in DD/MM/YYYY format (using current day)."""
        mes_combo = self.combo_mes.get()
        if not mes_combo:
            return agora().strftime("%m/%Y")
        return self._parse_mes_combo(mes_combo)

    # ── Ordenação por coluna ─────────────────

    def _ordenar(self, col: str, evento=None):
        mes = self.combo_mes.get()
        if not mes:
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

    def _on_mes_change(self, event=None):
        self._sort_state.clear()
        self._atualizar_lista()

    # ── Eventos ──────────────────────────────

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

    def _on_double_click(self, event=None):
        item = self.tree.identify_row(event.y)
        if item:
            rid = int(self.tree.item(item)["tags"][0])
            self._abrir_form_edicao(rid)

    def _saida_selecionado(self):
        sel = self.tree.selection()
        if not sel:
            return
        rid = int(self.tree.item(sel[0])["tags"][0])
        self._registrar_saida_por_rid(rid)

    def _registrar_saida_por_rid(self, rid: int):
        reg = buscar_registro_por_id(rid)
        if not reg or reg[8] != "ATIVO":
            return
        try:
            finalizar_registro(rid, agora().strftime("%H:%M"))
            self._push_undo({"tipo": "saida", "rid": rid, "nome": reg[1]})
            self.status(f"Saída de {reg[1]} registrada.")
        except Exception as e:
            log.error("Falha ao registrar saída: %s", e)
            self.status("Erro ao registrar saída.", erro=True)
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
        if messagebox.askyesno("Confirmar", "Remover registro?"):
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

        # Parse selected month
        mes_combo = self.combo_mes.get()
        if not mes_combo:
            return
        mes = self._parse_mes_combo(mes_combo)

        # Clear and configure tree
        self.tree.delete(*self.tree.get_children())

        self.tree.tag_configure("ATIVO", background=t["ativo_bg"])
        self.tree.tag_configure("FINALIZADO", background=t["bg"])

        registros = buscar_registros_por_mes(mes)

        # Apply filters based on var_filtro
        filtro = self.var_filtro.get() if hasattr(self, 'var_filtro') else "Mês"
        if filtro == "Hoje":
            registros = [r for r in registros if r[3] == hoje]
        elif filtro == "Ativos":
            registros = [r for r in registros if r[7] == "ATIVO"]

        # Populate with zebra striping
        for i, r in enumerate(registros):
            rid, nome, matricula, data, entrada, saida, maquina, status = r
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
                tags = (str(rid), status, str(i % 2))

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
        self.lbl_dashboard.config(text=f"Hoje: {total} | Ativos: {ativos}")

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

        style = ttk.Style()
        style.theme_use("default")

        self.root.configure(bg=bg)
        self.header.configure(bg=bg)
        self.toolbar.configure(bg=bg)
        self.tree_frame.configure(bg=bg)
        self.bottom_bar.configure(bg=bg)
        if hasattr(self, 'frame_mes'):
            self.frame_mes.configure(bg=bg)

        self.sep_header.configure(bg=field)

        self.lbl_title.configure(bg=bg, fg=fg)
        self.lbl_dashboard.configure(bg=bg, fg=fg)
        self.lbl_clock.configure(bg=bg, fg=fg)
        self.lbl_mes.configure(bg=bg, fg=fg)
        self.lbl_selecionados.configure(bg=bg, fg=fg)
        self.lbl_registros.configure(bg=bg, fg=fg)
        self.lbl_status.configure(bg=bg, fg=fg)

        # Toolbar buttons
        self.btn_entrada.configure(bg=field, fg=fg, activebackground=select, disabledforeground="#888888")
        self.btn_saida.configure(bg=field, fg=fg, activebackground=select, disabledforeground="#888888")
        self.btn_desfazer.configure(bg=field, fg=fg, activebackground=select)

        # Style filter buttons in header
        for nome, btn in self._btns_filtro.items():
            ativo = nome == self.var_filtro.get()
            btn.configure(
                bg=select if ativo else field, fg=fg,
                activebackground=select,
                relief="sunken" if ativo else "raised",
            )

        if not self.entry_matricula.get() or self.entry_matricula.get() == "Matrícula":
            self.entry_matricula.configure(bg=field, fg="#B5BAC1", insertbackground=fg, disabledbackground=field)
        else:
            self.entry_matricula.configure(bg=field, fg=fg, insertbackground=fg, disabledbackground=field)

        # Configure dark theme for all ttk widgets
        style.configure("TFrame", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=field, foreground=fg)
        style.configure("TCombobox",
            fieldbackground=field, background=field, foreground=fg)
        style.map("TCombobox",
            fieldbackground=[("readonly", field)],
            background=[("readonly", field)],
            foreground=[("readonly", fg)])

        style.configure("Treeview",
            background=bg, foreground=fg, fieldbackground=field,
            borderwidth=0, highlightthickness=0)
        style.map("Treeview",
            background=[("selected", select)])
        style.configure("Treeview.Heading",
            background=field, foreground=fg, borderwidth=0)
        style.map("Treeview.Heading",
            background=[("active", field)])

        # Configure vertical scrollbar
        style.configure("Vertical.TScrollbar",
            background=field, troughcolor=bg, arrowcolor=fg, borderwidth=0)
        style.map("Vertical.TScrollbar",
            background=[("active", select)],
            arrowcolor=[("active", select)])
        self.tree_scroll.configure(style="Vertical.TScrollbar")

        # Configure menu button
        self.btn_menu.configure(bg=field, fg=fg, activebackground=select, relief="flat")

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
                f"O mês {mes_ant} ainda não foi exportado.\n\nExportar agora?"):
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
            messagebox.showinfo("Exportar", f"Nenhum registro para {titulo}.")
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
        caminho = os.path.join(BASE_DIR, nome_arquivo)
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
        messagebox.showinfo("Exportado", f"Arquivo salvo: {nome_arquivo}")

        # Abre a pasta onde o arquivo foi salvo
        import subprocess
        try:
            subprocess.Popen(["xdg-open", os.path.dirname(os.path.abspath(caminho))])
        except Exception:
            pass


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
            messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência")

    def _abrir_copiar_personalizado(self):
        win = tk.Toplevel(self.root)
        win.title("Copiar dados para planilha")
        win.resizable(False, False)
        win.grab_set()

        var_periodo = tk.StringVar(value=self._mes_ativo())
        periodo_cb = ttk.Combobox(win, textvariable=var_periodo, values=buscar_meses(), width=15, state="readonly")
        periodo_cb.grid(row=0, column=0, columnspan=2, padx=10, pady=(12, 4))

        frame_alunos = tk.Frame(win)
        frame_alunos.grid(row=1, column=0, columnspan=2, padx=10, pady=4)
        canvas = tk.Canvas(frame_alunos, width=280, height=200)
        scrollbar = ttk.Scrollbar(frame_alunos, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        var_todos = tk.IntVar()
        var_alunos = {}
        aluno_cbs = []

        def toggle_todos():
            for var in var_alunos.values():
                var.set(var_todos.get())

        tk.Checkbutton(scroll_frame, text="Todos", variable=var_todos, command=toggle_todos).pack(anchor="w")

        def atualizar_alunos():
            for cb in aluno_cbs:
                cb.destroy()
            aluno_cbs.clear()
            var_alunos.clear()

            periodo = var_periodo.get()
            with get_conn() as conn:
                # Período está no formato MM/YYYY, data no formato DD/MM/YYYY
                mes_ano = periodo.split("/")
                # data[4:6] = MM, data[7:11] = YYYY
                registros = conn.execute(
                    "SELECT DISTINCT matricula, nome FROM registros WHERE substr(data, 4, 2) = ? AND substr(data, 7, 4) = ? ORDER BY nome",
                    (mes_ano[0], mes_ano[1])
                ).fetchall()

            for mat, nome in registros:
                var = tk.IntVar()
                var_alunos[mat] = var
                cb = tk.Checkbutton(scroll_frame, text=f"{nome} - {mat}", variable=var)
                cb.pack(anchor="w")
                aluno_cbs.append(cb)

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
            messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência")

        tk.Button(win, text="COPIAR CSV", command=copiar).grid(row=2, column=0, columnspan=2, pady=12)
        win.bind("<Return>", lambda _: copiar())

    # ── Janelas auxiliares ────────────────────

    def _visualizar_db(self):
        win = tk.Toplevel(self.root)
        win.title("Banco de Dados")
        win.geometry("720x500")

        top_bar = tk.Frame(win)
        top_bar.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(top_bar, text="🔍").pack(side="left")
        var_busca = tk.StringVar()
        tk.Entry(top_bar, textvariable=var_busca, width=30).pack(side="left", padx=4)

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=6, pady=4)

        cols  = ("Nome", "Matrícula", "Data", "Entrada", "Saída", "Máquina", "Bolsista")
        trees: dict[str, ttk.Treeview] = {}
        todos: dict[str, list[tuple]]  = {}

        for mes in buscar_meses():
            frame = tk.Frame(nb)
            nb.add(frame, text=mes)
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            for col in cols:
                tree.heading(col, text=col)
            tree.pack(fill="both", expand=True)
            trees[mes] = tree

            dados     = buscar_registros_por_mes(mes)
            todos[mes] = [
                (r[1], r[2] if not r[2].startswith("SRV-") else "servidor",
                 r[3], r[4], r[5] or "", r[6] or "-", "")
                for r in dados
            ]
            for row in todos[mes]:
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
        win = tk.Toplevel(self.root)
        win.title("Bolsistas")

        lista = tk.Listbox(win)
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

        tk.Button(win, text="Adicionar", command=adicionar).pack()
        tk.Button(win, text="Remover",   command=remover).pack()

    def _abrir_alunos(self):
        win = tk.Toplevel(self.root)
        win.title("Alunos e Servidores")
        win.geometry("540x420")

        # Search frame
        search_frame = tk.Frame(win)
        search_frame.pack(fill="x", padx=5, pady=(5, 0))
        tk.Label(search_frame, text="Filtrar (nome ou matrícula):").pack(side="left")
        filtro_var = tk.StringVar()
        filtro_var.trace("w", lambda *_: recarregar())
        filtro_entry = tk.Entry(search_frame, textvariable=filtro_var)
        filtro_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        filtro_entry.focus()

        cols = ("Matrícula / ID", "Nome", "Tipo")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="browse")
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
                    parent=win):
                deletar_aluno(matricula)
                recarregar()
                self._focus_matricula()

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=(0, 8))
        tk.Button(btn_frame, text="Editar nome", command=editar).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Remover",     command=remover).pack(side="left", padx=5)

    def _editar_registro(self):
        tree = self.tree
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecione um registro primeiro.")
            return
        rid = int(tree.item(sel[0])["tags"][0])
        self._abrir_form_edicao(rid)

    def _abrir_form_edicao(self, rid: int):
        reg = buscar_registro_por_id(rid)
        if not reg:
            return
        _, nome, _, data, entrada, saida, maquina, _, _ = reg

        win = tk.Toplevel(self.root)
        win.title(f"Editar — {nome}")
        win.resizable(False, False)

        campos = {}
        ordem_campos = []  # Track field order for keyboard navigation

        defs   = [
            ("Data (DD/MM/AAAA)",   data),
            ("Entrada (HH:MM)",     entrada),
            ("Saída (HH:MM)",       saida or ""),
            ("Máquina",             maquina or ""),
        ]
        for i, (label, valor) in enumerate(defs):
            tk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=4)
            e = tk.Entry(win, width=20)
            e.insert(0, valor)
            e.grid(row=i, column=1, padx=10, pady=4)
            campos[label] = e
            ordem_campos.append(e)

        def format_hora_on_save(valor):
            """Format HHMM -> HH:MM only on save/focus-out."""
            if not valor:
                return valor
            nums = "".join(c for c in valor if c.isdigit())
            if len(nums) == 4:
                return f"{nums[:2]}:{nums[2:]}"
            elif len(nums) == 3:
                return f"0{nums[:1]}:{nums[1:]}"
            return valor

        def format_maquina_on_save(valor):
            """Pad single digit machine number only on save/focus-out."""
            if valor and valor not in ("-", "ML") and len(valor) == 1 and valor.isdigit():
                return valor.zfill(2)
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

        # Bind keyboard navigation
        for campo in ordem_campos:
            campo.bind("<Tab>", focus_proximo)
            campo.bind("<Shift-Tab>", focus_anterior)
            campo.bind("<Down>", focus_proximo)
            campo.bind("<Up>", focus_anterior)

        def format_fields_on_focus_out(event):
            """Format hora and maquina fields when they lose focus."""
            widget = event.widget
            label = None
            for l, c in campos.items():
                if c == widget:
                    label = l
                    break
            if label == "Entrada (HH:MM)" or label == "Saída (HH:MM)":
                valor = format_hora_on_save(widget.get().strip())
                widget.delete(0, tk.END)
                widget.insert(0, valor)
            elif label == "Máquina":
                valor = format_maquina_on_save(widget.get().strip())
                widget.delete(0, tk.END)
                widget.insert(0, valor)

        # Bind focus-out formatting
        for label in ["Entrada (HH:MM)", "Saída (HH:MM)", "Máquina"]:
            campos[label].bind("<FocusOut>", format_fields_on_focus_out)

        def salvar():
            nova_data    = campos["Data (DD/MM/AAAA)"].get().strip()
            nova_entrada = format_hora_on_save(campos["Entrada (HH:MM)"].get().strip())
            nova_saida   = format_hora_on_save(campos["Saída (HH:MM)"].get().strip())
            nova_maquina = format_maquina_on_save(campos["Máquina"].get().strip())
            try:
                datetime.strptime(nova_data, "%d/%m/%Y")
                dt_entrada = datetime.strptime(nova_entrada, "%H:%M")
                if nova_saida:
                    dt_saida = datetime.strptime(nova_saida, "%H:%M")
                    if dt_saida <= dt_entrada:
                        messagebox.showerror("Horário inválido",
                            "A saída deve ser posterior à entrada.", parent=win)
                        return
            except ValueError:
                messagebox.showerror("Formato inválido",
                    "Use DD/MM/AAAA para data e HH:MM para horários.", parent=win)
                return
            try:
                self._push_undo({
                    "tipo": "edicao",
                    "nome": nome,
                    "antes": {
                        "id": rid, "data": data, "entrada": entrada,
                        "saida": saida, "maquina": maquina,
                    },
                })
                atualizar_registro(rid, nova_data, nova_entrada, nova_saida, nova_maquina)
                self.status(f"Registro de {nome} atualizado.")
            except Exception as e:
                log.error("Falha ao atualizar: %s", e)
                self.status("Erro ao salvar alterações.", erro=True)
                return
            win.destroy()
            self._rebuild_abas()
            self._atualizar_lista()

        tk.Button(win, text="Salvar", command=salvar).grid(
            row=len(defs), column=0, columnspan=2, pady=10)
        win.bind("<Return>", lambda _: salvar())

    def _pedir_input(self, titulo: str, mensagem: str) -> str | None:
        win = tk.Toplevel(self.root)
        win.title(titulo)
        tk.Label(win, text=mensagem).pack(padx=10, pady=(10, 0))

        entry = tk.Entry(win)
        entry.pack(padx=10, pady=5)
        entry.focus()

        resultado = {"valor": None}

        def confirmar():
            resultado["valor"] = entry.get().strip() or None
            win.destroy()

        entry.bind("<Return>", lambda _: confirmar())
        tk.Button(win, text="OK", command=confirmar).pack(pady=(0, 10))
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