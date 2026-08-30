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


def mostrar_sobre(parent: tk.Tk | tk.Toplevel):
    """Open the about dialog."""
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]

    win = tk.Toplevel(parent)
    win.title("Sobre")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=400, min_height=200, resizable=(False, False), escape_close=True)

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


def pedir_input(parent: tk.Tk | tk.Toplevel, titulo: str, mensagem: str) -> str | None:
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    win = tk.Toplevel(parent)
    win.title(titulo)
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=300, min_height=100, escape_close=True)

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


from tkinter import ttk, messagebox
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
        linhas.append(f"{data},{entrada},{saida or ''},{nome},{mat_fmt},{maquina or ''},{bolsista or ''}")
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
            linhas.append(f"{data}\t{entrada}\t{saida or ''}\t{nome}\t{mat_fmt}\t{maquina or ''}\t{bolsista or ''}")
        texto = "\n".join(linhas)
        parent.clipboard_clear()
        parent.clipboard_append(texto)
        messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência", parent=parent)


def abrir_copiar_personalizado(parent, mes_ativo: str):
    t = TEMAS["default"]
    bg, fg, field, select = t["bg"], t["fg"], t["field"], t["select"]
    win = tk.Toplevel(parent)
    win.title("Copiar dados para planilha")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=500, min_height=400, resizable=(False, False), escape_close=True)

    var_periodo = tk.StringVar(value=mes_ativo)
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

        csv = gerar_csv(dados)
        parent.clipboard_clear()
        parent.clipboard_append(csv)
        win.destroy()
        messagebox.showinfo("Copiar Dados", "Copiado para a área de transferência", parent=parent)

    select_btn = "#35383e"
    tk.Button(win, text="COPIAR CSV", command=copiar, bd=0, highlightthickness=0,
              bg=select_btn, fg=fg).grid(row=2, column=0, columnspan=2, pady=12)
    win.bind("<Return>", lambda _: copiar())
    win.bind("<KP_Enter>", lambda _: copiar())

# ── Janelas auxiliares ────────────────────


def visualizar_db(parent):
    t = TEMAS["default"]
    bg, fg, field, select = t["bg"], t["fg"], t["field"], t["select"]
    win = tk.Toplevel(parent)
    win.title("Banco de Dados")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=600, min_height=400, resizable=(True, True), escape_close=True)

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


def abrir_bolsistas(parent, on_success_callback=None):
    t = TEMAS["default"]
    bg, fg, field = t["bg"], t["fg"], t["field"]
    select_btn = "#35383e"
    win = tk.Toplevel(parent)
    win.title("Bolsistas")
    win.configure(bg=bg)
    setup_dialog(win, parent, min_width=300, min_height=250, resizable=(True, True), escape_close=True)

    lista = tk.Listbox(win, bg=field, fg=fg,
                      highlightthickness=0, bd=0)
    lista.pack(fill="both", expand=True)
    for b in buscar_bolsistas():
        lista.insert(tk.END, b)

    def adicionar():
        nome = pedir_input(parent, "Adicionar", "Nome:")
        if nome:
            inserir_bolsista(nome)
            lista.insert(tk.END, nome)
            if on_success_callback:
                on_success_callback()
            

    def remover():
        sel = lista.curselection()
        if sel:
            nome = lista.get(sel)
            deletar_bolsista(nome)
            lista.delete(sel)
            if on_success_callback:
                on_success_callback()

    tk.Button(win, text="Adicionar", command=adicionar, bd=0, highlightthickness=0,
              bg=select_btn, fg=fg).pack()
    tk.Button(win, text="Remover",   command=remover, bd=0, highlightthickness=0,
              bg=select_btn, fg=fg).pack()


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
                },
            }
            atualizar_registro(rid, nova_data, nova_entrada, nova_saida, nova_maquina)
            if novo_nome != nome:
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





