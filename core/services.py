import sqlite3
import copy
import json
import os
import re
import shutil
import glob
import subprocess
import csv
import logging
import threading
import urllib.request
import urllib.error
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

from core.config import CONFIG_FILE, EXPORT_DIR, DB_FILE, BASE_DIR, VERSAO_ATUAL

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Importações de database ficam aqui para evitar
# importação circular (database ← config, services ← database)
# ─────────────────────────────────────────────
def _get_db():
    from core import database as db
    return db


DEFAULT_CONFIG = {
    "exported_months": [],
    "ultimo_bolsista": None,
    "turno_inicio_iso": "",
    "modo_ui": "dashboard",
    "kiosk_fullscreen": False,
    "kiosk_enter_confirm": True,
    "layout": "lab_informatica",
    "open_export_folder": True,
    "escolher_maquina_entrada": False,
    "ultimo_backup": "",
    "versao_registrada": "",
    "popup_expira_em": "",
    "confirmar_saida": True,
    "backups_diarios": {},
    "orfaos_sem_saida": [],
    "maquinas_defeito": {},
    "repo_updater_owner": "4mrco",
    "repo_updater_name": "labctrl",
    "ota_postergado_em": "",
}


def save_config(cfg: dict) -> None:
    tmp_file = f"{CONFIG_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, CONFIG_FILE)


def load_config() -> dict:
    default = copy.deepcopy(DEFAULT_CONFIG)
    if not os.path.exists(CONFIG_FILE) or os.path.getsize(CONFIG_FILE) == 0:
        save_config(default)
        return default

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError("Config root is not a dictionary")
    except Exception:
        save_config(default)
        return default

    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = copy.deepcopy(v)

    if "backups_diarios" not in cfg or not isinstance(cfg["backups_diarios"], dict):
        legacy = cfg.get("ultimo_backup", "")
        cfg["backups_diarios"] = {"12": legacy, "17": legacy} if legacy else {}

    if not isinstance(cfg.get("maquinas_defeito"), dict):
        cfg["maquinas_defeito"] = {}

    return cfg


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


def validar_entrada_nome(proposed: str, max_len: int = 60) -> bool:
    if len(proposed) > max_len:
        return False
    if any(ch.isdigit() for ch in proposed):
        return False
    return True


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


def formatar_dois_nomes(nome_completo: str) -> str:
    """Retorna apenas os 2 primeiros nomes do bolsista, ignorando conectores."""
    if not nome_completo:
        return ""
    palavras = [p for p in nome_completo.strip().split() if p.lower() not in PORTUGUESE_CONNECTORS]
    if not palavras:
        palavras = nome_completo.strip().split()
    return " ".join(palavras[:2])


def normalizar_hora_turno(dt: datetime | None = None) -> str:
    """Zera minutos, segundos e microssegundos da hora base do turno."""
    if dt is None:
        dt = agora()
    return dt.replace(minute=0, second=0, microsecond=0).isoformat()


def iniciar_turno_bolsista(nome: str, config: dict) -> None:
    """Define o bolsista ativo e grava a hora cheia normalizada do início do turno."""
    config["ultimo_bolsista"] = nome
    config["turno_inicio_iso"] = normalizar_hora_turno()
    save_config(config)


def verificar_alerta_turno(config: dict, duracao_horas: int = 2) -> bool:
    """Retorna True se o turno atual atingiu/ultrapassou duracao_horas ou está ausente/vencido."""
    iso_str = config.get("turno_inicio_iso")
    if not iso_str or not isinstance(iso_str, str):
        return True
    try:
        dt_inicio = datetime.fromisoformat(iso_str)
    except Exception:
        return True
    now = agora()
    if dt_inicio.date() < now.date():
        return True
    return (now - dt_inicio) >= timedelta(hours=duracao_horas)


def registrar_defeito_maquina(config: dict, maquina: str, motivo: str) -> None:
    """Registra defeito ativo para uma máquina em config['maquinas_defeito']."""
    defeitos = config.setdefault("maquinas_defeito", {})
    if not isinstance(defeitos, dict):
        defeitos = {}
        config["maquinas_defeito"] = defeitos
    defeitos[str(maquina)] = str(motivo)
    save_config(config)


def resolver_defeito_maquina(config: dict, maquina: str) -> None:
    """Remove o defeito registrado de uma máquina em config['maquinas_defeito']."""
    defeitos = config.get("maquinas_defeito")
    if isinstance(defeitos, dict) and str(maquina) in defeitos:
        defeitos.pop(str(maquina), None)
        save_config(config)


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

DEFAULT_BACKUP_SLOTS = [(12, "12"), (17, "17")]

def executar_backup_diario(db_path=None, max_backups=5) -> str:
    """Creates a timestamped backup directory using SQLite online backup and keeps only max_backups."""
    if db_path is None:
        db_path = DB_FILE
        
    backup_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    now = agora()
    today_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d_%H%M")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco de dados não encontrado para backup: {db_path}")

    # Create specific backup folder
    specific_backup_dir = os.path.join(backup_dir, timestamp_str)
    os.makedirs(specific_backup_dir, exist_ok=True)
    
    dest_db = os.path.join(specific_backup_dir, "lab.db")
    tmp_dest_db = os.path.join(specific_backup_dir, "lab.db.tmp")
    
    src_conn = None
    dst_conn = None
    try:
        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(tmp_dest_db)
        src_conn.backup(dst_conn)
        dst_conn.close()
        dst_conn = None
        src_conn.close()
        src_conn = None
        
        os.replace(tmp_dest_db, dest_db)
    except Exception as e:
        log.error("Falha ao criar backup do banco de dados: %s", e)
        if dst_conn:
            try:
                dst_conn.close()
            except Exception:
                pass
        if src_conn:
            try:
                src_conn.close()
            except Exception:
                pass
        if os.path.exists(tmp_dest_db):
            try:
                os.remove(tmp_dest_db)
            except OSError:
                pass
        try:
            os.rmdir(specific_backup_dir)
        except OSError:
            pass
        raise
        
    # Rotate backups (directories only - retention behavior preserved as deferred)
    all_dirs = [os.path.join(backup_dir, d) for d in os.listdir(backup_dir)]
    backups = sorted([d for d in all_dirs if os.path.isdir(d)], key=os.path.getmtime)
    
    while len(backups) > max_backups:
        shutil.rmtree(backups.pop(0))
        
    # Update config
    cfg = load_config()
    cfg["ultimo_backup"] = today_str
    save_config(cfg)
    
    return f"Backup realizado com sucesso: {timestamp_str}"

def verificar_e_executar_backups(config: dict) -> list[str]:
    """Checks scheduled daily backup slots (12h, 17h) and executes due backups.
    
    Returns a list of successfully executed slot keys (e.g. ['12'], ['17'], or []).
    Ensures each slot is executed at most once per day and handles save failures safely.
    """
    now = agora()
    today_str = now.strftime("%Y-%m-%d")
    slots = config.get("backups_diarios", {})
    if not isinstance(slots, dict):
        slots = {}

    executados = []
    for slot_hour, slot_key in DEFAULT_BACKUP_SLOTS:
        if now.hour >= slot_hour and slots.get(slot_key) != today_str:
            try:
                executar_backup_diario()
                slots[slot_key] = today_str
                executados.append(slot_key)
            except Exception as e:
                log.error("Falha ao executar backup automático do slot %sh: %s", slot_key, e)

    if executados:
        try:
            fresh_cfg = load_config()
        except Exception:
            fresh_cfg = dict(config)
        fresh_slots = fresh_cfg.setdefault("backups_diarios", {})
        fresh_slots.update(slots)
        fresh_cfg["ultimo_backup"] = today_str
        config.update(fresh_cfg)
        try:
            save_config(fresh_cfg)
        except Exception as e:
            log.error("Falha ao salvar configuração após backups automáticos: %s", e)
            for s in executados:
                slots.pop(s, None)
                fresh_slots.pop(s, None)
            config["backups_diarios"] = slots
            return []

    return executados

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
    rid = db.inserir_registro(
        matricula, nome,
        now.strftime("%d/%m/%Y"), now.strftime("%H:%M"),
        maquina, bolsista,
    )

    return {"status": "entrada_registrada", "rid": rid, "nome": nome, "hora": now.strftime("%H:%M")}


def processar_entrada_com_despejo(
    matricula: str | None,
    nome: str,
    machine: str,
    bolsista: str,
    ocupantes_atuais: list[tuple[str, str, int]],
    config: dict,
) -> dict:
    """Finaliza sessões abandonadas dos ocupantes anteriores da máquina,
    adiciona suas matrículas em config['orfaos_sem_saida'], registra a nova
    entrada do aluno atual e retorna payload compatível com reverter_acao.
    """
    db = _get_db()
    if matricula:
        rid_ativo = db.buscar_registro_ativo(matricula)
        if rid_ativo:
            return {"status": "ja_ativo", "rid_ativo": rid_ativo, "nome": nome}

    hora_atual = agora().strftime("%H:%M")
    orfaos_sem_saida = config.setdefault("orfaos_sem_saida", [])
    if not isinstance(orfaos_sem_saida, list):
        orfaos_sem_saida = []
        config["orfaos_sem_saida"] = orfaos_sem_saida

    encerrados: list[int] = []
    orfaos_adicionados: list[str] = []

    for _nome_ant, mat_ant, rid_ant in ocupantes_atuais:
        db.finalizar_registro(rid_ant, hora_atual)
        encerrados.append(rid_ant)
        if mat_ant and mat_ant not in orfaos_sem_saida:
            orfaos_sem_saida.append(mat_ant)
            orfaos_adicionados.append(mat_ant)

    save_config(config)
    res_ent = processar_entrada(matricula, nome, machine, bolsista)
    novo_rid = res_ent["rid"]
    return {
        "status": "entrada_registrada",
        "tipo": "despejo_entrada",
        "rid": novo_rid,
        "nome": nome,
        "hora": res_ent["hora"],
        "encerrados": encerrados,
        "orfaos_adicionados": orfaos_adicionados,
    }


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
        db.reabrir_registro(acao["rid"])
        return f"Saída de {acao['nome']} desfeita."

    elif tipo == "despejo_entrada":
        db.deletar_registro(acao["rid"])
        for rid_ant in acao.get("encerrados", []):
            db.reabrir_registro(rid_ant)
        orfaos_add = acao.get("orfaos_adicionados", [])
        if orfaos_add:
            cfg = load_config()
            orfaos_atuais = cfg.get("orfaos_sem_saida", [])
            if isinstance(orfaos_atuais, list):
                cfg["orfaos_sem_saida"] = [m for m in orfaos_atuais if m not in orfaos_add]
                save_config(cfg)
            if isinstance(acao.get("config"), dict):
                acao["config"]["orfaos_sem_saida"] = list(cfg.get("orfaos_sem_saida", []))
        return f"Entrada de {acao['nome']} desfeita e sessão anterior restaurada."

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
    results["backups"] = verificar_e_executar_backups(config)
    
    # 2. Órfãos
    orfaos = db.buscar_registros_orfaos()
    orfaos_sem_saida = config.setdefault("orfaos_sem_saida", [])
    for r in orfaos:
        rid, nome = r[0], r[1]
        matricula = r[2] if len(r) > 2 else ""
        db.finalizar_registro(rid, None)
        results["orfaos"].append({"tipo": "saida", "rid": rid, "nome": nome, "matricula": matricula})
        if matricula and matricula not in orfaos_sem_saida:
            orfaos_sem_saida.append(matricula)
    if orfaos:
        config["orfaos_sem_saida"] = orfaos_sem_saida
        save_config(config)
        
    # 3. Export Pendente
    from core.services import mes_anterior
    mes_ant = mes_anterior()
    if mes_ant not in config.get("exported_months", []):
        dados = db.buscar_export_mes(mes_ant)
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

def normalizar_matricula_export(m: str | None) -> str:
    """Normaliza matrícula para exportação de forma consistente e idempotente.

    None / vazio -> ''
    'SERVIDOR' / 'Servidor' -> 'Servidor'
    qualquer outra string -> preserva (ex: '123456', 'SRV-slug')
    """
    if not m:
        return ""
    m_str = str(m).strip()
    if m_str.upper() == "SERVIDOR":
        return "Servidor"
    return m_str


def gerar_relatorio_csv(dados: list[tuple], label: str, titulo: str) -> str:
    """Gera o arquivo CSV canônico de relatório do laboratório.

    Contém:
      1. Cabeçalho com métricas gerais do laboratório
      2. Resumo individual por pessoa em blocos de 10 (paginados em grupos de até 50)
      3. Seção 'Registros detalhados' com todas as linhas brutas de atendimento

    Retorna o caminho do arquivo gerado.
    Garante escrita atômica via arquivo .tmp e limpeza em caso de falha.
    """
    dados_norm = [
        (
            data,
            entrada,
            saida,
            nome,
            normalizar_matricula_export(mat),
            "ML" if str(maquina).startswith("ML-") else maquina,
            bolsista,
        )
        for data, entrada, saida, nome, mat, maquina, bolsista in dados
    ]

    stats = calcular_estatisticas(dados_norm)
    nome_arquivo = f"lab_{label}.csv"

    if dados:
        primeira_data = str(dados[0][0])
        partes = primeira_data.split("/")
        if len(partes) >= 3:
            mes_pasta = f"{partes[2]}-{partes[1]}"
        else:
            mes_pasta = agora().strftime("%Y-%m")
    else:
        mes_pasta = agora().strftime("%Y-%m")

    month_dir = get_month_export_dir(mes_pasta)
    caminho = os.path.join(month_dir, nome_arquivo)
    caminho_tmp = f"{caminho}.tmp"

    try:
        with open(caminho_tmp, "w", newline="", encoding="utf-8") as f:
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

            def _write_blocks(writer, chunk_of_50):
                cols = [chunk_of_50[i:i + 10] for i in range(0, len(chunk_of_50), 10)]
                header = []
                for c in cols:
                    if c:
                        header.extend(["Nome (Matrícula)", "Visitas", "Tempo total", ""])
                writer.writerow(header)

                for row_idx in range(10):
                    row_data = []
                    has_data = False
                    for c in cols:
                        if c:
                            if row_idx < len(c):
                                pessoa, visitas = c[row_idx]
                                tempo = stats.get("horas_por_pessoa", {}).get(pessoa, "-")
                                row_data.extend([pessoa, visitas, tempo, ""])
                                has_data = True
                            else:
                                row_data.extend(["", "", "", ""])
                    if has_data:
                        writer.writerow(row_data)
                writer.writerow([])

            pessoas = stats.get("visitas_por_pessoa", [])
            for i in range(0, len(pessoas), 50):
                _write_blocks(w, pessoas[i:i + 50])

            if not pessoas:
                w.writerow([])

            w.writerow(["Registros detalhados"])
            w.writerow([
                "Data", "Entrada", "Saída", "Nome",
                "Matrícula", "Máquina(Nº)", "Bolsista presente"
            ])
            w.writerows(dados_norm)
            f.flush()
            os.fsync(f.fileno())

        os.replace(caminho_tmp, caminho)
    except Exception:
        if os.path.exists(caminho_tmp):
            try:
                os.remove(caminho_tmp)
            except OSError:
                pass
        raise

    return caminho


def finalizar_export_silencioso(mes: str, dados: list, config: dict) -> str | None:
    """Gera o CSV do mês anterior de forma silenciosa e atualiza config['exported_months'].

    Retorna o nome do arquivo gerado (ex: 'lab_10_2026.csv') se sucesso, ou None se falha.
    Garante que falhas de escrita ou falhas de gravação em config.json não deixem
    um falso positivo de sucesso em memória.
    """
    label = mes.replace("/", "_")
    titulo = f"Mês {mes}"
    try:
        caminho = gerar_relatorio_csv(dados, label, titulo)
    except Exception as e:
        log.error("Falha ao gerar CSV de exportação silenciosa para %s: %s", mes, e)
        return None

    nome_arquivo = os.path.basename(caminho)
    if mes not in config.get("exported_months", []):
        config.setdefault("exported_months", []).append(mes)
        try:
            save_config(config)
        except Exception as e:
            log.error("Falha ao salvar config após exportar %s: %s", mes, e)
            if mes in config.get("exported_months", []):
                config["exported_months"].remove(mes)
            return None

    return nome_arquivo


# ─────────────────────────────────────────────
# SERVIÇO: ATUALIZAÇÃO OTA (GITHUB RELEASES)
# ─────────────────────────────────────────────

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

OTA_ROOT_FILES = ("app.py", "CHANGELOG.md", "README.md", "LICENSE")
OTA_DIRS_EXTS = {
    "core": (".py",),
    "ui": (".py",),
    "layouts": (".json",),
    "hardware": (".py",),
}
OTA_REQUIRED_FILES = (
    "app.py",
    "core/config.py",
    "core/database.py",
    "core/services.py",
    "ui/app_window.py",
    "ui/kiosk.py",
    "ui/dialogs.py",
    "layouts/lab_informatica.json",
)
OTA_PROTECTED_NAMES = {
    "lab.db",
    "config.json",
    "exports",
    "backups",
    ".git",
    ".gitignore",
    ".agents",
    "PROJECT_STATE.md",
    "docs",
    "temp",
}


def parse_semver(ver_str: str) -> tuple[int, int, int] | None:
    """Converte string SemVer estrita ('v1.4.0' ou '1.4.0') em tupla (major, minor, patch)."""
    if not ver_str or not isinstance(ver_str, str):
        return None
    s = ver_str.strip()
    if s.startswith(("v", "V")):
        s = s[1:]
    m = _SEMVER_RE.fullmatch(s)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def comparar_versoes_ota(remote_tag: str, local_ver: str = VERSAO_ATUAL) -> bool:
    """Retorna True se remote_tag for uma versão SemVer estrita maior que local_ver."""
    rem = parse_semver(remote_tag)
    loc = parse_semver(local_ver)
    if rem is None or loc is None:
        return False
    return rem > loc


def postergar_ota_hoje(config: dict) -> None:
    """Grava a data de hoje em config['ota_postergado_em'] para suprimir novos avisos no dia."""
    config["ota_postergado_em"] = agora().strftime("%Y-%m-%d")
    save_config(config)


def verificar_atualizacao_ota(config: dict, opener=None) -> dict:
    """Consulta a última release no GitHub (timeout 5s, falha 100% silenciosa).

    Retorna dict:
      {"disponivel": False} ou
      {"disponivel": True, "versao_nova": str, "tag_name": str, "zipball_url": str, "notas": str}
    """
    owner = (config.get("repo_updater_owner") or "4mrco").strip()
    repo = (config.get("repo_updater_name") or "labctrl").strip()
    if not owner or not repo:
        return {"disponivel": False}

    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "LabCTRL-OTA",
        },
    )
    open_fn = opener if opener is not None else urllib.request.urlopen

    try:
        with open_fn(req, timeout=5) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return {"disponivel": False}
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"disponivel": False}
        tag_name = str(data.get("tag_name") or "").strip()
        zipball_url = str(data.get("zipball_url") or "").strip()
        if not tag_name or not zipball_url:
            return {"disponivel": False}
        if not comparar_versoes_ota(tag_name, VERSAO_ATUAL):
            return {"disponivel": False}
        rem_tuple = parse_semver(tag_name)
        versao_str = f"{rem_tuple[0]}.{rem_tuple[1]}.{rem_tuple[2]}"
        return {
            "disponivel": True,
            "versao_nova": versao_str,
            "tag_name": tag_name,
            "zipball_url": zipball_url,
            "notas": str(data.get("body") or ""),
        }
    except Exception:
        return {"disponivel": False}


def iniciar_verificacao_ota_async(config: dict, callback) -> threading.Thread:
    """Dispara verificação OTA em thread daemon e invoca callback(resultado)."""
    def _worker():
        res = verificar_atualizacao_ota(config)
        if callback:
            try:
                callback(res)
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def baixar_pacote_ota(zipball_url: str, dest_zip_path: str, opener=None) -> str:
    """Baixa zipball_url via HTTPS de forma atômica para dest_zip_path."""
    if not zipball_url or not str(zipball_url).startswith("https://"):
        raise ValueError("URL de atualização inválida (deve utilizar HTTPS).")
    os.makedirs(os.path.dirname(os.path.abspath(dest_zip_path)), exist_ok=True)
    tmp_zip = f"{dest_zip_path}.tmp"
    req = urllib.request.Request(
        zipball_url,
        headers={"User-Agent": "LabCTRL-OTA"},
    )
    open_fn = opener if opener is not None else urllib.request.urlopen
    try:
        with open_fn(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise RuntimeError(f"Download falhou com status HTTP {status}.")
            with open(tmp_zip, "wb") as f:
                shutil.copyfileobj(resp, f)
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp_zip, dest_zip_path)
    except Exception:
        if os.path.exists(tmp_zip):
            try:
                os.remove(tmp_zip)
            except OSError:
                pass
        raise
    return dest_zip_path


def validar_e_extrair_zip_ota(zip_path: str, extract_dir: str) -> str:
    """Valida integridade e segurança do ZIP (rejeitando path traversal e symlinks),
    extrai em extract_dir, localiza o diretório-raiz único do GitHub e valida arquivos essenciais.
    Retorna o caminho de candidate_root.
    """
    if not os.path.isfile(zip_path) or not zipfile.is_zipfile(zip_path):
        raise ValueError("O arquivo de atualização não é um arquivo ZIP válido.")

    shutil.rmtree(extract_dir, ignore_errors=True)
    os.makedirs(extract_dir, exist_ok=True)
    real_extract_dir = os.path.realpath(extract_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        corrompido = zf.testzip()
        if corrompido is not None:
            raise ValueError(f"Arquivo corrompido dentro do ZIP: {corrompido}")

        infos = zf.infolist()
        if not infos:
            raise ValueError("Arquivo ZIP vazio.")

        for info in infos:
            raw_name = info.filename
            if not raw_name or raw_name.startswith(("/", "\\")) or "\\" in raw_name:
                raise ValueError(f"Entrada de caminho inseguro no ZIP: {raw_name!r}")
            parts = [p for p in raw_name.split("/") if p]
            if not parts or ".." in parts or "." in parts:
                raise ValueError(f"Segmento de path traversal detectado no ZIP: {raw_name!r}")
            unix_mode = (info.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ValueError(f"Link simbólico rejeitado no ZIP: {raw_name!r}")
            target_path = os.path.realpath(os.path.join(real_extract_dir, *parts))
            if os.path.commonpath([real_extract_dir, target_path]) != real_extract_dir or target_path == real_extract_dir:
                raise ValueError(f"Tentativa de extração fora do diretório de staging: {raw_name!r}")

        for info in infos:
            parts = [p for p in info.filename.split("/") if p]
            target_path = os.path.join(real_extract_dir, *parts)
            if info.is_dir() or info.filename.endswith("/"):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(info, "r") as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    top_entries = [os.path.join(real_extract_dir, e) for e in os.listdir(real_extract_dir)]
    top_dirs = [d for d in top_entries if os.path.isdir(d)]
    if len(top_dirs) == 1 and len(top_entries) == 1:
        candidate_root = top_dirs[0]
    else:
        raise ValueError("Pacote de release inválido: deve conter um único diretório-raiz.")

    for req_rel in OTA_REQUIRED_FILES:
        req_abs = os.path.join(candidate_root, *req_rel.split("/"))
        if not os.path.isfile(req_abs):
            raise ValueError(f"Arquivo essencial ausente no pacote OTA: {req_rel}")

    return candidate_root


def coletar_arquivos_whitelist(root_dir: str) -> list[str]:
    """Retorna lista ordenada de caminhos relativos pertencentes à whitelist existentes em root_dir."""
    elegiveis: list[str] = []
    for fname in OTA_ROOT_FILES:
        fpath = os.path.join(root_dir, fname)
        if os.path.isfile(fpath) and not os.path.islink(fpath):
            elegiveis.append(fname)

    for subdir, exts in OTA_DIRS_EXTS.items():
        dpath = os.path.join(root_dir, subdir)
        if not os.path.isdir(dpath) or os.path.islink(dpath):
            continue
        for entry in sorted(os.listdir(dpath)):
            full = os.path.join(dpath, entry)
            if os.path.isfile(full) and not os.path.islink(full) and entry.endswith(exts):
                elegiveis.append(f"{subdir}/{entry}")

    return elegiveis


def _copiar_arquivo_atomico_ota(src_file: str, dst_file: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(dst_file)), exist_ok=True)
    tmp_dst = f"{dst_file}.ota.tmp"
    try:
        with open(src_file, "rb") as fsrc, open(tmp_dst, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)
            fdst.flush()
            os.fsync(fdst.fileno())
        os.replace(tmp_dst, dst_file)
    except Exception:
        if os.path.exists(tmp_dst):
            try:
                os.remove(tmp_dst)
            except OSError:
                pass
        raise


def aplicar_atualizacao_ota(candidate_root: str, base_dir: str = BASE_DIR) -> None:
    """Cria snapshot de rollback em temp/ota/rollback/ e substitui atomicamente
    apenas os arquivos da whitelist em base_dir. Em caso de falha parcial,
    restaura a versão anterior a partir do rollback.
    """
    for req_rel in OTA_REQUIRED_FILES:
        req_abs = os.path.join(candidate_root, *req_rel.split("/"))
        if not os.path.isfile(req_abs):
            raise ValueError(f"Arquivo essencial ausente em candidate_root: {req_rel}")

    novos_rel = coletar_arquivos_whitelist(candidate_root)
    if not novos_rel:
        raise ValueError("Nenhum arquivo elegível encontrado na whitelist do pacote.")

    rollback_dir = os.path.join(base_dir, "temp", "ota", "rollback")
    shutil.rmtree(rollback_dir, ignore_errors=True)
    os.makedirs(rollback_dir, exist_ok=True)

    atuais_rel = coletar_arquivos_whitelist(base_dir)
    for rel in atuais_rel:
        src_cur = os.path.join(base_dir, *rel.split("/"))
        dst_rb = os.path.join(rollback_dir, *rel.split("/"))
        _copiar_arquivo_atomico_ota(src_cur, dst_rb)

    try:
        for rel in novos_rel:
            top_seg = rel.split("/")[0]
            if top_seg in OTA_PROTECTED_NAMES or rel.endswith((".db", ".log", ".tmp")):
                continue
            src_new = os.path.join(candidate_root, *rel.split("/"))
            dst_inst = os.path.join(base_dir, *rel.split("/"))
            _copiar_arquivo_atomico_ota(src_new, dst_inst)
    except Exception as e:
        log.error("Falha durante aplicação OTA; iniciando rollback: %s", e)
        for rel in atuais_rel:
            rb_src = os.path.join(rollback_dir, *rel.split("/"))
            rb_dst = os.path.join(base_dir, *rel.split("/"))
            if os.path.isfile(rb_src):
                try:
                    _copiar_arquivo_atomico_ota(rb_src, rb_dst)
                except Exception as rb_err:
                    log.error("Erro ao restaurar %s no rollback: %s", rel, rb_err)
        raise RuntimeError(f"A atualização falhou e a versão anterior foi restaurada ({e}).") from e


def baixar_e_aplicar_ota(zipball_url: str, base_dir: str = BASE_DIR, opener=None) -> None:
    """Executa o fluxo completo de download, validação, extração, backup de rollback,
    aplicação da whitelist e limpeza de staging.
    """
    ota_dir = os.path.join(base_dir, "temp", "ota")
    os.makedirs(ota_dir, exist_ok=True)
    zip_path = os.path.join(ota_dir, "release.zip")
    extract_dir = os.path.join(ota_dir, "extracted")

    baixar_pacote_ota(zipball_url, zip_path, opener=opener)
    candidate_root = validar_e_extrair_zip_ota(zip_path, extract_dir)
    aplicar_atualizacao_ota(candidate_root, base_dir=base_dir)

    # Limpeza pós-sucesso (preservando temp/ota/rollback/)
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except OSError:
            pass
    shutil.rmtree(extract_dir, ignore_errors=True)
