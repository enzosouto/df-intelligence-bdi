"""Testes do parser do Balanço Criminal da SSP-DF.

Este é o ponto mais frágil do pipeline: planilha sem contrato, layout que muda
entre anos, linhas de subtotal misturadas às de dado e meses futuros zerados no
arquivo do ano corrente. Cada teste aqui representa um erro que já seria
cometido sem ele.
"""

from datetime import date

import pandas as pd
import pytest

from ingestion.security import parse_sheet

URL = "https://www.ssp.df.gov.br/documents/d/ssp/teste-xlsx"


def build_sheet(year: int, rows: list[list], ra_header: str = "RA XX - ÁGUAS CLARAS"):
    """Reproduz o layout real: 8 linhas de cabeçalho, depois os dados."""
    header = [
        [None] * 15,
        [None] * 15,
        [None] * 15,
        [None, "BALANÇO CRIMINAL"] + [None] * 13,
        [None, ra_header] + [None] * 13,
        [None, f"COMPARATIVO MENSAL {year}"] + [None] * 13,
        ["EIXOS INDICADORES", "NATUREZA", "TOTAL", year] + [None] * 11,
        [None, None, None]
        + ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"],
    ]
    return pd.DataFrame(header + rows)


def test_extracts_region_year_and_monthly_values():
    frame = build_sheet(
        2021,
        [
            ["1. C.V.L.I.", "HOMICÍDIO", 7, 1, 2, 0, 0, 2, 0, 0, 2, 0, 0, 0, 0],
            [None, "LATROCÍNIO", 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
    )
    rows = parse_sheet(frame, "(mensal)2021", URL)

    assert len(rows) == 24, "2 naturezas x 12 meses"
    region_ids = {row[0] for row in rows}
    years = {row[1] for row in rows}
    assert region_ids == {"RA-XX"}, "o código da RA sai do cabeçalho da planilha"
    assert years == {2021}, "o ano sai do arquivo, nunca do link"

    january_homicides = next(r for r in rows if r[4] == "HOMICÍDIO" and r[2] == 1)
    assert january_homicides[5] == 1
    march_homicides = next(r for r in rows if r[4] == "HOMICÍDIO" and r[2] == 3)
    assert march_homicides[5] == 0, "zero de mês passado é dado, não ausência"


def test_subtotal_rows_are_discarded():
    """Somar os subtotais da planilha dobraria a contagem."""
    frame = build_sheet(
        2021,
        [
            ["1. C.V.L.I.", "HOMICÍDIO", 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ["1.TOTAL C.V.L.I.", None, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ["TOTAL CRIMES (CVLI + CCP)", None, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ["2. C.C.P.", "ROUBO DE VEÍCULO", 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
    )
    rows = parse_sheet(frame, "(mensal)2021", URL)

    natures = {row[4] for row in rows}
    assert natures == {"HOMICÍDIO", "ROUBO DE VEÍCULO"}
    assert not any("TOTAL" in nature for nature in natures)


def test_axis_carries_down_but_subtotal_never_becomes_axis():
    frame = build_sheet(
        2021,
        [
            ["2. C.C.P. - CRIMES CONTRA O PATRIMÔNIO", "ROUBO A TRANSEUNTE", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [None, "FURTO EM VEÍCULO", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ["2. TOTAL C.C.P.", None, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            ["3. OUTROS CRIMES", "ESTUPRO", 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ],
    )
    rows = parse_sheet(frame, "(mensal)2021", URL)

    axis_of = {row[4]: row[3] for row in rows}
    assert axis_of["FURTO EM VEÍCULO"].startswith("2. C.C.P."), "eixo herdado da linha anterior"
    assert axis_of["ESTUPRO"] == "3. OUTROS CRIMES", "subtotal não vira eixo"


def test_future_months_of_current_year_are_dropped():
    """No ano corrente a planilha traz 0 nos meses que ainda não aconteceram.

    Gravá-los desenharia uma queda que não existe.
    """
    current_year = date.today().year
    values = [0] * 12
    values[0] = 5  # apenas janeiro tem ocorrência
    frame = build_sheet(current_year, [["1. C.V.L.I.", "HOMICÍDIO", 5, *values]])

    rows = parse_sheet(frame, f"(mensal){current_year}", URL)
    months = {row[2] for row in rows}
    assert months == {1}, "só o mês com ocorrência sobrevive no ano corrente"


def test_past_years_keep_all_twelve_months_even_when_zero():
    values = [0] * 12
    values[0] = 5
    frame = build_sheet(2019, [["1. C.V.L.I.", "HOMICÍDIO", 5, *values]])

    rows = parse_sheet(frame, "(mensal)2019", URL)
    assert {row[2] for row in rows} == set(range(1, 13)), "ano fechado mantém os 12 meses"


def test_sheet_without_ra_header_is_skipped():
    """As abas de RISP (regiões integradas de segurança) não são RAs."""
    frame = build_sheet(
        2021,
        [["1. C.V.L.I.", "HOMICÍDIO", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]],
        ra_header="REGIÃO INTEGRADA DE SEGURANÇA PÚBLICA SUL",
    )
    assert parse_sheet(frame, "SUL", URL) == []


def test_sheet_without_header_row_is_skipped():
    assert parse_sheet(pd.DataFrame([[1, 2], [3, 4]]), "Notas", URL) == []


@pytest.mark.parametrize(
    "raw_value,expected",
    [("12", 12), (12.0, 12), ("1.234", 1234), (None, None), ("", None), (-3, None)],
)
def test_count_parsing(raw_value, expected):
    from ingestion.security import _to_count

    assert _to_count(raw_value) == expected
