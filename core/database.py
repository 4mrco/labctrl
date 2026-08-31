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
