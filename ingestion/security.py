"""Ingestão do Balanço Criminal da SSP-DF.

A SSP-DF não tem API. Ela publica, em uma página do Liferay, um par de arquivos
(PDF + XLS/XLSX) por Região Administrativa e por ano, com *slugs* opacos que
**se repetem entre anos diferentes**.

Decisão central deste módulo: **o ano e a RA são lidos de dentro da planilha,
nunca do link ou do texto da página.** O portal pode trocar, duplicar ou
reordenar links sem corromper o banco — o pior caso vira um download
redundante. É o que torna a ingestão confiável em cima de uma fonte que não
oferece contrato.

Layout verificado em arquivos reais de 2014–2026:

    linha 3  BALANÇO CRIMINAL
    linha 4  RA XX - ÁGUAS CLARAS
    linha 6  EIXOS INDICADORES | NATUREZA | TOTAL | <ano>
    linha 7  (vazio)           | (vazio)  |(vazio)| JAN FEV ... DEZ
    linha 8+ eixo, natureza, total, 12 valores mensais
"""

from __future__ import annotations

import html
import io
import logging
import re
from datetime import date

import pandas as pd

from .common import (
    connect,
    ingestion_run,
    PoliteSession,
    record_check,
    save_raw,
    settings,
    upsert,
)

log = logging.getLogger("ingestion.security")

PORTAL_URL = "https://www.ssp.df.gov.br/dados-por-regiao-administrativa/"
PORTAL_ORIGIN = "https://www.ssp.df.gov.br"

MONTHS = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

# "RA XX - ÁGUAS CLARAS", "RA I – BRASÍLIA", "RA IX- CEILÂNDIA"
RA_HEADER_RE = re.compile(r"\bRA\s+([IVXLCDM]+)\s*[-–—]\s*(.+)", re.IGNORECASE)

# Linhas de subtotal presentes na planilha. Somá-las duplicaria a contagem.
SUBTOTAL_MARKER = "TOTAL"


def _discover_spreadsheets(session: PoliteSession) -> list[str]:
    """Extrai as URLs de planilha da seção 'REGIÕES ADMINISTRATIVAS' da página.

    Retorna URLs únicas. Como RA e ano saem do conteúdo do arquivo, não
    precisamos confiar no rótulo do link — só precisamos da lista de arquivos.
    """
    response = session.get(PORTAL_URL)
    response.raise_for_status()
    page = response.text
    save_raw("security", "ssp_dados_por_ra.html", page)

    anchor = page.find('id="RAs"')
    if anchor == -1:
        raise ValueError(
            "Âncora 'RAs' não encontrada na página da SSP-DF — o layout mudou. "
            "Revise ingestion/security.py antes de seguir."
        )

    section = page[anchor:]
    urls: list[str] = []
    for href in re.findall(r'href="([^"]+)"', section):
        href = html.unescape(href)
        if "/documents/" not in href or "xls" not in href.lower():
            continue
        full = href if href.startswith("http") else PORTAL_ORIGIN + href
        if full not in urls:
            urls.append(full)
    return urls


def _read_workbook(content: bytes) -> pd.ExcelFile:
    """Escolhe o engine pelo magic number, não pela extensão do link.

    Os links terminam em `-xlsx` mesmo quando o arquivo é um .xls OLE2 antigo.
    """
    engine = "openpyxl" if content[:4] == b"PK\x03\x04" else "xlrd"
    return pd.ExcelFile(io.BytesIO(content), engine=engine)


def _find_header_row(frame: pd.DataFrame) -> int | None:
    for idx in range(min(20, len(frame))):
        cell = frame.iat[idx, 0]
        if isinstance(cell, str) and cell.strip().upper().startswith("EIXOS"):
            return idx
    return None


def _find_ra(frame: pd.DataFrame, header_row: int) -> tuple[str, str] | None:
    for idx in range(header_row + 1):
        for col in range(min(4, frame.shape[1])):
            cell = frame.iat[idx, col]
            if not isinstance(cell, str):
                continue
            match = RA_HEADER_RE.search(cell)
            if match:
                roman = match.group(1).upper()
                return f"RA-{roman}", " ".join(cell.split())
    return None


def _find_year(frame: pd.DataFrame, header_row: int, sheet_name: str) -> int | None:
    candidate = frame.iat[header_row, 3] if frame.shape[1] > 3 else None
    for raw_value in (candidate, sheet_name):
        match = re.search(r"(20\d{2})", str(raw_value))
        if match:
            return int(match.group(1))
    return None


def _to_count(value) -> int | None:
    """Converte a célula em contagem.

    Números vindos do Excel são usados como estão. A limpeza de separadores só
    vale para texto: aplicá-la a um float faria `12.0` virar `120` — o ponto
    decimal seria lido como separador de milhar.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(round(value))
    else:
        text = str(value).strip()
        if not text:
            return None
        # Texto vem no padrão pt-BR: "1.234" é mil duzentos e trinta e quatro.
        text = text.replace(".", "").replace(",", ".")
        try:
            number = int(round(float(text)))
        except ValueError:
            return None

    return number if number >= 0 else None


def parse_sheet(frame: pd.DataFrame, sheet_name: str, source_url: str) -> list[tuple]:
    """Converte uma aba do balanço criminal em linhas longas (RA × mês × natureza)."""
    header_row = _find_header_row(frame)
    if header_row is None:
        return []

    ra = _find_ra(frame, header_row)
    year = _find_year(frame, header_row, sheet_name)
    if ra is None or year is None:
        log.warning("Aba %r ignorada: RA=%s ano=%s (%s)", sheet_name, ra, year, source_url)
        return []
    ra_code, ra_label = ra

    # Mapa coluna -> nº do mês, lido do próprio arquivo (a posição JAN..DEZ é
    # estável, mas ler é mais barato que rezar).
    month_row = header_row + 1
    month_columns: dict[int, int] = {}
    for col in range(frame.shape[1]):
        cell = frame.iat[month_row, col]
        if isinstance(cell, str) and cell.strip().upper()[:3] in MONTHS:
            month_columns[col] = MONTHS.index(cell.strip().upper()[:3]) + 1
    if len(month_columns) != 12:
        log.warning(
            "Aba %r ignorada: %s colunas de mês encontradas (esperado 12) em %s",
            sheet_name, len(month_columns), source_url,
        )
        return []

    rows: list[tuple] = []
    current_axis: str | None = None
    for idx in range(month_row + 1, len(frame)):
        axis_cell = frame.iat[idx, 0]
        nature_cell = frame.iat[idx, 1]

        if isinstance(axis_cell, str) and axis_cell.strip():
            label = " ".join(axis_cell.split())
            # Subtotais ("1.TOTAL C.V.L.I.", "TOTAL CRIMES (CVLI + CCP)") não
            # viram eixo nem linha: somá-los duplicaria a contagem.
            if SUBTOTAL_MARKER not in label.upper():
                current_axis = label

        if not isinstance(nature_cell, str) or not nature_cell.strip():
            continue
        nature = " ".join(nature_cell.split()).rstrip(" *")
        if SUBTOTAL_MARKER in nature.upper() or current_axis is None:
            continue

        for col, month in month_columns.items():
            count = _to_count(frame.iat[idx, col])
            if count is None:
                continue
            rows.append((ra_code, year, month, current_axis, nature, count, ra_label, source_url))

    return _drop_future_months(rows, year)


def _drop_future_months(rows: list[tuple], year: int) -> list[tuple]:
    """No ano corrente, a planilha traz 0 nos meses que ainda não aconteceram.

    Gravar esses zeros produziria uma queda falsa no fim da série. Truncamos no
    último mês com qualquer ocorrência registrada. Efeito colateral aceito e
    documentado: um mês realmente zerado no fim do ano corrente, numa RA muito
    pequena, é descartado.
    """
    if year != date.today().year or not rows:
        return rows
    last_active = max((r[2] for r in rows if r[5] > 0), default=0)
    return [r for r in rows if r[2] <= last_active]


def run() -> None:
    cfg = settings()
    session = PoliteSession(cfg.user_agent, cfg.throttle_seconds)
    conn = connect()

    with ingestion_run(conn, "security") as (run_id, tracker):
        urls = _discover_spreadsheets(session)
        log.info("%s planilhas encontradas na página da SSP-DF", len(urls))
        record_check(
            conn,
            run_id,
            "security.spreadsheets_discovered",
            passed=len(urls) >= 100,
            severity="ERROR",
            observed=len(urls),
            expected=">= 100 (35 RAs x ~9 anos)",
        )

        all_rows: list[tuple] = []
        failures: list[str] = []
        for position, url in enumerate(urls, start=1):
            try:
                response = session.get(url)
                response.raise_for_status()
                content = response.content
                if content[:4] not in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
                    raise ValueError("resposta não é uma planilha (provável HTML de erro)")

                save_raw("security", url.rsplit("/", 1)[-1] + ".bin", content)
                workbook = _read_workbook(content)
                # Arquivo com várias abas é o agregado histórico; arquivo de aba
                # única é o balanço daquele ano específico, mantido e revisado
                # pela SSP. Quando os dois discordam, o específico prevalece.
                priority = 0 if len(workbook.sheet_names) > 1 else 1
                for sheet_name in workbook.sheet_names:
                    frame = pd.read_excel(workbook, sheet_name=sheet_name, header=None)
                    all_rows.extend(
                        (priority, row) for row in parse_sheet(frame, sheet_name, url)
                    )
            except Exception as exc:  # uma planilha ruim não derruba o lote
                failures.append(f"{url}: {type(exc).__name__}: {exc}")
                log.warning("Falha em %s — %s", url, exc)

            if position % 25 == 0:
                log.info("... %s/%s planilhas processadas", position, len(urls))

        record_check(
            conn,
            run_id,
            "security.download_failures",
            passed=len(failures) <= len(urls) * 0.1,
            severity="WARN",
            observed=failures[:10],
            expected="<= 10% das planilhas com falha",
        )

        # Mesma RA/ano aparece em vários arquivos (o agregado histórico repete
        # anos que também têm arquivo próprio) e a mesma natureza mudou de eixo
        # ao longo dos anos (ex.: ROUBO EM RESIDÊNCIA saiu de "OUTROS CRIMES"
        # para "C.C.P." em 2016). O grão é a natureza, não o eixo.
        #
        # Quando duas fontes discordam do NÚMERO para a mesma chave, isso não é
        # ruído: é a SSP tendo republicado o dado. Registramos o conflito e
        # ficamos com a última leitura.
        deduped: dict[tuple, tuple[int, tuple]] = {}
        conflicts: list[str] = []
        for priority, row in all_rows:
            key = (row[0], row[1], row[2], row[4])
            previous = deduped.get(key)
            if previous is not None:
                if previous[1][5] != row[5]:
                    conflicts.append(f"{key} {previous[1][5]}→{row[5]}")
                if previous[0] > priority:
                    continue  # o arquivo anual já venceu; agregado não sobrescreve
            deduped[key] = (priority, row)
        rows = [row for _, row in deduped.values()]

        record_check(
            conn,
            run_id,
            "security.value_conflicts_between_files",
            passed=len(conflicts) <= len(rows) * 0.02,
            severity="WARN",
            observed=f"{len(conflicts)} conflitos; exemplos: {conflicts[:5]}",
            expected="<= 2% das chaves com valores divergentes entre arquivos",
        )
        if conflicts:
            log.warning(
                "%s chaves com valores divergentes entre arquivos da SSP (última leitura vence)",
                len(conflicts),
            )

        record_check(
            conn,
            run_id,
            "security.rows_parsed",
            passed=len(rows) > 10_000,
            severity="ERROR",
            observed=len(rows),
            expected="> 10.000 linhas (RA x ano x mês x natureza)",
        )

        tracker["rows"] += upsert(
            conn,
            "raw.security_occurrence",
            [
                "ra_code",
                "reference_year",
                "reference_month",
                "axis_source",
                "nature_source",
                "occurrences",
                "ra_label_source",
                "_source_url",
            ],
            rows,
            conflict_columns=["ra_code", "reference_year", "reference_month", "nature_source"],
        )
        log.info(
            "%s linhas gravadas (%s brutas, %s após deduplicação)",
            len(rows), len(all_rows), len(rows),
        )
        tracker["requests"] = session.requests_made

    conn.close()


if __name__ == "__main__":
    from .common import configure_logging

    configure_logging()
    run()
