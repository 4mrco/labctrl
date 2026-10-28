/**
 * LabCTRL — Google Apps Script Webhook (v1.5.0)
 * Receptor HTTP para sincronizacao e espelhamento no Google Sheets.
 */

function _jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return _jsonResponse({ ok: false, error: "empty_payload" });
    }

    const expectedToken = PropertiesService.getScriptProperties().getProperty("TOKEN")
      || PropertiesService.getScriptProperties().getProperty("SECRET_TOKEN");
    if (!expectedToken) {
      return _jsonResponse({ ok: false, error: "server_token_not_configured" });
    }

    let payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return _jsonResponse({ ok: false, error: "invalid_json" });
    }

    if (!payload || typeof payload.token !== "string" || payload.token !== expectedToken) {
      return _jsonResponse({ ok: false, error: "unauthorized" });
    }

    // 1. Suporte a Teste de Conexão (Ping leve sem tocar na planilha)
    if (payload.ping === true) {
      return _jsonResponse({ ok: true, ping: true });
    }

    // 2. Validação estrita do contrato de dados (Nome da aba e matriz N >= 2 x 7 colunas)
    const mes = String(payload.mes || "").trim();
    if (!mes || mes.length > 50) {
      return _jsonResponse({ ok: false, error: "invalid_month_format" });
    }

    const rows = payload.rows;
    if (!Array.isArray(rows) || rows.length < 2) {
      return _jsonResponse({ ok: false, error: "invalid_rows_matrix" });
    }

    for (let i = 0; i < rows.length; i++) {
      if (!Array.isArray(rows[i]) || rows[i].length !== 7) {
        return _jsonResponse({ ok: false, error: "invalid_column_count_at_row_" + i });
      }
    }

    // 3. Controle de concorrência e escrita atômica na aba do mês
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      let sheet = ss.getSheetByName(mes);
      if (!sheet) {
        sheet = ss.insertSheet(mes, ss.getNumSheets());
      }

      sheet.clearContents();
      const range = sheet.getRange(1, 1, rows.length, 7);
      // Preserva zeros à esquerda (ex.: máquina "04") e evita coerção indevida de datas/fórmulas
      range.setNumberFormat("@");
      range.setValues(rows);
      SpreadsheetApp.flush();
    } finally {
      lock.releaseLock();
    }

    return _jsonResponse({ ok: true, mes: mes, rows_written: rows.length - 1 });
  } catch (err) {
    return _jsonResponse({
      ok: false,
      error: String(err && err.message ? err.message : err)
    });
  }
}
