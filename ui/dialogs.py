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
