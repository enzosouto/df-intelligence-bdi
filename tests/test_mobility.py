"""Testes das regras de mobilidade (IDE-DF).

A geometria dos testes é construída com números reais de Brasília (graus perto
de −15,8° de latitude), para que as distâncias geodésicas sejam as do DF.
"""

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ingestion.mobility import geodesic_km, parse_year, region_of_point, split_by_region


def _two_regions():
    """Duas RAs lado a lado, divididas no meridiano −47,90."""
    west = Polygon([(-47.95, -15.85), (-47.90, -15.85), (-47.90, -15.80), (-47.95, -15.80)])
    east = Polygon([(-47.90, -15.85), (-47.85, -15.85), (-47.85, -15.80), (-47.90, -15.80)])
    geometries = [west, east]
    return ["RA-A", "RA-B"], geometries, STRtree(geometries)


def test_geodesic_length_matches_known_distance():
    """0,01° de longitude a −15,8° de latitude ≈ 1,071 km."""
    line = LineString([(-47.90, -15.80), (-47.89, -15.80)])
    assert geodesic_km(line) == pytest.approx(1.071, abs=0.002)


def test_segment_crossing_a_border_is_split_not_assigned_whole():
    """35 trechos reais cruzam divisa. Atribuí-los inteiros à RA declarada
    transferiria km de uma região para outra."""
    codes, geometries, tree = _two_regions()
    line = LineString([(-47.92, -15.82), (-47.88, -15.82)])  # metade em cada RA
    pieces = split_by_region(line, codes, geometries, tree)
    assert set(pieces) == {"RA-A", "RA-B"}
    assert pieces["RA-A"] == pytest.approx(pieces["RA-B"], rel=1e-3)
    assert sum(pieces.values()) == pytest.approx(geodesic_km(line), rel=1e-6)


def test_segment_touching_border_does_not_create_phantom_piece():
    codes, geometries, tree = _two_regions()
    line = LineString([(-47.93, -15.82), (-47.90, -15.82)])  # termina na divisa
    assert set(split_by_region(line, codes, geometries, tree)) == {"RA-A"}


def test_segment_outside_every_region_has_no_pieces():
    codes, geometries, tree = _two_regions()
    assert split_by_region(LineString([(-48.5, -16.5), (-48.4, -16.5)]), codes, geometries, tree) == {}


def test_station_is_located_by_geometry_not_by_name():
    """"ESTAÇÃO ARNIQUEIRAS" cai, pela geometria, em Águas Claras."""
    codes, geometries, tree = _two_regions()
    assert region_of_point(Point(-47.87, -15.83), codes, geometries, tree) == "RA-B"
    assert region_of_point(Point(-48.5, -16.5), codes, geometries, tree) is None


@pytest.mark.parametrize(
    "raw,expected",
    [("2012", 2012), (" 2023 ", 2023), ("", None), (None, None), ("12", None), ("2O14", None), ("s/d", None)],
)
def test_construction_year_is_parsed_strictly(raw, expected):
    assert parse_year(raw) == expected
