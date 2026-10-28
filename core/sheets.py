"""
core/sheets.py — Cliente HTTP assíncrono para integração com Google Sheets via Apps Script Webhook.

Regras arquiteturais:
- Zero dependências externas (apenas stdlib: urllib.request, json, queue, threading, logging).
- Zero importações de tkinter ou core/database.py.
- Nunca recebe nem modifica config.json diretamente.
- Nunca expõe ou registra o token em logs.
"""

import json
import logging
import queue
import threading
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

SHEETS_HEADER = [
    "Data",
    "Entrada",
    "Saída",
    "Nome",
    "Matrícula",
    "Máquina(Nº)",
    "Bolsista presente",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitizar_celula_sheets(valor) -> str:
    """Converte o valor para string e previne Formula Injection no Google Sheets.

    Prefixa com apóstrofo (') textos iniciados por '=', '+', '-' ou '@',
    exceto números puros (ex.: -10, +3.14) e o marcador canônico '-' de sem máquina.
    """
    if valor is None:
        return ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(valor)
    s = str(valor)
    s_lstrip = s.lstrip()
    if not s_lstrip or s_lstrip == "-":
        return s
    if s_lstrip[0] in ("+", "-"):
        rest = s_lstrip[1:]
        if rest and rest.replace(".", "", 1).isdigit():
            return s
    if s_lstrip.startswith(_FORMULA_PREFIXES):
        return f"'{s}"
    return s


def montar_matriz_sheets(dados_normalizados: list[tuple]) -> list[list[str]]:
    """Constrói a matriz completa de 7 colunas (cabeçalho + linhas sanitizadas)."""
    matriz: list[list[str]] = [list(SHEETS_HEADER)]
    for linha in dados_normalizados:
        matriz.append([sanitizar_celula_sheets(col) for col in linha[:7]])
    return matriz


def _sanitizar_erro_transporte(exc: Exception, token: str) -> str:
    """Extrai mensagem segura de erro sem jamais vazar o token."""
    msg = str(exc) or exc.__class__.__name__
    if token and token in msg:
        msg = msg.replace(token, "***")
    return msg


def enviar_mes_sheets(
    webhook_url: str,
    token: str,
    mes_aba: str,
    rows: list[list[str]],
    timeout: int = 10,
    opener=None,
) -> dict:
    """Envia a matriz mensal completa via POST JSON para o Apps Script Web App.

    Retorna:
      {"ok": True, "mes": mes_aba, "rows_sent": int, "error": None}
      ou
      {"ok": False, "mes": mes_aba, "error": str}
    """
    url_clean = (webhook_url or "").strip()
    token_clean = (token or "").strip()
    mes_clean = (mes_aba or "").strip()

    if not url_clean or not url_clean.startswith("https://"):
        err = "URL do webhook inválida (deve iniciar com https://)."
        log.error("Falha ao enviar para Google Sheets (%s): %s", mes_clean, err)
        return {"ok": False, "mes": mes_clean, "error": err}

    if not token_clean:
        err = "Token do webhook não configurado."
        log.error("Falha ao enviar para Google Sheets (%s): %s", mes_clean, err)
        return {"ok": False, "mes": mes_clean, "error": err}

    if not mes_clean:
        err = "Mês da aba não informado."
        log.error("Falha ao enviar para Google Sheets: %s", err)
        return {"ok": False, "mes": mes_clean, "error": err}

    if not rows or not isinstance(rows, list) or len(rows) < 2:
        err = "Matriz de dados vazia ou sem registros para enviar."
        log.error("Falha ao enviar para Google Sheets (%s): %s", mes_clean, err)
        return {"ok": False, "mes": mes_clean, "error": err}

    rows_sanitizadas = [
        list(SHEETS_HEADER) if idx == 0 else [sanitizar_celula_sheets(c) for c in r[:7]]
        for idx, r in enumerate(rows)
    ]

    payload_bytes = json.dumps(
        {
            "token": token_clean,
            "mes": mes_clean,
            "rows": rows_sanitizadas,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        url_clean,
        data=payload_bytes,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "LabCTRL-Sheets",
        },
        method="POST",
    )
    open_fn = opener if opener is not None else urllib.request.urlopen

    try:
        with open_fn(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read().decode("utf-8", errors="replace")
            if status != 200:
                err = f"HTTP {status}"
                log.error("Falha HTTP no Google Sheets (%s): %s", mes_clean, err)
                return {"ok": False, "mes": mes_clean, "error": err}

        data = json.loads(raw)
        if not isinstance(data, dict):
            err = "Resposta JSON inválida do webhook."
            log.error("Falha no Google Sheets (%s): %s", mes_clean, err)
            return {"ok": False, "mes": mes_clean, "error": err}

        if not data.get("ok"):
            err_code = str(data.get("error") or "Erro retornado pelo Apps Script")
            if token_clean and token_clean in err_code:
                err_code = err_code.replace(token_clean, "***")
            log.error("Webhook Google Sheets recusou envio (%s): %s", mes_clean, err_code)
            return {"ok": False, "mes": mes_clean, "error": err_code}

        return {
            "ok": True,
            "mes": mes_clean,
            "rows_sent": len(rows_sanitizadas) - 1,
            "error": None,
        }
    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}"
        log.error("Erro HTTP ao sincronizar Google Sheets (%s): %s", mes_clean, err)
        return {"ok": False, "mes": mes_clean, "error": err}
    except urllib.error.URLError as e:
        reason = _sanitizar_erro_transporte(e.reason if hasattr(e, "reason") else e, token_clean)
        err = f"Falha de conexão ({reason})"
        log.error("Erro de rede ao sincronizar Google Sheets (%s): %s", mes_clean, err)
        return {"ok": False, "mes": mes_clean, "error": err}
    except TimeoutError:
        err = "Tempo limite de conexão esgotado (timeout)."
        log.error("Timeout ao sincronizar Google Sheets (%s).", mes_clean)
        return {"ok": False, "mes": mes_clean, "error": err}
    except json.JSONDecodeError:
        err = "Resposta inesperada do servidor (não é JSON válido)."
        log.error("Resposta não-JSON ao sincronizar Google Sheets (%s).", mes_clean)
        return {"ok": False, "mes": mes_clean, "error": err}
    except Exception as e:
        err = _sanitizar_erro_transporte(e, token_clean)
        log.error("Erro inesperado ao sincronizar Google Sheets (%s): %s", mes_clean, err)
        return {"ok": False, "mes": mes_clean, "error": err}


def testar_conexao_sheets(
    webhook_url: str,
    token: str,
    timeout: int = 6,
    opener=None,
) -> dict:
    """Envia um ping leve {'token': token, 'ping': True} sem modificar nenhuma aba.

    Retorna:
      {"ok": True, "error": None}
      ou
      {"ok": False, "error": str}
    """
    url_clean = (webhook_url or "").strip()
    token_clean = (token or "").strip()

    if not url_clean or not url_clean.startswith("https://"):
        return {"ok": False, "error": "URL inválida (deve iniciar com https://)"}

    if not token_clean:
        return {"ok": False, "error": "Token não informado"}

    payload_bytes = json.dumps(
        {"token": token_clean, "ping": True},
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        url_clean,
        data=payload_bytes,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "LabCTRL-Sheets",
        },
        method="POST",
    )
    open_fn = opener if opener is not None else urllib.request.urlopen

    try:
        with open_fn(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read().decode("utf-8", errors="replace")
            if status != 200:
                return {"ok": False, "error": f"HTTP {status}"}

        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"ok": False, "error": "Resposta JSON inválida"}

        if not data.get("ok"):
            err_code = str(data.get("error") or "Token incorreto ou recusado")
            if token_clean and token_clean in err_code:
                err_code = err_code.replace(token_clean, "***")
            return {"ok": False, "error": err_code}

        return {"ok": True, "error": None}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        reason = _sanitizar_erro_transporte(e.reason if hasattr(e, "reason") else e, token_clean)
        return {"ok": False, "error": f"Falha de rede ({reason})"}
    except TimeoutError:
        return {"ok": False, "error": "Timeout de conexão"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "Resposta inválida do servidor"}
    except Exception as e:
        return {"ok": False, "error": _sanitizar_erro_transporte(e, token_clean)}


def iniciar_sync_sheets_async(
    webhook_url: str,
    token: str,
    mes_aba: str,
    rows: list[list[str]],
    *,
    mes_ref: str | None = None,
    marcar_mes: bool = True,
    timeout: int = 10,
    opener=None,
) -> queue.Queue:
    """Dispara enviar_mes_sheets em thread daemon e retorna a queue.Queue imediatamente."""
    result_queue: queue.Queue = queue.Queue()

    def _worker():
        res = enviar_mes_sheets(
            webhook_url=webhook_url,
            token=token,
            mes_aba=mes_aba,
            rows=rows,
            timeout=timeout,
            opener=opener,
        )
        res["mes"] = mes_ref if mes_ref is not None else mes_aba
        res["mes_aba"] = mes_aba
        res["marcar_mes"] = bool(marcar_mes)
        result_queue.put(res)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return result_queue
