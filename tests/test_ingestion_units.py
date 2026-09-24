"""Testes das regras de tratamento das demais fontes.

Cada um cobre uma decisão que, se invertida, produziria um número errado no
dashboard sem levantar nenhum erro.
"""

import pytest
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ingestion.health import _assign_region, _placeholder_coordinates
from ingestion.population import _parse_int, _total_series
from ingestion.regions import _geodesic_area_km2, _neighbors
from ingestion.weather import _grid_cells


# --------------------------------------------------------------------------- #
# População
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("198697", 198697),
        ("2.817.381", 2817381),
        ("...", None),  # SIDRA: valor não disponível
        ("-", None),  # SIDRA: valor zero por arredondamento
        ("X", None),  # SIDRA: valor sob sigilo
        (None, None),
    ],
)
def test_sidra_missing_markers_become_null_not_zero(raw_value, expected):
    """`...` significa "não publicado". Virar 0 inventaria uma RA despovoada."""
    assert _parse_int(raw_value) == expected


def test_total_series_only_reads_the_total_category():
    """Sem esse filtro, categorias urbana/rural seriam somadas ao total."""
    payload = [
        {
            "id": "93",
            "resultados": [
                {
                    "classificacoes": [{"id": "1", "categoria": {"6795": "Total"}}],
                    "series": [{"localidade": {"id": "53001080506"}, "serie": {"2022": "198697"}}],
                },
                {
                    "classificacoes": [{"id": "1", "categoria": {"6796": "Urbana"}}],
                    "series": [{"localidade": {"id": "53001080506"}, "serie": {"2022": "190000"}}],
                },
            ],
        }
    ]
    assert _total_series(payload) == {"53001080506": "198697"}


# --------------------------------------------------------------------------- #
# Regiões
# --------------------------------------------------------------------------- #
def test_geodesic_area_matches_known_square():
    """Um grau de latitude ~111 km; 0,1° x 0,1° perto de Brasília ~119 km²."""
    square = Polygon([(-47.9, -15.8), (-47.8, -15.8), (-47.8, -15.7), (-47.9, -15.7)])
    area = _geodesic_area_km2(square)
    assert 115 < area < 125, f"área implausível: {area}"


def test_neighbors_are_symmetric_and_exclude_point_contact():
    """Dois polígonos que só se tocam num vértice não são vizinhos."""
    left = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    right = Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])
    corner = Polygon([(2, 1), (3, 1), (3, 2), (2, 2)])

    result = _neighbors({"A": left, "B": right, "C": corner})

    assert [n["ra_code"] for n in result["A"]] == ["B"]
    assert "A" in [n["ra_code"] for n in result["B"]], "vizinhança é simétrica"
    assert result["C"] == [] or "B" not in [n["ra_code"] for n in result["C"]]


# --------------------------------------------------------------------------- #
# Saúde
# --------------------------------------------------------------------------- #
def test_placeholder_coordinates_are_detected_from_the_data():
    facilities = [
        {"latitude_estabelecimento_decimo_grau": -15.78, "longitude_estabelecimento_decimo_grau": -47.93}
        for _ in range(25)
    ] + [
        {"latitude_estabelecimento_decimo_grau": -15.84, "longitude_estabelecimento_decimo_grau": -48.10},
        {"latitude_estabelecimento_decimo_grau": None, "longitude_estabelecimento_decimo_grau": None},
    ]
    assert _placeholder_coordinates(facilities) == {(-15.78, -47.93)}


def test_placeholder_coordinate_is_treated_as_missing_not_located():
    """Empilhar 232 registros na RA onde a coordenada falsa cai inflaria a rede
    daquela região e esvaziaria todas as outras."""
    region = Polygon([(-48.0, -16.0), (-47.5, -16.0), (-47.5, -15.5), (-48.0, -15.5)])
    codes, geometries = ["RA-I"], [region]
    tree = STRtree(geometries)
    placeholders = {(-15.78, -47.93)}

    assert _assign_region(-15.78, -47.93, codes, geometries, tree, placeholders) == (None, "MISSING")
    assert _assign_region(-15.80, -47.90, codes, geometries, tree, placeholders) == ("RA-I", "OK")
    assert _assign_region(None, None, codes, geometries, tree, placeholders) == (None, "MISSING")
    assert _assign_region(-23.5, -46.6, codes, geometries, tree, placeholders) == (None, "OUTSIDE_DF")


# --------------------------------------------------------------------------- #
# Clima
# --------------------------------------------------------------------------- #
def test_regions_in_the_same_grid_cell_share_one_request():
    """A grade do ERA5 é menor que o DF. Consultar 35 pontos distintos gastaria
    cota para receber a mesma série várias vezes."""
    regions = [
        ("RA-I", -15.78, -47.93),
        ("RA-II", -15.781, -47.932),  # mesma célula de 0,1°
        ("RA-III", -15.99, -48.13),  # célula diferente
    ]
    cells = _grid_cells(regions)

    assert len(cells) == 2
    shared = next(codes for codes in cells.values() if len(codes) > 1)
    assert sorted(shared) == ["RA-I", "RA-II"]
