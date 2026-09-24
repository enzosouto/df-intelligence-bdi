"""Testes do parser do Educacenso (SEEDF).

Cabeçalhos e valores reproduzem trechos dos arquivos reais de
`data.se.df.gov.br`. Cada teste protege uma decisão que, invertida, produziria
um número errado sem levantar erro.
"""

import pytest

from ingestion.education import (
    best_coordinates,
    norm,
    parse_count,
    parse_file,
    PLACEHOLDER_MIN_SHARED,
)

# Cabeçalho de matrículas 2014–2023 (64 colunas no real; aqui só as usadas).
OLD_ENROLLMENT_HEADER = (
    "NU_ANO_CENSO,CO_REDE,NO_REDE,CO_RA,NO_RA,LOCALIZACAO,CO_ENTIDADE,NO_ENTIDADE,"
    "NU_LATITUDE,NU_LONGITUDE,IDADE,MATRÍCULA,MAT_CRECHE,MAT_PRE,ESC_EF_TOTAL,"
    "MAT_EM_TOTAL,MAT_EMI,MAT_EP_TOTAL,MAT_EJA_TOTAL,MAT_EE_CE,MAT_EE_TOTAL"
)

# 2025: linha-banner, nomes por extenso, "Código INEP", sem coordenada.
NEW_ENROLLMENT_HEADER = (
    '"EXTRAÍDO DO MICRODADOS DE MATRÍCULAS PUBLICADO",,,,,,,,,,,,,,,,,,,\n'
    "Ano do Censo,Rede,Nome Rede,RA,Nome RA,Localização,Código INEP,Nome da escola,Idade,"
    '"TOTAL GERAL (Matrículas de escolarização)",Educação infantil - Creche,'
    "Educação infantil - Pré-escola,Ensino fundamental - TOTAL,"
    '"Ensino médio - TOTAL  (EM/EMM)",Ensino Médio Integrado (EMI) - TOTAL ,'
    '"Educação Profissional - TOTAL (EMI / CT / FIC / EJAI / EAD)",'
    '"EJA - TOTAL ( EF / EM / EAD )",Educação Especial - Classe exclusiva,Educação Especial - TOTAL'
)


# --------------------------------------------------------------------------- #
# Números
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("657", 657),
        ("2,657", 2657),  # 2025: milhar com vírgula dentro de CSV com vírgula
        ("2.657", 2657),
        ("1,234,567", 1234567),
        ("", None),
        ("NUL.L", None),  # marcador de nulo de 2014
        (None, None),
    ],
)
def test_counts_accept_integers_and_well_formed_thousands(raw_value, expected):
    assert parse_count(raw_value) == expected


@pytest.mark.parametrize("ambiguous", ["12.5", "1,2", "2,65", "abc"])
def test_ambiguous_counts_fail_instead_of_guessing(ambiguous):
    """`12.0` virando `120` foi um bug real no parser da SSP. Aqui, falha alto."""
    with pytest.raises(ValueError):
        parse_count(ambiguous)


def test_column_names_normalize_across_spellings():
    assert norm("Ensino médio - TOTAL  (EM/EMM)") == "ENSINO MEDIO - TOTAL (EM EMM)"
    assert norm("Código INEP") == "CODIGO INEP"
    assert norm("AGUAS CLARAS ") == norm("Águas Claras")


# --------------------------------------------------------------------------- #
# Estrutura do arquivo
# --------------------------------------------------------------------------- #
def test_old_format_aggregates_rows_to_school():
    text = "\n".join(
        [
            OLD_ENROLLMENT_HEADER,
            "2015,1,REDE PÚBLICA FEDERAL,1,BRASILIA,Urbana,53001354,COL MILITAR DE BRASILIA,"
            "-15.780748879026,-47.892897853317,10,2,0,0,2,0,0,0,0,0,0",
            "2015,1,REDE PÚBLICA FEDERAL,1,BRASILIA,Urbana,53001354,COL MILITAR DE BRASILIA,"
            "-15.780748879026,-47.892897853317,11,17,0,0,17,0,0,0,0,0,1",
        ]
    )
    year, schools = parse_file(text, with_enrollment=True)
    school = schools[53001354]
    assert year == 2015
    assert school.counts["total_published"] == 19
    assert school.counts["elementary"] == 19
    assert school.counts["special_total"] == 1
    assert school.source_rows == 2
    assert school.ra_code == "1" and school.ra_name == "BRASILIA"
    assert school.latitude == pytest.approx(-15.780748879026)


def test_2025_banner_row_is_skipped_and_long_names_are_mapped():
    text = NEW_ENROLLMENT_HEADER + "\n" + (
        '2025,1,REDE PÚBLICA FEDERAL,1,PLANO PILOTO,Urbana,53001354,COL MILITAR DE BRASILIA,10,'
        '"2,657",0,0,"1,500",900,0,257,0,0,5'
    )
    year, schools = parse_file(text, with_enrollment=True)
    school = schools[53001354]
    assert year == 2025
    assert school.counts["total_published"] == 2657
    assert school.counts["elementary"] == 1500
    assert school.counts["high_school"] == 900
    assert school.latitude is None  # 2025 não publica coordenada


def test_missing_total_column_is_null_not_computed():
    """2024 não tem coluna de total. Ela fica nula — não é recalculada aqui."""
    header = OLD_ENROLLMENT_HEADER.replace("MATRÍCULA,", "")
    row = "2024,2,REDE SEEDF,9,CEILANDIA,Urbana,53000001,EC 01,-15.8,-48.1,7,0,0,30,0,0,0,0,0,0"
    _, schools = parse_file(header + "\n" + row, with_enrollment=True)
    assert schools[53000001].counts["total_published"] is None
    assert schools[53000001].counts["elementary"] == 30


def test_blank_stage_stays_null_instead_of_zero():
    row = "2016,4,PARTICULAR,3,TAGUATINGA,Urbana,53000002,COLEGIO X,-15.8,-48.0,5,,,,,,,,,,"
    _, schools = parse_file(OLD_ENROLLMENT_HEADER + "\n" + row, with_enrollment=True)
    assert all(value is None for value in schools[53000002].counts.values())


def test_year_comes_from_content_and_mixed_years_are_rejected():
    rows = [
        "2017,2,SEEDF,9,CEILANDIA,Urbana,53000003,EC 03,,,6,1,0,0,1,0,0,0,0,0,0",
        "2018,2,SEEDF,9,CEILANDIA,Urbana,53000004,EC 04,,,6,1,0,0,1,0,0,0,0,0,0",
    ]
    with pytest.raises(ValueError, match="único ano"):
        parse_file("\n".join([OLD_ENROLLMENT_HEADER, *rows]), with_enrollment=True)


def test_contract_change_fails_loudly():
    header = OLD_ENROLLMENT_HEADER.replace("ESC_EF_TOTAL", "ALGUMA_OUTRA")
    row = "2019,2,SEEDF,9,CEILANDIA,Urbana,53000005,EC 05,,,6,1,0,0,1,0,0,0,0,0,0"
    with pytest.raises(ValueError, match="elementary"):
        parse_file(header + "\n" + row, with_enrollment=True)


def test_2019_latitude_column_alias():
    header = OLD_ENROLLMENT_HEADER.replace("NU_LATITUDE,NU_LONGITUDE", "LATITUDE,LONGITUDE")
    row = "2019,1,FED,1,BRASILIA,Urbana,53001354,CMB,-15.7806739,-47.8920385,10,1,0,0,1,0,0,0,0,0,0"
    _, schools = parse_file(header + "\n" + row, with_enrollment=True)
    assert schools[53001354].longitude == pytest.approx(-47.8920385)


# --------------------------------------------------------------------------- #
# Localização
# --------------------------------------------------------------------------- #
def test_latest_valid_coordinate_wins_and_propagates_to_years_without_it():
    observations = [
        (53047028, 2023, -15.6397, -47.6359),
        (53047028, 2024, -15.6398, -47.6360),
        (53047028, 2025, None, None),  # 2025 não traz coordenada
    ]
    best, _ = best_coordinates(observations)
    assert best[53047028] == (-15.6398, -47.6360, 2024)


def test_coordinates_outside_df_are_ignored():
    best, _ = best_coordinates([(1, 2020, -47.9, -15.8)])  # lat/lon trocadas
    assert 1 not in best


def test_placeholder_coordinate_shared_by_many_schools_is_discarded():
    shared = [(code, 2020, -15.78, -47.93) for code in range(PLACEHOLDER_MIN_SHARED)]
    best, placeholders = best_coordinates(shared + [(999, 2020, -15.83, -48.05)])
    assert (-15.78, -47.93) in placeholders
    assert 0 not in best
    assert 999 in best
