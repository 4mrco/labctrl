import json
import os
import shutil
import glob
import subprocess
from collections import defaultdict
from datetime import date, datetime, timedelta

from core.config import CONFIG_FILE, EXPORT_DIR, DB_FILE, BASE_DIR


# ─────────────────────────────────────────────
# Importações de database ficam aqui para evitar
# importação circular (database ← config, services ← database)
# ─────────────────────────────────────────────
def _get_db():
    from core import database as db
    return db


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {
            "exported_months": [], "ultimo_bolsista": None, 
            "open_export_folder": True, "escolher_maquina_entrada": False,
            "ultimo_backup": "", "versao_registrada": "", "popup_expira_em": "",
            "layout": "lab_informatica"
        }
    cfg = json.load(open(CONFIG_FILE, "r"))
    cfg.setdefault("exported_months", [])
    cfg.setdefault("ultimo_bolsista", None)
    cfg.setdefault("modo_ui", "dashboard")
    cfg.setdefault("kiosk_fullscreen", False)
    cfg.setdefault("layout", "lab_informatica")
    cfg.setdefault("open_export_folder", True)
    cfg.setdefault("escolher_maquina_entrada", False)
    cfg.setdefault("ultimo_backup", "")
    cfg.setdefault("versao_registrada", "")
    cfg.setdefault("popup_expira_em", "")
    cfg.setdefault("confirmar_saida", True)
    if "backups_diarios" not in cfg:
        legacy = cfg.get("ultimo_backup", "")
        cfg["backups_diarios"] = {"12": legacy, "17": legacy} if legacy else {}
    return cfg


def save_config(cfg: dict) -> None:
    json.dump(cfg, open(CONFIG_FILE, "w"))


def load_layout(name: str = "lab_informatica") -> dict:
    """Carrega e valida os dados de planta física de um laboratório a partir de layouts/<name>.json."""
    layout_path = os.path.join(BASE_DIR, "layouts", f"{name}.json")
    if not os.path.isfile(layout_path):
        raise FileNotFoundError(f"Arquivo de layout não encontrado: {layout_path}")
    with open(layout_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    required_keys = {"width", "height", "table_size", "tables", "desk_poly", "bolsista_pos", "pcs", "ml_slots"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Layout '{name}' malformado. Chaves ausentes: {', '.join(sorted(missing))}")
    return data


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
    visitas_por_dia:    dict[str, int] = defaultdict(int)

    for data, entrada, saida, nome, matricula, maquina, _ in dados:
        chave = f"{nome} ({matricula})"
        visitas_por_pessoa[chave] += 1
        
        if data:
            visitas_por_dia[data] += 1

        if maquina and maquina not in ("-", ""):
            maq_exib = "ML" if str(maquina).startswith("ML-") else maquina
            # We track all machines, but we will exclude ML/ML-X from the top 3 later
            uso_maquinas[maq_exib] += 1
            
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

    total_minutos = sum(minutos_por_pessoa.values())
    tempo_total_formatado = f"{total_minutos // 60}h{total_minutos % 60:02}m"

    # Top 3 machines (excluding ML and ML-X)
    maquinas_validas = {k: v for k, v in uso_maquinas.items() if not k.startswith("ML")}
    top3 = sorted(maquinas_validas.items(), key=lambda x: -x[1])[:3]
    top3_maquinas = ", ".join(f"{k} ({v})" for k, v in top3) if top3 else "-"

    return {
        "total_visitas":      sum(visitas_por_pessoa.values()),
        "total_pessoas":      len(visitas_por_pessoa),
        "tempo_total":        tempo_total_formatado,
        "dia_pico":           max(visitas_por_dia, key=visitas_por_dia.get) if visitas_por_dia else "-",
        "top3_maquinas":      top3_maquinas,
        "visitas_por_pessoa": sorted(visitas_por_pessoa.items(), key=lambda x: -x[1]),
        "horas_por_pessoa": {
            k: f"{v // 60}h{v % 60:02}m"
            for k, v in sorted(minutos_por_pessoa.items(), key=lambda x: -x[1])
        },
        "horario_pico": (
            f"{max(horas_entrada, key=horas_entrada.get):02}:00"
            if horas_entrada else "-"
        ),
    }


# ─────────────────────────────────────────────
# SERVIÇO: BACKUP & SISTEMA
# ─────────────────────────────────────────────

def executar_backup_diario(db_path=None, max_backups=5) -> str:
    """Creates a timestamped backup directory and keeps only max_backups."""
    if db_path is None:
        db_path = DB_FILE
        
    backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    now = agora()
    today_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d_%H%M")
    
    # Create specific backup folder
    specific_backup_dir = os.path.join(backup_dir, timestamp_str)
    os.makedirs(specific_backup_dir, exist_ok=True)
    
    if os.path.exists(db_path):
        shutil.copy2(db_path, os.path.join(specific_backup_dir, "lab.db"))
        
    # Rotate backups (directories only)
    all_dirs = [os.path.join(backup_dir, d) for d in os.listdir(backup_dir)]
    backups = sorted([d for d in all_dirs if os.path.isdir(d)], key=os.path.getmtime)
    
    while len(backups) > max_backups:
        shutil.rmtree(backups.pop(0))
        
    # Update config
    cfg = load_config()
    cfg["ultimo_backup"] = today_str
    save_config(cfg)
    
    return f"Backup realizado com sucesso: {timestamp_str}"

def abrir_diretorio_so(caminho_relativo: str):
    """Opens a directory in the host OS file explorer."""
    abs_path = os.path.join(BASE_DIR, caminho_relativo)
    os.makedirs(abs_path, exist_ok=True)
    try:
        if os.name == 'nt':
            os.startfile(abs_path)
        else:
            subprocess.Popen(['xdg-open', abs_path])
    except Exception as e:
        print(f"Erro ao abrir {caminho_relativo}: {e}")


# ─────────────────────────────────────────────
# SERVIÇO: FLUXO DE ENTRADA
# ─────────────────────────────────────────────

def processar_entrada(matricula: str | None, nome: str, maquina: str, bolsista: str) -> dict:
    """Executa o fluxo de negócio da entrada no laboratório.

    Retorna um dict com 'status' indicando o resultado:
      - {"status": "ja_ativo",           "rid_ativo": int, "nome": str}
      - {"status": "entrada_registrada", "rid": int, "nome": str, "hora": str}

    Não acessa self, não abre janelas Tkinter, não toca na pilha de undo.
    Lança exceção em caso de falha de banco de dados.
    """
    db = _get_db()

    # Se tem matrícula, verifica se já há uma sessão ativa
    if matricula:
        rid_ativo = db.buscar_registro_ativo(matricula)
        if rid_ativo:
            return {"status": "ja_ativo", "rid_ativo": rid_ativo, "nome": nome}

    now = agora()
    db.inserir_registro(
        matricula, nome,
        now.strftime("%d/%m/%Y"), now.strftime("%H:%M"),
        maquina, bolsista,
    )

    # Descobre o id do registro recém-inserido
    db_conn = db.get_conn
    with db_conn() as conn:
        rid = conn.execute(
            "SELECT id FROM registros WHERE matricula IS ? AND nome=? ORDER BY id DESC LIMIT 1",
            (matricula, nome),
        ).fetchone()[0]

    return {"status": "entrada_registrada", "rid": rid, "nome": nome, "hora": now.strftime("%H:%M")}


# ─────────────────────────────────────────────
# SERVIÇO: DESFAZER (UNDO)
# ─────────────────────────────────────────────

def reverter_acao(acao: dict) -> str:
    """Reverte uma ação na base de dados com base no dict da pilha de undo.

    Retorna a mensagem de status a ser exibida pela UI.
    Lança exceção em caso de falha de banco de dados.
    Não acessa self, não toca em Tkinter.
    """
    db = _get_db()
    tipo = acao["tipo"]

    if tipo == "entrada":
        # desfaz: deleta o registro inserido
        db.deletar_registro(acao["rid"])
        return f"Entrada de {acao['nome']} desfeita."

    elif tipo == "saida":
        # desfaz: volta status ATIVO, apaga saída
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE registros SET saida=NULL, status='ATIVO' WHERE id=?",
                (acao["rid"],),
            )
        return f"Saída de {acao['nome']} desfeita."

    elif tipo == "remocao":
        # desfaz: recria o registro deletado
        db.restaurar_registro_db(acao["campos"])
        return f"Remoção de {acao['nome']} desfeita."

    elif tipo == "edicao":
        # desfaz: restaura valores anteriores
        c = acao["antes"]
        db.atualizar_registro(c["id"], c["nome"], c["data"], c["entrada"],
                              c["saida"] or "", c["maquina"] or "")
        if c.get("matricula"):
            db.atualizar_aluno(c["matricula"], c["nome"])
        return f"Edição de {acao['nome']} desfeita."

    raise ValueError(f"Tipo de undo desconhecido: {tipo!r}")


# ─────────────────────────────────────────────
# SERVIÇO: REMOÇÃO DE REGISTRO
# ─────────────────────────────────────────────

def remover_registro(rid: int) -> dict:
    """Busca o registro, apaga-o e retorna o snapshot para a pilha de undo.

    Retorna dict pronto para ser passado ao _push_undo() da UI:
      {"tipo": "remocao", "nome": str, "campos": {...}}

    Lança exceção em caso de falha de banco de dados.
    Não acessa self, não abre janelas Tkinter.
    """
    db = _get_db()
    reg = db.buscar_registro_por_id(rid)
    if not reg:
        raise ValueError(f"Registro {rid} não encontrado.")

    snapshot = {
        "tipo":  "remocao",
        "nome":  reg[1],
        "campos": {
            "id": reg[0], "nome": reg[1], "matricula": reg[2],
            "data": reg[3], "entrada": reg[4], "saida": reg[5],
            "maquina": reg[6], "bolsista": reg[7], "status": reg[8],
        },
    }
    db.deletar_registro(rid)
    return snapshot


# ─────────────────────────────────────────────
# SERVIÇO: BOOT OPERATIONS
# ─────────────────────────────────────────────

def run_boot_operations(config: dict) -> dict:
    """
    Executa as verificações de inicialização:
    - Backups pendentes
    - Órfãos auto-encerrados
    - Exportação do mês anterior
    - Verificação de relógio (comparação com último registro)
    
    Retorna um dicionário de resultados. A UI decide como exibir.
    """
    db = _get_db()
    now = agora()
    today_str = now.strftime("%Y-%m-%d")
    results = {
        "backups": [],
        "orfaos": [],
        "export": None,
        "relogio": None
    }
    
    # 1. Backups
    slots = config.get("backups_diarios", {})
    for slot_hour, slot_key in [(12, "12"), (17, "17")]:
        if now.hour >= slot_hour and slots.get(slot_key) != today_str:
            executar_backup_diario()
            slots[slot_key] = today_str
            results["backups"].append(slot_key)
    config["backups_diarios"] = slots
    
    # 2. Órfãos
    orfaos = db.buscar_registros_orfaos()
    for r in orfaos:
        rid, nome = r[0], r[1]
        db.finalizar_registro(rid, None)
        results["orfaos"].append({"tipo": "saida", "rid": rid, "nome": nome})
        
    # 3. Export Pendente
    from core.services import mes_anterior
    mes_ant = mes_anterior()
    if mes_ant not in config.get("exported_months", []):
        dados = db.buscar_registros_por_mes(mes_ant)
        if dados:
            # We don't write the CSV here to avoid UI duplication, or we write it here?
            # The spec says it runs silently. Let's do the CSV logic here if it's not strictly UI.
            # But the UI handles CSV writing in `_fazer_export` with stats. 
            # We can return `mes_ant` and the dashboard writes it, or the kiosk does it.
            # Wait, the kiosk needs to do it silently.
            results["export"] = {"mes": mes_ant, "dados": dados}
            
    # 4. Relógio
    reg = db.buscar_ultimo_registro()
    if reg:
        data_ant, entrada_ant = reg
        try:
            dt_ant = datetime.strptime(f"{data_ant} {entrada_ant}", "%d/%m/%Y %H:%M")
            dt_novo = now.replace(second=0, microsecond=0)
            if dt_novo < dt_ant - timedelta(minutes=5):
                results["relogio"] = {"dt_ant": dt_ant, "dt_novo": dt_novo}
        except Exception:
            pass
            
    return results

def finalizar_export_silencioso(mes: str, dados: list, config: dict):
    from core.services import get_month_export_dir, calcular_estatisticas, agora
    import csv, os
    
    stats = calcular_estatisticas(dados)
    label = mes.replace("/", "_")
    titulo = f"Mês {mes}"
    nome_arquivo = f"lab_{label}.csv"
    
    if dados:
        primeira_data = dados[0][0]
        mes_pasta = primeira_data.split("/")[2] + "-" + primeira_data.split("/")[1]
    else:
        mes_pasta = agora().strftime("%Y-%m")
        
    month_dir = get_month_export_dir(mes_pasta)
    caminho = os.path.join(month_dir, nome_arquivo)
    
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"Relatório do Laboratório — {titulo}"])
        w.writerow([
            f"Total de visitas: {stats.get('total_visitas', 0)}",
            f"Pessoas distintas: {stats.get('total_pessoas', 0)}",
            f"Tempo total: {stats.get('tempo_total', '-')}",
            f"Horário de pico: {stats.get('horario_pico', '-')}",
            f"Dia mais movim.: {stats.get('dia_pico', '-')}",
            f"Top 3 máquinas: {stats.get('top3_maquinas', '-')}",
        ])
        w.writerow([])
        w.writerow(["Resumo por pessoa (blocos de 10)"])
        
        chunk = stats.get("visitas_por_pessoa", [])
        cols = [chunk[i:i+10] for i in range(0, len(chunk), 10)]
        header = []
        for c in cols:
            if c:
                header.extend(["Nome (Matrícula)", "Visitas", "Tempo total", ""])
        w.writerow(header)
        
        for row_idx in range(10):
            row_data = []
            for c in cols:
                if c:
                    if row_idx < len(c):
                        pessoa, visitas = c[row_idx]
                        tempo = stats.get("horas_por_pessoa", {}).get(pessoa, "-")
                        row_data.extend([pessoa, visitas, tempo, ""])
                    else:
                        row_data.extend(["", "", "", ""])
            if any(row_data):
                w.writerow(row_data)
                
    if mes not in config["exported_months"]:
        config["exported_months"].append(mes)
        
