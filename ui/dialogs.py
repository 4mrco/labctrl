import os
import tkinter as tk
from core.config import TEMAS

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


def mostrar_toast(parent: tk.Tk | tk.Toplevel, mensagem: str, duration: int = 4000):
    """Display a subtle, self-dismissing toast notification at the bottom-right."""
    toast = tk.Toplevel(parent)
    toast.overrideredirect(True)
    toast.transient(parent)
    toast.configure(bg="#222222")
    
    lbl = tk.Label(toast, text=mensagem, bg="#222222", fg="#FFFFFF", font=("Arial", 10), padx=15, pady=8)
    lbl.pack()
    
    toast.update_idletasks()
    
    # Position bottom-right of parent window
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    tw, th = toast.winfo_width(), toast.winfo_height()
    
    # Padding from edges
    pad_x = 20
    pad_y = 20
    
    x = px + pw - tw - pad_x
    y = py + ph - th - pad_y
    toast.geometry(f"+{x}+{y}")
    
    toast.after(duration, toast.destroy)


def renderizar_changelog(widget: tk.Text, raw_text: str):
    """Lightweight Markdown renderer for CHANGELOG.md content.

    Supports only the syntax actually used in LabCTRL:
      # h1  ## h2  ### h3  - bullet  **bold**  `code`
    Everything else is plain text.
    """
    import re
    t = TEMAS["default"]
    fg  = t["fg"]
    bg  = t["bg"]
    field = t["field"]

    # ── Tag definitions ─────────────────────────────────────────────
    widget.tag_configure("h1",     font=("Segoe UI", 13, "bold"),   foreground=fg,        spacing1=12, spacing3=4)
    widget.tag_configure("h2",     font=("Segoe UI", 11, "bold"),   foreground=fg,        spacing1=10, spacing3=2)
    widget.tag_configure("h3",     font=("Segoe UI", 10, "bold"),   foreground="#b0c4de", spacing1=8,  spacing3=1)
    widget.tag_configure("bullet", font=("Segoe UI", 9),            foreground=fg,        lmargin1=12, lmargin2=24)
    widget.tag_configure("normal", font=("Segoe UI", 9),            foreground=fg)
    widget.tag_configure("bold",   font=("Segoe UI", 9, "bold"),   foreground=fg)
    widget.tag_configure("code",   font=("TkFixedFont",),           foreground="#a8d8ea",
                         background=field, relief="flat")
    widget.tag_configure("hr",     font=("Segoe UI", 5),            foreground="#555")

    # ── Inline parser: splits a line into (text, tag) chunks ────────
    _BOLD = re.compile(r"\*\*(.+?)\*\*")
    _CODE = re.compile(r"`([^`]+)`")
    _LINK = re.compile(r"!?\[([^\]]+)\]\([^)]+\)")  # strip markdown links

    def _insert_inline(line: str, base_tag: str):
        """Parse inline **bold** and `code`, inserting mixed chunks."""
        # Strip markdown link syntax, keep display text
        line = _LINK.sub(r"\1", line)
        pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
        parts = pattern.split(line)
        for part in parts:
            if _BOLD.fullmatch(part):
                widget.insert("end", _BOLD.fullmatch(part).group(1), ("bold",))
            elif _CODE.fullmatch(part):
                widget.insert("end", _CODE.fullmatch(part).group(1), ("code",))
            elif part:
                widget.insert("end", part, (base_tag,))

    # ── Line-by-line rendering ───────────────────────────────────────
    widget.configure(state="normal")
    widget.delete("1.0", "end")

    for raw_line in raw_text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("# "):
            widget.insert("end", line[2:] + "\n", ("h1",))
        elif line.startswith("## "):
            widget.insert("end", line[3:] + "\n", ("h2",))
        elif line.startswith("### "):
            widget.insert("end", line[4:] + "\n", ("h3",))
        elif line.startswith("---"):
            widget.insert("end", "\u2015" * 48 + "\n", ("hr",))
        elif line.startswith("- ") or line.startswith("* "):
            widget.insert("end", "\u2022 ", ("bullet",))
            _insert_inline(line[2:], "bullet")
            widget.insert("end", "\n")
        elif line == "":
            widget.insert("end", "\n")
        else:
            _insert_inline(line, "normal")
            widget.insert("end", "\n")

    widget.configure(state="disabled")


def mostrar_sobre(parent: tk.Tk | tk.Toplevel):
    """Open the about dialog."""
    from tkinter.scrolledtext import ScrolledText
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]

    win = tk.Toplevel(parent)
    win.title("Sobre")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=500, min_height=350, resizable=(True, True), escape_close=True)

    from tkinter import ttk
    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    frame_sobre = tk.Frame(notebook, bg=bg)
    notebook.add(frame_sobre, text=" Sobre ")

    # Title
    tk.Label(frame_sobre, text="LabCTRL", font=(None, 14, "bold"),
             bg=bg, fg=fg).pack(pady=(15, 5))

    # Subtitle
    tk.Label(frame_sobre, text="Sistema de Controle de Acesso de Laboratório",
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
    text_widget = tk.Text(frame_sobre, wrap="word", bg=bg, fg=fg, relief="flat",
                          highlightthickness=0, font=(None, 9), padx=5, pady=5, bd=0, height=8)
    text_widget.pack(padx=15, pady=(0, 5), fill="x")
    text_widget.insert("1.0", texto)
    text_widget.configure(state="disabled", cursor="")  # Disabled but selectable

    # Tab 2: Changelog
    frame_notas = tk.Frame(notebook, bg=bg)
    notebook.add(frame_notas, text=" Notas da Versão ")

    # Embedded CHANGELOG.md
    from core.config import BASE_DIR
    changelog_path = os.path.join(BASE_DIR, "CHANGELOG.md")
    try:
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog_txt = f.read()
    except Exception:
        changelog_txt = "(Não foi possível carregar as notas de versão.)"

    cl = ScrolledText(frame_notas, wrap="word", bg=field, fg=fg, relief="flat",
                      highlightthickness=0, font=("Segoe UI", 9), padx=8, pady=6, bd=0)
    cl.pack(padx=10, pady=10, fill="both", expand=True)
    renderizar_changelog(cl, changelog_txt)

    # Close button
    close_btn = tk.Button(win, text="Fechar", width=10, command=win.destroy,
              bg="#35383e", fg=fg, bd=0, highlightthickness=0)
    close_btn.pack(pady=(0, 15))
    bind_enter_to_button(win, close_btn)



def pedir_input(parent: tk.Tk | tk.Toplevel, titulo: str, mensagem: str, valor_inicial: str = "") -> str | None:
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    win = tk.Toplevel(parent)
    win.title(titulo)
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=300, min_height=100, escape_close=True)

    tk.Label(win, text=mensagem, bg=bg, fg=fg).pack(padx=10, pady=(10, 0))

    entry = tk.Entry(win, bd=0, highlightthickness=0, bg=field, fg=fg)
    entry.pack(padx=10, pady=5)
    if valor_inicial:
        entry.insert(0, valor_inicial)
        entry.select_range(0, tk.END)

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


def popup_sem_matricula(parent: tk.Tk | tk.Toplevel) -> tuple[str, str] | None:
    """Retorna (nome, tipo) ou None se cancelado."""
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    win = tk.Toplevel(parent)
    win.title("Entrada sem matrícula")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=320, min_height=140)

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
    return resultado["valor"]


from tkinter import ttk, messagebox, filedialog
import csv
import logging
from datetime import datetime
from core.database import (
    buscar_registro_por_id, atualizar_registro, buscar_meses,
    buscar_registros_por_mes, buscar_bolsistas, inserir_bolsista,
    deletar_bolsista, buscar_todos_alunos, atualizar_aluno, deletar_aluno,
    get_conn, buscar_export_mes, buscar_export_dia, buscar_export_ontem,
    buscar_export_semana
)
from core.services import agora, datas_semana_atual

log = logging.getLogger(__name__)

def gerar_csv(dados: list[tuple]) -> str:
    """Gera CSV com cabeçalho e dados na ordem exigida."""
    linhas = ["Data,Horário Entrada,Horário Saída,Nome,Matrícula,Máquina (Nº),Nome do bolsista presente"]
    for data, entrada, saida, nome, mat, maquina, bolsista in dados:
        mat_fmt = "" if not mat or mat == "SERVIDOR" else mat
        maq_exib = "ML" if str(maquina).startswith("ML-") else maquina
        linhas.append(f"{data},{entrada},{saida or ''},{nome},{mat_fmt},{maq_exib or ''},{bolsista or ''}")
    return "\n".join(linhas)

def copiar_periodo(parent, periodo: str, mes_ativo: str):
    if periodo == "Hoje":
        dados = buscar_export_dia(agora().strftime("%d/%m/%Y"))
    elif periodo == "Ontem":
        dados, _ = buscar_export_ontem()
    elif periodo == "Semana":
        dados = buscar_export_semana(datas_semana_atual())
    elif periodo == "Mês":
        dados = buscar_export_mes(mes_ativo)
    else:
        return
    if dados:
        # Copiar dados na mesma ordem do CSV (sem cabeçalho)
        linhas = []
        for data, entrada, saida, nome, matricula, maquina, bolsista in dados:
            mat_fmt = "" if not matricula or matricula == "SERVIDOR" else matricula
            maq_exib = "ML" if str(maquina).startswith("ML-") else maquina
            linhas.append(f"{data}\t{entrada}\t{saida or ''}\t{nome}\t{mat_fmt}\t{maq_exib or ''}\t{bolsista or ''}")
        texto = "\n".join(linhas)
        parent.clipboard_clear()
        parent.clipboard_append(texto)
        messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência", parent=parent)



# ── Janelas auxiliares ────────────────────



def visualizar_db(parent):
    t = TEMAS["default"]
    bg, fg, field, select = t["bg"], t["fg"], t["field"], t["select"]
    win = tk.Toplevel(parent)
    win.title("Banco de Dados")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=700, min_height=500, resizable=(True, True), escape_close=True)

    # ── Apply clam styles once ───────────────────────────────────
    style_db = ttk.Style()
    style_db.theme_use("clam")
    style_db.configure("Treeview", background=field, foreground=fg,
                       fieldbackground=field, bordercolor=bg,
                       lightcolor=bg, darkcolor=bg,
                       borderwidth=0, relief="flat", highlightthickness=0)
    style_db.map("Treeview",
                background=[("selected", select)],
                foreground=[("selected", fg)])
    style_db.configure("Treeview.Heading", background=bg, foreground=fg,
                       bordercolor=bg, lightcolor=bg, darkcolor=bg,
                       borderwidth=0, highlightthickness=0, relief="flat")
    style_db.map("Treeview.Heading", background=[("active", bg)])
    style_db.configure("Vertical.TScrollbar",
                       background=field, troughcolor=bg, arrowcolor=fg,
                       bordercolor=bg, lightcolor=bg, darkcolor=bg,
                       borderwidth=0, relief="flat", highlightthickness=0)
    style_db.configure("TCombobox",
                       fieldbackground=field, background=field, foreground=fg,
                       bordercolor=bg, lightcolor=bg, darkcolor=bg, arrowcolor=fg,
                       borderwidth=0, relief="flat", highlightthickness=0)
    style_db.map("TCombobox",
                fieldbackground=[("readonly", field)],
                background=[("readonly", field)],
                foreground=[("readonly", fg)])

    # ── TOP: Dashboard cards ─────────────────────────────────────
    dash_frame = tk.Frame(win, bg=bg)
    dash_frame.pack(fill="x", padx=10, pady=(10, 10))

    var_visitas = tk.StringVar(value="-")
    var_pessoas = tk.StringVar(value="-")
    var_tempo   = tk.StringVar(value="-")
    var_media   = tk.StringVar(value="-")

    muted = "#888888"
    for titulo, var in [
        ("Total de Visitas",   var_visitas),
        ("Pessoas Únicas",     var_pessoas),
        ("Média de Visitas/Dia", var_tempo),
        ("Permanência Média",  var_media),
    ]:
        card = tk.Frame(dash_frame, bg=bg)
        card.pack(side="left", expand=True)
        tk.Label(card, text=titulo, font=("Arial", 9), fg=muted, bg=bg).pack()
        tk.Label(card, textvariable=var, font=("Arial", 14, "bold"), fg=fg, bg=bg).pack()

    # ── MIDDLE: Controls (Year + Month Comboboxes + Search) ────────
    control_frame = tk.Frame(win, bg=bg)
    control_frame.pack(fill="x", padx=10, pady=(0, 8))

    meses_raw = buscar_meses()  # ["09/2026", "08/2026", ...]
    nomes_mes = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
                 "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
                 "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
    nomes_mes_rev = {v: k for k, v in nomes_mes.items()}

    # Group months by year: {"2026": ["09", "08", ...], ...}
    from collections import OrderedDict
    anos_map = OrderedDict()
    for m in meses_raw:
        mm, yyyy = m.split("/")
        anos_map.setdefault(yyyy, []).append(mm)
    anos = list(anos_map.keys())

    # Year combobox
    tk.Label(control_frame, text="Ano:", bg=bg, fg=fg, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
    var_ano = tk.StringVar(value=anos[0] if anos else "")
    combo_ano = ttk.Combobox(control_frame, textvariable=var_ano,
                              values=anos, width=6, state="readonly")
    combo_ano.pack(side="left")

    # Month combobox (dependent on year)
    tk.Label(control_frame, text="Mês:", bg=bg, fg=fg, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
    var_mes_nome = tk.StringVar()
    combo_mes_nome = ttk.Combobox(control_frame, textvariable=var_mes_nome,
                                   width=12, state="readonly")
    combo_mes_nome.pack(side="left")

    def _repopular_meses(*_):
        """Repopulate month combobox when year changes, then refresh."""
        y = var_ano.get()
        month_nums = anos_map.get(y, [])
        month_names = [nomes_mes[n] for n in month_nums]
        combo_mes_nome["values"] = month_names
        if month_names:
            combo_mes_nome.set(month_names[0])
        atualizar_tela()

    combo_ano.bind("<<ComboboxSelected>>", _repopular_meses)

    tk.Label(control_frame, text="🔍", bg=bg, fg=fg).pack(side="right", padx=(8, 0))
    var_busca = tk.StringVar()
    tk.Entry(control_frame, textvariable=var_busca, width=28, bd=0, highlightthickness=0,
             bg=field, fg=fg).pack(side="right", padx=(0, 8))

    # ── BOTTOM: Single Treeview ──────────────────────────────────
    tree_frame = tk.Frame(win, bg=bg)
    tree_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    cols = ("Nome", "Matrícula", "Data", "Entrada", "Saída", "Máquina", "Bolsista")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
    col_widths = {"Nome": 160, "Matrícula": 90, "Data": 90, "Entrada": 70,
                  "Saída": 70, "Máquina": 70, "Bolsista": 120}
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=col_widths.get(col, 80), anchor="center")
    tree.column("Nome", anchor="w")

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    # ── Load all month data once ─────────────────────────────────
    todos: dict[str, list[tuple]] = {}
    for mes in meses_raw:
        dados = buscar_registros_por_mes(mes)
        todos[mes] = []
        for r in dados:
            _, nome, matricula, data, entrada, saida, maquina, bolsista, _ = r
            if not matricula:
                mat_exib = ""
            elif matricula == "SERVIDOR":
                mat_exib = "Servidor"
            elif matricula.startswith("SRV-"):
                mat_exib = "Servidor"
            else:
                mat_exib = matricula
            maq_exib = "ML" if str(maquina).startswith("ML-") else maquina
            row = (nome, mat_exib, data, entrada, saida or "", maq_exib or "-", bolsista or "")
            todos[mes].append(row)

    # ── Helpers ──────────────────────────────────────────────────
    def _fmt_mins(total_mins: int) -> str:
        return f"{total_mins // 60}h {total_mins % 60:02d}m"

    # ── Unified update function ──────────────────────────────────
    def atualizar_tela(*_):
        ano = var_ano.get()
        mes_nome = var_mes_nome.get()
        mes_num = nomes_mes_rev.get(mes_nome, "")
        mes_atual = f"{mes_num}/{ano}" if mes_num and ano else ""
        if not mes_atual or mes_atual not in todos:
            return
        termo = var_busca.get().lower()

        # Populate treeview (filtered)
        tree.delete(*tree.get_children())
        for row in todos[mes_atual]:
            if not termo or termo in row[0].lower() or termo in str(row[1]).lower():
                tree.insert("", "end", values=row)

        # Calculate stats from full (unfiltered) month data
        rows = todos[mes_atual]
        visitas = len(rows)
        pessoas = len({row[1] if row[1] else row[0] for row in rows})

        total_mins = 0
        valid_exits = 0
        for row in rows:
            entrada_str = row[3]
            saida_str   = row[4]
            if not saida_str or not entrada_str:
                continue
            try:
                ent = datetime.strptime(entrada_str.strip(), "%H:%M")
                sai = datetime.strptime(saida_str.strip(),   "%H:%M")
                delta = int((sai - ent).total_seconds() // 60)
                if delta > 0:
                    total_mins  += delta
                    valid_exits += 1
            except ValueError:
                pass

        media_mins = (total_mins // valid_exits) if valid_exits else 0

        var_visitas.set(str(visitas))
        var_pessoas.set(str(pessoas))
        
        dias_distintos = len({row[2] for row in rows if row[2]})
        if dias_distintos > 0:
            media = visitas / dias_distintos
            var_tempo.set(f"{media:.1f}".replace(".", ","))
        else:
            var_tempo.set("-")
            
        var_media.set(_fmt_mins(media_mins) if valid_exits else "-")

    combo_mes_nome.bind("<<ComboboxSelected>>", atualizar_tela)
    var_busca.trace_add("write", atualizar_tela)
    _repopular_meses()  # Initial population + first render




def abrir_bolsistas(parent, on_success_callback=None):
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    select_btn = "#35383e"
    win = tk.Toplevel(parent)
    win.title("Bolsistas")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=450, min_height=350, resizable=(True, True), escape_close=True)

    # ── Treeview ────────────────────────────────────────────────
    tree_frame = tk.Frame(win, bg=bg)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))

    style_bolsistas = ttk.Style()
    style_bolsistas.theme_use("clam")
    style_bolsistas.configure("Treeview", background=field, foreground=fg,
                              fieldbackground=field, bordercolor=bg,
                              lightcolor=bg, darkcolor=bg,
                              borderwidth=0, relief="flat", highlightthickness=0)
    style_bolsistas.map("Treeview",
                        background=[("selected", select_btn)],
                        foreground=[("selected", fg)])
    style_bolsistas.configure("Treeview.Heading", background=bg, foreground=fg,
                              bordercolor=bg, lightcolor=bg, darkcolor=bg,
                              borderwidth=0, highlightthickness=0, relief="flat")
    style_bolsistas.map("Treeview.Heading", background=[("active", bg)])
    style_bolsistas.configure("Vertical.TScrollbar",
                              background=field, troughcolor=bg, arrowcolor=fg,
                              bordercolor=bg, lightcolor=bg, darkcolor=bg,
                              borderwidth=0, relief="flat", highlightthickness=0)

    tree = ttk.Treeview(tree_frame, columns=("Nome",), show="headings", selectmode="browse")
    tree.heading("Nome", text="Nome do Bolsista")
    tree.column("Nome", anchor="w")

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    # btn_importar is defined below; recarregar references it via closure
    _btn_importar_ref = []

    def recarregar():
        tree.delete(*tree.get_children())
        lista = buscar_bolsistas()
        for b in lista:
            tree.insert("", "end", values=(b,), tags=(b,))
        # Show Import button only when list is empty
        if _btn_importar_ref:
            if len(lista) == 0:
                _btn_importar_ref[0].pack(side="left", padx=5)
            else:
                _btn_importar_ref[0].pack_forget()

    recarregar()

    # ── Actions ──────────────────────────────────────────────────
    def adicionar():
        nome = pedir_input(win, "Adicionar", "Nome:")
        if nome:
            inserir_bolsista(nome)
            recarregar()
            if on_success_callback:
                on_success_callback()

    def editar():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecione um bolsista primeiro.", parent=win)
            return
        nome_atual = tree.item(sel[0])["values"][0]
        novo_nome = pedir_input(win, "Editar", "Nome:", valor_inicial=nome_atual)
        if novo_nome and novo_nome != nome_atual:
            deletar_bolsista(nome_atual)
            inserir_bolsista(novo_nome)
            recarregar()
            if on_success_callback:
                on_success_callback()

    def remover():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Remover", "Selecione um bolsista primeiro.", parent=win)
            return
        nome = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Remover", f"Remover '{nome}'?", parent=win):
            deletar_bolsista(nome)
            recarregar()
            if on_success_callback:
                on_success_callback()

    def importar_csv():
        path = filedialog.askopenfilename(
            parent=win,
            title="Importar lista de bolsistas",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        importados = 0
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        nome = row[0].strip()
                        if nome:
                            inserir_bolsista(nome)
                            importados += 1
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao importar: {e}", parent=win)
            return
        recarregar()
        if on_success_callback:
            on_success_callback()
        messagebox.showinfo("Importar", f"{importados} bolsista(s) importado(s).", parent=win)

    # ── Buttons ───────────────────────────────────────────────────
    btn_frame = tk.Frame(win, bg=bg)
    btn_frame.pack(pady=(5, 10))
    for label, cmd in [("Adicionar", adicionar), ("Editar", editar), ("Remover", remover)]:
        tk.Button(btn_frame, text=label, command=cmd, bd=0, highlightthickness=0,
                  bg=select_btn, fg=fg, padx=10, pady=4).pack(side="left", padx=5)

    btn_importar = tk.Button(btn_frame, text="Importar CSV", command=importar_csv,
                             bd=0, highlightthickness=0, bg=select_btn, fg=fg, padx=10, pady=4)
    _btn_importar_ref.append(btn_importar)
    # Trigger visibility check now that btn_importar is registered
    recarregar()

    tree.bind("<Double-1>", lambda _: editar())


def abrir_alunos(parent, on_success_callback=None):
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    select_btn = "#35383e"
    win = tk.Toplevel(parent)
    win.title("Alunos e Servidores")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=500, min_height=350, resizable=(True, True), escape_close=True)

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
    style_alunos.theme_use("clam")
    style_alunos.configure("Treeview", background=field, foreground=fg,
                           fieldbackground=field, bordercolor=bg,
                           lightcolor=bg, darkcolor=bg,
                           borderwidth=0, relief="flat", highlightthickness=0)
    style_alunos.map("Treeview",
                    background=[("selected", select_btn)],
                    foreground=[("selected", fg)])
    style_alunos.configure("Treeview.Heading", background=bg, foreground=fg,
                           bordercolor=bg, lightcolor=bg, darkcolor=bg,
                           borderwidth=0, highlightthickness=0, relief="flat")
    style_alunos.map("Treeview.Heading", background=[("active", bg)])
    style_alunos.configure("Vertical.TScrollbar",
                           background=field, troughcolor=bg, arrowcolor=fg,
                           bordercolor=bg, lightcolor=bg, darkcolor=bg,
                           borderwidth=0, relief="flat", highlightthickness=0)
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
        novo_nome = pedir_input(parent, f"Editar — {matricula}", "Novo nome:")
        if novo_nome:
            atualizar_aluno(matricula, novo_nome)
            recarregar()
            if on_success_callback: on_success_callback()

    def remover():
        sel = tree.selection()
        if not sel:
            return
        matricula, nome, _ = tree.item(sel)["values"]
        if messagebox.askyesno("Confirmar",
                f"Remover {nome}?\n(registros associados não serão apagados)",
                parent=parent):
            deletar_aluno(matricula)
            recarregar()
            if on_success_callback: on_success_callback()

    btn_frame = tk.Frame(win, bg=bg)
    btn_frame.pack(pady=(0, 8))
    tk.Button(btn_frame, text="Editar nome", command=editar, bd=0, highlightthickness=0,
              bg=select_btn, fg=fg).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Remover",     command=remover, bd=0, highlightthickness=0,
              bg=select_btn, fg=fg).pack(side="left", padx=5)


def abrir_form_edicao(parent, rid: int, on_success_callback=None):
    reg = buscar_registro_por_id(rid)
    if not reg:
        return
    _, nome, _, data, entrada, saida, maquina, _, _ = reg

    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    win = tk.Toplevel(parent)
    win.title(f"Editar — {nome}")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=350, min_height=180, resizable=(False, False), escape_close=True)

    campos = {}
    ordem_campos = []  # Track field order for keyboard navigation

    defs   = [
        ("Nome",                  nome),
        ("Data (DD/MM/AAAA)",   data),
        ("Entrada (HH:MM)",     entrada),
        ("Saída (HH:MM)",       saida or ""),
        ("Máquina",             "ML" if str(maquina).startswith("ML-") else (maquina or "")),
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
        
        # Preserve original ML-X if the user left it as "ML"
        if nova_maquina == "ML" and str(maquina).startswith("ML-"):
            nova_maquina = maquina

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
                        "A saída deve ser posterior à entrada.", parent=parent)
                    return
        except ValueError:
            messagebox.showerror("Formato inválido",
                "Use DD/MM/AAAA para data e HH:MM para horários.", parent=parent)
            return
        novo_nome = campos["Nome"].get().strip()
        try:
            undo_payload = {
                "tipo": "edicao",
                "nome": nome,
                "antes": {
                    "id": rid, "data": data, "entrada": entrada,
                    "saida": saida, "maquina": maquina, "nome": nome,
                    "matricula": reg[2],
                },
            }
            atualizar_registro(rid, novo_nome, nova_data, nova_entrada, nova_saida, nova_maquina)
            if reg[2] and novo_nome != nome:
                atualizar_aluno(reg[2], novo_nome)  # reg[2] is matricula
            status_msg = f"Registro de {novo_nome} atualizado."
        except Exception as e:
            log.error("Falha ao atualizar: %s", e)
            if on_success_callback: on_success_callback(None, "Erro ao salvar alterações.", True)
            return
        win.destroy()
        if on_success_callback: on_success_callback(undo_payload, status_msg, False)

    select_btn = "#35383e"  # Slightly darker than select
    tk.Button(win, text="Salvar", command=salvar, bd=0, highlightthickness=0,
              bg=select_btn, fg=t["fg"]).grid(row=len(defs), column=0, columnspan=2, pady=10)
    focus_first_field(campos["Nome"])
    bind_enter_to_button(campos["Nome"], win.winfo_children()[-1])
    win.bind("<Return>", lambda _: salvar())
    win.bind("<KP_Enter>", lambda _: salvar())

# ── Nova Janela Unificada Exportar / Copiar ──────────────

def abrir_janela_exportar(parent, mes_ativo_default: str, callback_acao):
    """Abre janela unificada para Exportar (CSV) ou Copiar Dados."""
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    titulo = "Exportar / Copiar Dados"
    
    win = tk.Toplevel(parent)
    win.title(titulo)
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=380, min_height=260,
                 resizable=(False, False), escape_close=True)

    tk.Label(win, text="Selecione o período desejado:",
             bg=bg, fg=fg, font=("Segoe UI", 11, "bold")).pack(pady=(16, 10))

    var_periodo = tk.StringVar(value="Hoje")
    frame_radios = tk.Frame(win, bg=bg)
    frame_radios.pack(pady=5)

    # Reusing months logic
    meses_raw = buscar_meses()
    nomes_mes = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
                 "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
                 "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
    nomes_mes_rev = {v: k for k, v in nomes_mes.items()}
    
    from collections import OrderedDict
    anos_map = OrderedDict()
    for m in meses_raw:
        mm, yyyy = m.split("/")
        anos_map.setdefault(yyyy, []).append(mm)
    anos = list(anos_map.keys())

    frame_mes = tk.Frame(win, bg=bg)
    
    # Year combobox
    tk.Label(frame_mes, text="Ano:", bg=bg, fg=fg, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
    var_ano = tk.StringVar()
    combo_ano = ttk.Combobox(frame_mes, textvariable=var_ano, values=anos, width=6, state="readonly")
    combo_ano.pack(side="left")

    # Month combobox
    tk.Label(frame_mes, text="Mês:", bg=bg, fg=fg, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
    var_mes_nome = tk.StringVar()
    combo_mes_nome = ttk.Combobox(frame_mes, textvariable=var_mes_nome, width=12, state="readonly")
    combo_mes_nome.pack(side="left")

    def _repopular_meses(*_):
        y = var_ano.get()
        month_nums = anos_map.get(y, [])
        month_names = [nomes_mes[n] for n in month_nums]
        combo_mes_nome["values"] = month_names
        if month_names:
            combo_mes_nome.set(month_names[0])
            
    combo_ano.bind("<<ComboboxSelected>>", _repopular_meses)

    # Initialize combos to mes_ativo_default if possible
    if mes_ativo_default:
        mm_def, yyyy_def = mes_ativo_default.split("/")
        if yyyy_def in anos_map:
            var_ano.set(yyyy_def)
            _repopular_meses()
            nome_def = nomes_mes.get(mm_def)
            if nome_def in combo_mes_nome["values"]:
                var_mes_nome.set(nome_def)
    elif anos:
        var_ano.set(anos[0])
        _repopular_meses()

    def _update_ui(*_):
        if var_periodo.get() == "Mês":
            frame_mes.pack(pady=10)
        else:
            frame_mes.pack_forget()

    for p in ["Hoje", "Ontem", "Semana", "Mês"]:
        tk.Radiobutton(frame_radios, text=p, variable=var_periodo, value=p,
                       bg=bg, fg=fg, selectcolor=field, activebackground=bg, bd=0, highlightthickness=0,
                       activeforeground=fg, command=_update_ui).pack(side="left", padx=5)
                       
    _update_ui()

    def _executar(modo: str):
        periodo = var_periodo.get()
        mes_str = None
        if periodo == "Mês":
            ano = var_ano.get()
            mes_nome = var_mes_nome.get()
            mes_num = nomes_mes_rev.get(mes_nome, "")
            mes_str = f"{mes_num}/{ano}" if mes_num and ano else ""
        
        callback_acao(modo, periodo, mes_str)
        win.destroy()

    btn_frame = tk.Frame(win, bg=bg)
    btn_frame.pack(pady=(15, 10))
    
    tk.Button(btn_frame, text="Exportar arquivo CSV", command=lambda: _executar("exportar"),
              bd=0, highlightthickness=0, bg="#35383e", fg=fg,
              padx=15, pady=6, font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)
              
    tk.Button(btn_frame, text="Copiar p. área de transf.", command=lambda: _executar("copiar"),
              bd=0, highlightthickness=0, bg="#35383e", fg=fg,
              padx=15, pady=6, font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)



