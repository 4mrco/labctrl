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

from core.config import (
    BASE_DIR,
    CONFIG_FILE,
    DB_FILE,
    SCHEMA_VERSION,
    EXPORT_DIR,
    BOLSISTAS_INICIAIS,
    TEMAS,
    COL_NAMES
)

from core.database import (
    get_conn,
    init_db,
    buscar_aluno,
    inserir_aluno,
    buscar_todos_alunos,
    atualizar_aluno,
    deletar_aluno,
    inserir_registro,
    finalizar_registro,
    buscar_registro_ativo,
    buscar_registro_por_id,
    atualizar_registro,
    deletar_registro,
    restaurar_registro_db,
    buscar_registros_por_mes,
    buscar_registros_orfaos,
    contar_registros_hoje,
    contar_ativos,
    buscar_meses,
    buscar_export_mes,
    buscar_export_dia,
    buscar_export_ontem,
    buscar_export_semana,
    buscar_bolsistas,
    inserir_bolsista,
    deletar_bolsista,
)



from core.services import (
    load_config,
    save_config,
    get_export_dir,
    get_month_export_dir,
    agora,
    calcular_tempo,
    mes_anterior,
    PORTUGUESE_CONNECTORS,
    normalizar_nome,
    datas_semana_atual,
    gerar_id_servidor,
    calcular_estatisticas,
    processar_entrada,
    reverter_acao,
    remover_registro as servico_remover_registro,
)
from ui.dialogs import (
    mostrar_sobre, pedir_input, popup_sem_matricula,
    setup_dialog, focus_first_field, bind_enter_to_button,
    abrir_copiar_personalizado, visualizar_db, abrir_bolsistas,
    abrir_alunos, abrir_form_edicao, copiar_periodo
)
# ─────────────────────────────────────────────
# DIALOG UTILITIES
# ─────────────────────────────────────────────




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
        copiar_menu.add_command(label="Hoje",        command=lambda: copiar_periodo(self.root, "Hoje", self._mes_ativo()))
        copiar_menu.add_command(label="Ontem",       command=lambda: copiar_periodo(self.root, "Ontem", self._mes_ativo()))
        copiar_menu.add_command(label="Semana",      command=lambda: copiar_periodo(self.root, "Semana", self._mes_ativo()))
        copiar_menu.add_command(label="Mês",         command=lambda: copiar_periodo(self.root, "Mês", self._mes_ativo()))
        copiar_menu.add_command(label="Personalizado", command=lambda: abrir_copiar_personalizado(self.root, self._mes_ativo()))
        self.menu.add_cascade(label="Copiar Dados", menu=copiar_menu)
        self.menu.add_separator()
        
        self.menu.add_command(label="Visualizar DB", command=lambda: visualizar_db(self.root))
        self.menu.add_separator()
        
        def on_bolsistas_changed():
            self.combo_bolsista["values"] = __import__('core.database').database.buscar_bolsistas()
            self._focus_matricula()

        self.menu.add_command(label="Bolsistas",           command=lambda: abrir_bolsistas(self.root, on_bolsistas_changed))
        self.menu.add_command(label="Alunos / Servidores", command=lambda: abrir_alunos(self.root, lambda: (self._atualizar_lista(), self._focus_matricula())))
        self.menu.add_separator()
        self.menu.add_command(label="Sobre",               command=lambda: mostrar_sobre(self.root))

    def _abrir_menu(self):
        """Open the menu using the button's screen position."""
        self.menu.tk_popup(self.btn_menu.winfo_rootx(), self.btn_menu.winfo_rooty() + 20)



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



    def status(self, msg: str, erro: bool = False):
        if self._status_job:
            self.root.after_cancel(self._status_job)

        t = TEMAS["default"]
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

    def _abrir_form_edicao_wrapper(self, rid: int):
        def on_success(undo_payload, status_msg, erro=False):
            if undo_payload:
                self._push_undo(undo_payload)
            self.status(status_msg, erro=erro)
            if not erro:
                self._rebuild_abas()
                self._atualizar_lista()
        abrir_form_edicao(self.root, rid, on_success)

    def _on_double_click(self, event=None):
        item = self.tree.identify_row(event.y)
        if item:
            rid = int(self.tree.item(item)["tags"][0])
            self._abrir_form_edicao_wrapper(rid)

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

        try:
            msg = reverter_acao(acao)
            self.status(msg)
        except Exception as e:
            log.error("Falha no undo: %s", e)
            self.status("Erro ao desfazer.", erro=True)
            return

        self._rebuild_abas()
        self._atualizar_lista()
        self._focus_matricula()

    def _fluxo_entrada(self, matricula: str | None, nome: str) -> bool:
        """UI glue: chama o serviço de entrada e reage ao resultado."""
        try:
            resultado = processar_entrada(
                matricula, nome,
                self.combo_maquina.get(), self.combo_bolsista.get(),
            )
        except Exception as e:
            log.error("Falha ao registrar entrada: %s", e)
            self.status("Erro ao registrar entrada.", erro=True)
            return False

        if resultado["status"] == "ja_ativo":
            resp = messagebox.askyesno(
                "Já dentro",
                f"{nome} já tem entrada ativa.\nRegistrar saída agora?",
                parent=self.root
            )
            if resp:
                finalizar_registro(resultado["rid_ativo"], agora().strftime("%H:%M"))
                self._push_undo({"tipo": "saida", "rid": resultado["rid_ativo"], "nome": nome})
                self.status(f"Saída de {nome} registrada.")
                self._atualizar_lista()
            return False

        # status == "entrada_registrada"
        self._push_undo({"tipo": "entrada", "rid": resultado["rid"], "nome": nome})
        self.status(f"Entrada de {nome} registrada às {resultado['hora']}.")
        return True

    def registrar_entrada(self, event=None):
        matricula = self.entry_matricula.get().strip()
        # Handle placeholder text
        if matricula == "Matrícula" or matricula == "":
            matricula = ""

        if not matricula:
            res = popup_sem_matricula(self.root)
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
            nome = pedir_input(self.root, "Novo aluno", "Nome completo:")
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
        if not messagebox.askyesno("Confirmar", "Remover registro?", parent=self.root):
            return
        try:
            snapshot = servico_remover_registro(rid)
            self._push_undo(snapshot)
            self.status("Registro removido.")
            self._focus_matricula()
        except Exception as e:
            log.error("Falha ao remover: %s", e)
            self.status("Erro ao remover registro.", erro=True)
        self._rebuild_abas()
        self._atualizar_lista()

    def registrar_servidor(self):
        nome = pedir_input(self.root, "Servidor", "Nome completo:")
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
        t = TEMAS["default"]
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

    def _apply_tk_colors(self, widget, bg: str, fg: str, field: str, select: str):
        """Recursively apply bg/fg to all classic tk.* widgets under `widget`.

        Skips ttk widgets (they are handled by ttk.Style) and the
        entry_matricula (handled separately for placeholder logic).
        """
        for child in widget.winfo_children():
            cls = child.winfo_class()
            if cls in ("Frame",):
                child.configure(bg=bg)
            elif cls in ("Label",):
                child.configure(bg=bg, fg=fg)
            elif cls in ("Button",):
                child.configure(bg=field, fg=fg, activebackground=select,
                                activeforeground=fg,
                                disabledforeground="#888888",
                                relief="flat", bd=0, highlightthickness=0)
            elif cls in ("Entry",) and child is not self.entry_matricula:
                child.configure(bg=field, fg=fg, insertbackground=fg,
                                disabledbackground=field,
                                bd=0, highlightthickness=0)
            # Recurse into children
            if child.winfo_children():
                self._apply_tk_colors(child, bg, fg, field, select)

    def _aplicar_tema(self):
        t = TEMAS["default"]
        bg, fg, field, select, row_a, row_b, ativo_bg = (
            t["bg"], t["fg"], t["field"], t["select"], t["row_a"], t["row_b"], t["ativo_bg"]
        )

        # ── 1. Global option_add ─────────────────────────────────────────
        self.root.option_add("*Background",       bg,    "interactive")
        self.root.option_add("*Foreground",       fg,    "interactive")
        self.root.option_add("*Entry.Background", field, "interactive")
        self.root.option_add("*Entry.Foreground", fg,    "interactive")
        self.root.option_add("*Entry.insertBackground", fg, "interactive")
        self.root.option_add("*Button.Background",       field,  "interactive")
        self.root.option_add("*Button.Foreground",       fg,     "interactive")
        self.root.option_add("*Button.activeBackground", select, "interactive")
        self.root.option_add("*Button.activeForeground", fg,     "interactive")
        self.root.option_add("*Button.relief",           "flat", "interactive")
        self.root.option_add("*Button.bd",               0,      "interactive")
        self.root.option_add("*Button.highlightThickness", 0,    "interactive")
        self.root.option_add("*Menu.Background",         bg,     "interactive")
        self.root.option_add("*Menu.Foreground",         fg,     "interactive")
        self.root.option_add("*Menu.activeBackground",   select, "interactive")
        self.root.option_add("*Menu.activeForeground",   fg,     "interactive")
        # Combobox internal Listbox
        self.root.option_add("*TCombobox*Listbox.Background",      field,  "interactive")
        self.root.option_add("*TCombobox*Listbox.Foreground",      fg,     "interactive")
        self.root.option_add("*TCombobox*Listbox.SelectBackground", select, "interactive")
        self.root.option_add("*TCombobox*Listbox.SelectForeground", fg,     "interactive")

        # ── 2. ttk.Style ────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")

        style.configure("TFrame",  background=bg)
        style.configure("TLabel",  background=bg, foreground=fg)
        style.configure("TButton", background=field, foreground=fg,
                        borderwidth=0, highlightthickness=0)
        style.configure("TCombobox",
            fieldbackground=field, background=field, foreground=fg,
            borderwidth=0, highlightthickness=0)
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
            background=field, foreground=fg, borderwidth=0, highlightthickness=0)
        style.map("Treeview.Heading",
            background=[("active", field)])
        style.configure("Vertical.TScrollbar",
            background=field, troughcolor=bg, arrowcolor=fg,
            borderwidth=0, highlightthickness=0)
        style.map("Vertical.TScrollbar",
            background=[("active", select)],
            arrowcolor=[("active", select)])
        self.tree_scroll.configure(style="Vertical.TScrollbar")

        # ── 3. Recursive walk: main-window tk.* widgets ─────────────────
        # Applies colours to already-created widgets without naming each one.
        self.root.configure(bg=bg)
        self._apply_tk_colors(self.root, bg, fg, field, select)

        # ── 4. Widgets requiring conditional / special logic ─────────────

        # Separator uses `field`, not `bg`
        self.sep_header.configure(bg=field)

        # Filter buttons: active button gets select bg + sunken relief
        for nome, btn in self._btns_filtro.items():
            ativo = nome == self.var_filtro.get()
            btn.configure(
                bg=select if ativo else field, fg=fg,
                activebackground=select,
                relief="sunken" if ativo else "raised",
                bd=0, highlightthickness=0,
            )

        # Month selector buttons always look like inactive filter buttons
        self._month_btn.configure(
            bg=field, fg=fg, activebackground=select,
            relief="raised", bd=0, highlightthickness=0,
        )
        self._month_dropdown_btn.configure(
            bg=field, fg=fg, activebackground=select,
            relief="raised", bd=0, highlightthickness=0,
        )

        # Month drop-down menu
        self._month_menu.config(
            bg=field, fg=fg,
            activebackground=select, activeforeground=fg,
            tearoff=0,
        )

        # Entry placeholder: grey when showing placeholder text, normal fg otherwise
        if not self.entry_matricula.get() or self.entry_matricula.get() == "Matrícula":
            self.entry_matricula.configure(bg=field, fg="#B5BAC1",
                                           insertbackground=fg,
                                           disabledbackground=field,
                                           bd=0, highlightthickness=0)
        else:
            self.entry_matricula.configure(bg=field, fg=fg,
                                           insertbackground=fg,
                                           disabledbackground=field,
                                           bd=0, highlightthickness=0)

        # Application menu and its sub-menus
        self.menu.configure(background=bg, foreground=fg,
                            activebackground=select, activeforeground=fg,
                            bd=0, relief="flat")
        for item in self.menu.winfo_children():
            if isinstance(item, tk.Menu):
                item.configure(background=bg, foreground=fg,
                               activebackground=select, activeforeground=fg,
                               bd=0, relief="flat")

        # Treeview row tags (Treeview-specific API, not covered by Style)
        self.tree.tag_configure("0",          background=row_a)
        self.tree.tag_configure("1",          background=row_b)
        self.tree.tag_configure("ATIVO",      background=ativo_bg)
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

        t = TEMAS["default"]
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

    def _editar_registro(self):
        tree = self.tree
        sel  = tree.selection()
        if not sel:
            messagebox.showinfo("Editar", "Selecione um registro primeiro.", parent=self.root)
            return
        rid = int(tree.item(sel[0])["tags"][0])
        self._abrir_form_edicao_wrapper(rid)

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    App(root)
    root.mainloop()
