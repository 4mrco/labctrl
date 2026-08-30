import re
import sys

def main():
    with open('app.py', 'r') as f:
        content = f.read()

    # The functions to extract
    func_names = [
        '_abrir_copiar_personalizado',
        '_visualizar_db',
        '_abrir_bolsistas',
        '_abrir_alunos',
        '_abrir_form_edicao',
        '_gerar_csv'
    ]

    extracted_funcs = {}
    for func in func_names:
        # Find the start of the function
        match = re.search(r'^    def ' + func + r'\(self.*?\):.*?(?=^    def |^# ──)', content, re.MULTILINE | re.DOTALL)
        if match:
            func_code = match.group(0)
            # Remove from app.py
            content = content.replace(func_code, '')
            # Dedent one level
            func_code = '\n'.join([line[4:] if line.startswith('    ') else line for line in func_code.split('\n')])
            extracted_funcs[func] = func_code

    # Write back app.py
    with open('app.py', 'w') as f:
        f.write(content)

    # Now we process the extracted functions for dialogs.py
    # 1. _gerar_csv -> gerar_csv
    gerar_csv = extracted_funcs['_gerar_csv'].replace('def _gerar_csv(self, ', 'def gerar_csv(')
    
    # 2. _abrir_copiar_personalizado -> abrir_copiar_personalizado
    cp = extracted_funcs['_abrir_copiar_personalizado']
    cp = cp.replace('def _abrir_copiar_personalizado(self):', 'def abrir_copiar_personalizado(parent, mes_ativo: str):')
    cp = cp.replace('self.root', 'parent')
    cp = cp.replace('self._mes_ativo()', 'mes_ativo')
    cp = cp.replace('self._gerar_csv', 'gerar_csv')
    cp = cp.replace('parent.clipboard_clear()', 'parent.clipboard_clear()') # just checking
    
    # 3. _visualizar_db -> visualizar_db
    vdb = extracted_funcs['_visualizar_db']
    vdb = vdb.replace('def _visualizar_db(self):', 'def visualizar_db(parent):')
    vdb = vdb.replace('self.root', 'parent')

    # 4. _abrir_bolsistas -> abrir_bolsistas
    ab = extracted_funcs['_abrir_bolsistas']
    ab = ab.replace('def _abrir_bolsistas(self):', 'def abrir_bolsistas(parent, on_success_callback=None):')
    ab = ab.replace('self.root', 'parent')
    ab = ab.replace('self.combo_bolsista["values"] = buscar_bolsistas()', '')
    ab = ab.replace('self._focus_matricula()', 'if on_success_callback:\n                    on_success_callback()')
    # Since we removed two lines, we need to ensure the callback is called for adicionar as well.
    # In adicionar, the original code had:
    # inserir_bolsista(nome)
    # lista.insert(tk.END, nome)
    # self.combo_bolsista["values"] = buscar_bolsistas()
    ab = re.sub(r'lista\.insert\(tk\.END, nome\).*?(?=\n\s+def remover)', 'lista.insert(tk.END, nome)\n                if on_success_callback:\n                    on_success_callback()', ab, flags=re.DOTALL)
    
    # For remover:
    # deletar_bolsista(nome)
    # lista.delete(sel)
    # self.combo_bolsista["values"] = buscar_bolsistas()
    # self._focus_matricula()
    ab = re.sub(r'lista\.delete\(sel\).*?(?=\n\s+tk\.Button)', 'lista.delete(sel)\n                if on_success_callback:\n                    on_success_callback()', ab, flags=re.DOTALL)


    # 5. _abrir_alunos -> abrir_alunos
    al = extracted_funcs['_abrir_alunos']
    al = al.replace('def _abrir_alunos(self):', 'def abrir_alunos(parent, on_success_callback=None):')
    al = al.replace('self.root', 'parent')
    al = al.replace('self._atualizar_lista()', 'if on_success_callback: on_success_callback()')
    al = al.replace('self._focus_matricula()', 'if on_success_callback: on_success_callback()')

    # 6. _abrir_form_edicao -> abrir_form_edicao
    afe = extracted_funcs['_abrir_form_edicao']
    afe = afe.replace('def _abrir_form_edicao(self, rid: int):', 'def abrir_form_edicao(parent, rid: int, on_success_callback=None):')
    afe = afe.replace('self.root', 'parent')
    afe = afe.replace('self._atualizar_lista()', 'if on_success_callback: on_success_callback()')

    with open('ui/dialogs.py', 'a') as f:
        f.write('\n\nfrom tkinter import ttk, messagebox\n')
        f.write('from core.database import (\n')
        f.write('    buscar_registro_por_id, atualizar_registro, buscar_meses,\n')
        f.write('    buscar_registros_por_mes, buscar_bolsistas, inserir_bolsista,\n')
        f.write('    deletar_bolsista, buscar_todos_alunos, atualizar_aluno, deletar_aluno,\n')
        f.write('    get_conn, buscar_export_mes\n')
        f.write(')\n')
        f.write('from core.services import agora, datas_semana_atual\n\n')
        f.write(gerar_csv + '\n')
        f.write(cp + '\n')
        f.write(vdb + '\n')
        f.write(ab + '\n')
        f.write(al + '\n')
        f.write(afe + '\n')

if __name__ == '__main__':
    main()
