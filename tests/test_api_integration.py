"""Testes de integração da API contra o banco real.

Não usam mock: o objetivo é justamente provar que os dados chegaram ao
PostgreSQL, que os modelos do dbt foram materializados e que os endpoints
devolvem esses dados. São pulados automaticamente quando não há banco.

    pytest tests/test_api_integration.py
"""

from __future__ import annotations

import os

import pytest

psycopg2 = pytest.importorskip("psycopg2")
fastapi_testclient = pytest.importorskip("fastapi.testclient")


def _database_is_ready() -> bool:
    url = os.getenv("DATABASE_URL")
    if not url:
        return False
    try:
        with psycopg2.connect(url, connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("select to_regclass('marts.dim_region')")
            return cur.fetchone()[0] is not None
    except psycopg2.Error:
        return False


pytestmark = pytest.mark.skipif(
    not _database_is_ready(),
    reason="Precisa de DATABASE_URL apontando para um banco com os marts construídos.",
)


@pytest.fixture(scope="module")
def client():
    from api.main import app

    with fastapi_testclient.TestClient(app) as test_client:
        yield test_client


EXPECTED_REGIONS = 35


def test_health_check(client):
    assert client.get("/api/health-check").json() == {"status": "ok"}


def test_all_35_regions_are_served(client):
    regions = client.get("/api/regions").json()
    assert len(regions) == EXPECTED_REGIONS
    assert {r["region_id"] for r in regions} >= {"RA-I", "RA-IX", "RA-XXXV"}
    assert all(r["area_km2"] > 0 for r in regions)


def test_region_areas_sum_to_the_district(client):
    """A soma das RAs tem que reconstruir o DF (~5.760 km²)."""
    total = sum(r["area_km2"] for r in client.get("/api/regions").json())
    assert 5000 < total < 6500, f"soma implausível: {total:.0f} km²"


def test_geojson_has_geometry_for_every_region(client):
    payload = client.get("/api/regions/geojson").json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == EXPECTED_REGIONS
    assert all(f["geometry"]["type"] in {"Polygon", "MultiPolygon"} for f in payload["features"])


def test_census_population_sums_match_official_ibge_totals(client):
    """Reconciliação: valida mapeamento RA↔subdistrito, ingestão e ausência de
    duplicata de uma vez só."""
    official = {2010: 2570160, 2022: 2817381}
    points = client.get("/api/population", params={"scope": "region"}).json()

    for year, expected in official.items():
        total = sum(p["population"] for p in points if p["reference_year"] == year)
        assert total == expected, f"Censo {year}: {total} ≠ {expected}"


def test_df_population_series_preserves_gaps(client):
    """Anos de Censo e de revisão não têm estimativa. Interpolar seria inventar."""
    series = client.get("/api/population", params={"scope": "df"}).json()
    years = [p["reference_year"] for p in series]

    assert len(years) == len(set(years))
    assert years == sorted(years)
    assert max(years) - min(years) + 1 > len(years), "a série tem lacunas reais e elas foram mantidas"


def test_security_never_mixes_crime_with_police_activity(client):
    points = client.get("/api/security", params={"region_id": "RA-IX", "limit": 500}).json()
    assert points

    by_category = {p["category_code"]: p["metric_type"] for p in points}
    assert by_category.get("PRODUTIVIDADE") == "POLICE_ACTIVITY"
    assert all(by_category[code] == "CRIME" for code in ("CVLI", "CCP") if code in by_category)


def test_security_has_no_future_months(client):
    from datetime import date

    points = client.get("/api/security/summary").json()
    today = date.today()
    latest = max(p["reference_month_start"] for p in points)
    assert latest <= f"{today.year:04d}-{today.month:02d}-01"


def test_growth_is_only_published_when_comparable(client):
    """Ceilândia perdeu o Sol Nascente entre os Censos: a variação não pode ser
    publicada como se fosse perda populacional."""
    regions = client.get("/api/indicators").json()

    for region in regions:
        if not region["is_growth_comparable"]:
            assert region["population_change_pct_2010_2022"] is None, (
                f"{region['region_name']} não é comparável mas publicou variação"
            )

    ceilandia = next(r for r in regions if r["region_id"] == "RA-IX")
    assert ceilandia["is_growth_comparable"] is False
    assert ceilandia["population_change_pct_2010_2022"] is None


def test_health_facilities_are_never_dumped_into_a_single_region(client):
    """Regressão da coordenada-placeholder: 274 registros do CNES compartilham
    duas coordenadas falsas. Localizá-los inflaria uma RA e esvaziaria o resto."""
    summaries = client.get("/api/health").json()
    located = [s for s in summaries if s["region_id"]]
    assert located

    total = sum(s["facilities_total"] for s in located)
    biggest = max(s["facilities_total"] for s in located)
    assert biggest / total < 0.65, "uma única RA concentrando quase toda a rede indica erro de atribuição"

    assert all(s["facilities_private"] >= s["facilities_public"] or s["facilities_total"] < 10
               for s in located), "a rede do CNES no DF é majoritariamente privada"


def test_every_insight_carries_method_source_and_period(client):
    insights = client.get("/api/insights").json()
    assert insights

    source_ids = {s["source_id"] for s in client.get("/api/sources").json()}
    for insight in insights:
        assert insight["method"], f"{insight['insight_id']} sem metodologia"
        assert insight["source_id"] in source_ids, f"{insight['insight_id']} com fonte desconhecida"
        assert insight["period_start"], f"{insight['insight_id']} sem período"


def test_insights_never_claim_causation(client):
    """Regra editorial do projeto, verificada automaticamente."""
    forbidden = ("causou", "provocou", "por causa de", "resultou em", "devido ao aumento")
    for insight in client.get("/api/insights").json():
        text = f"{insight['title']} {insight['finding']}".lower()
        assert not any(term in text for term in forbidden), (
            f"{insight['insight_id']} afirma causalidade: {insight['finding']}"
        )


def test_coverage_exposes_the_real_gaps(client):
    coverage = client.get("/api/coverage").json()
    assert len(coverage) == EXPECTED_REGIONS

    missing_2024 = [c for c in coverage if 2024 in c["security_missing_years"]]
    assert missing_2024, "a lacuna de 2024 da SSP-DF precisa estar visível"

    without_census = [c for c in coverage if not c["population_2022_available"]]
    assert {c["region_name"] for c in without_census} == {"Arapoanga", "Água Quente"}


def test_unknown_region_returns_404(client):
    assert client.get("/api/regions/RA-INEXISTENTE").status_code == 404


def test_invalid_order_by_is_rejected(client):
    response = client.get("/api/indicators", params={"order_by": "1; drop table marts.dim_region"})
    assert response.status_code == 400
