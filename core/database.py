import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, date, timedelta

from core.config import DB_FILE, SCHEMA_VERSION

log = logging.getLogger(__name__)

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


def safe_query(default_return):
    """
    Decorator to catch 'no such table' errors during background reads,
    silently run init_db() to auto-heal the schema, and return a safe default.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "no such table" in str(e).lower():
                    log.warning(f"Auto-healing DB schema due to error: {e}")
                    init_db()
                    return default_return
                raise
        return wrapper
    return decorator


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

@safe_query(None)
def buscar_aluno(matricula: str) -> tuple | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT nome, tipo FROM alunos WHERE matricula=?", (matricula,)
        ).fetchone()


def inserir_aluno(matricula: str, nome: str, tipo: str = "aluno") -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO alunos VALUES (?,?,?)", (matricula, nome, tipo))


@safe_query([])
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

def inserir_registro(matricula, nome, data, hora, maquina, bolsista) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO registros
               (matricula,nome,data,entrada,maquina,bolsista,status)
               VALUES (?,?,?,?,?,?,'ATIVO')""",
            (matricula, nome, data, hora, maquina, bolsista),
        )
        return cursor.lastrowid


def finalizar_registro(rid: int, hora_saida: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE registros SET saida=?, status='FINALIZADO' WHERE id=?",
            (hora_saida, rid),
        )


def reabrir_registro(rid: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE registros SET saida=NULL, status='ATIVO' WHERE id=?",
            (rid,),
        )


@safe_query(None)
def buscar_registro_ativo(matricula: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id FROM registros
               WHERE matricula=? AND status='ATIVO'
               ORDER BY id DESC LIMIT 1""",
            (matricula,),
        ).fetchone()
    return row[0] if row else None


@safe_query(None)
def buscar_registro_por_id(rid: int) -> tuple | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT id,nome,matricula,data,entrada,saida,maquina,bolsista,status
               FROM registros WHERE id=?""",
            (rid,),
        ).fetchone()


def atualizar_registro(rid: int, nome: str, data: str, entrada: str, saida: str, maquina: str) -> None:
    status = "FINALIZADO" if saida else "ATIVO"
    with get_conn() as conn:
        conn.execute(
            "UPDATE registros SET nome=?, data=?, entrada=?, saida=?, maquina=?, status=? WHERE id=?",
            (nome, data, entrada, saida or None, maquina, status, rid),
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


def _parse_data_calendario(valor: str) -> date | None:
    """Interpreta string D/M/YYYY ou DD/MM/YYYY válida no calendário (ano de 4 dígitos)."""
    if not valor or not isinstance(valor, str):
        return None
    s = valor.strip()
    partes = s.split("/")
    if len(partes) != 3:
        return None
    d_str, m_str, y_str = partes
    if not (1 <= len(d_str) <= 2 and d_str.isdigit()):
        return None
    if not (1 <= len(m_str) <= 2 and m_str.isdigit()):
        return None
    if not (len(y_str) == 4 and y_str.isdigit() and y_str[0] != "0"):
        return None
    try:
        return date(int(y_str), int(m_str), int(d_str))
    except ValueError:
        return None


def _parse_mes_ano_param(mes: str) -> tuple[int, int] | None:
    """Interpreta parâmetro mensal 'MM/YYYY' ou 'M/YYYY' retornando (ano, mes)."""
    if not mes or not isinstance(mes, str):
        return None
    partes = mes.strip().split("/")
    if len(partes) != 2:
        return None
    m_str, y_str = partes
    if not (1 <= len(m_str) <= 2 and m_str.isdigit()):
        return None
    if not (len(y_str) == 4 and y_str.isdigit() and y_str[0] != "0"):
        return None
    m_int, y_int = int(m_str), int(y_str)
    if not (1 <= m_int <= 12):
        return None
    return (y_int, m_int)


@safe_query([])
def buscar_registros_por_mes(mes: str) -> list[tuple]:
    ym = _parse_mes_ano_param(mes)
    if ym is None:
        return []
    yyyy, mm = ym
    p_pad = f"%/{mm:02d}/{yyyy:04d}"
    p_raw = f"%/{mm}/{yyyy:04d}"
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id,nome,matricula,data,entrada,saida,maquina,bolsista,status
               FROM registros WHERE data LIKE ? OR data LIKE ? ORDER BY id DESC""",
            (p_pad, p_raw),
        ).fetchall()
    resultado = []
    for r in rows:
        dt = _parse_data_calendario(r[3])
        if dt is not None and dt.year == yyyy and dt.month == mm:
            resultado.append(r)
    return resultado


@safe_query([])
def buscar_registros_orfaos(data_ref: str | date | datetime | None = None) -> list[tuple]:
    if isinstance(data_ref, datetime):
        ref_dt = data_ref.date()
    elif isinstance(data_ref, date):
        ref_dt = data_ref
    elif isinstance(data_ref, str):
        ref_dt = _parse_data_calendario(data_ref) or datetime.now().date()
    else:
        ref_dt = datetime.now().date()

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, nome, matricula, data, entrada FROM registros
               WHERE status='ATIVO'"""
        ).fetchall()

    orfaos = []
    for r in rows:
        dt = _parse_data_calendario(r[3])
        if dt is not None and dt < ref_dt:
            orfaos.append(r)
    return orfaos


@safe_query(0)
def contar_registros_hoje(hoje: str) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM registros WHERE data=?", (hoje,)
        ).fetchone()[0]


@safe_query(0)
def contar_ativos() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM registros WHERE status='ATIVO'"
        ).fetchone()[0]


@safe_query([])
def buscar_registros_ativos_detalhes() -> list[tuple]:
    """Retorna [(id, nome, matricula, data, entrada), ...] de todos os registros com status ATIVO."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT id, nome, matricula, data, entrada FROM registros
               WHERE status='ATIVO'"""
        ).fetchall()


@safe_query([])
def buscar_maquinas_ocupadas() -> list[str]:
    """Retorna lista de máquinas em uso (status ATIVO), incluindo repetições para ML."""
    with get_conn() as conn:
        return [r[0] for r in conn.execute(
            "SELECT maquina FROM registros WHERE status='ATIVO' AND maquina IS NOT NULL AND maquina != '-'"
        ).fetchall()]


@safe_query(None)
def buscar_ultimo_registro() -> tuple | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT data, entrada FROM registros ORDER BY id DESC LIMIT 1"
        ).fetchone()


@safe_query([])
def buscar_meses_com_registros() -> list[tuple[int, int]]:
    """Retorna lista de tuplas (ano, mes) decrescente dos meses que possuem registros com data válida."""
    with get_conn() as conn:
        datas = [r[0] for r in conn.execute(
            "SELECT DISTINCT data FROM registros"
        ).fetchall()]
    ym_set: set[tuple[int, int]] = set()
    for d in datas:
        dt = _parse_data_calendario(d)
        if dt is not None:
            ym_set.add((dt.year, dt.month))
    return sorted(ym_set, reverse=True)


@safe_query([])
def buscar_meses() -> list[str]:
    ym_list = buscar_meses_com_registros()
    meses = [f"{mm:02d}/{yyyy:04d}" for yyyy, mm in ym_list]
    return meses or [datetime.now().strftime("%m/%Y")]


# ── Export queries ──

@safe_query([])
def buscar_export_mes(mes: str) -> list[tuple]:
    ym = _parse_mes_ano_param(mes)
    if ym is None:
        return []
    yyyy, mm = ym
    p_pad = f"%/{mm:02d}/{yyyy:04d}"
    p_raw = f"%/{mm}/{yyyy:04d}"
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, data, entrada, saida, nome, matricula, maquina, bolsista
               FROM registros WHERE data LIKE ? OR data LIKE ?""",
            (p_pad, p_raw),
        ).fetchall()
    validos = []
    for rid, data, entrada, saida, nome, matricula, maquina, bolsista in rows:
        dt = _parse_data_calendario(data)
        if dt is not None and dt.year == yyyy and dt.month == mm:
            validos.append((dt, entrada or "", rid, dt.strftime("%d/%m/%Y"), entrada, saida, nome, matricula, maquina, bolsista))
    validos.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3:] for item in validos]


@safe_query([])
def buscar_export_dia(dia: str) -> list[tuple]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT data,entrada,saida,nome,matricula,maquina,bolsista
               FROM registros WHERE data=? ORDER BY entrada""",
            (dia,),
        ).fetchall()


@safe_query(([], ""))
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


@safe_query([])
def buscar_export_semana(datas: list[str]) -> list[tuple]:
    ph = ",".join("?" * len(datas))
    with get_conn() as conn:
        return conn.execute(
            f"""SELECT data,entrada,saida,nome,matricula,maquina,bolsista
                FROM registros WHERE data IN ({ph}) ORDER BY data, entrada""",
            datas,
        ).fetchall()


# ── Bolsistas ──

@safe_query([])
def buscar_bolsistas() -> list[str]:
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT nome FROM bolsistas").fetchall()]


def inserir_bolsista(nome: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO bolsistas VALUES (?)", (nome,))


def deletar_bolsista(nome: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM bolsistas WHERE nome=?", (nome,))
