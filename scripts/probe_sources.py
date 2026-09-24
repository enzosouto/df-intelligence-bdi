"""Sonda TEMPORÁRIA: qualidade da malha cicloviária e estações (IDE-DF)."""
import collections, json, sys
import requests
from pyproj import Geod
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
sys.path.insert(0, ".")
from ingestion.education import norm

GEOD = Geod(ellps="WGS84")
s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 DFIntelligence/probe"
BASE = "https://www.geoservicos.ide.df.gov.br/arcgis/rest/services/Publico/IDEDF/FeatureServer"
RA_URL = ("https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/"
          "MapServer/0/query?where=1%3D1&outFields=ra_codigo,ra_nome&outSR=4326&f=geojson")

def all_features(layer):
    feats, offset = [], 0
    while True:
        r = s.get(f"{BASE}/{layer}/query", params={"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
                  "orderByFields": "objectid", "resultOffset": offset, "resultRecordCount": 1000}, timeout=120)
        batch = r.json().get("features", [])
        feats += batch
        print(f"  layer {layer} offset {offset}: +{len(batch)} (exceeded={r.json().get('exceededTransferLimit') or r.json().get('properties')})")
        if len(batch) < 1000: return feats
        offset += 1000

ras = s.get(RA_URL, timeout=120).json()["features"]
print("RAs:", len(ras), "exemplo props:", ras[0]["properties"])
geoms = [shape(f["geometry"]) for f in ras]
names = [norm(f["properties"]["ra_nome"]) for f in ras]
tree = STRtree(geoms)

bikes = all_features(218)
ids = [f["properties"]["objectid"] for f in bikes]
print("\nciclovia: trechos", len(bikes), "ids únicos", len(set(ids)))
declared_total = sum(f["properties"]["cvia_km"] or 0 for f in bikes)
geo_total, clipped_total = 0.0, 0.0
agree = disagree = crossing = no_geom = 0
by_ra_declared = collections.Counter(); by_ra_geo = collections.Counter()
ratio_bad = []
years = collections.Counter(); typ = collections.Counter(); tipo_via = collections.Counter()
declared_names = collections.Counter()
for f in bikes:
    p = f["properties"]
    years[p["cvia_ano_construcao"]] += 1; typ[p["cvia_tipologia"]] += 1; tipo_via[p["cvia_tipo_via"]] += 1
    declared_names[norm(p["cvia_ra"] or "")] += 1
    if not f.get("geometry"): no_geom += 1; continue
    g = shape(f["geometry"])
    length = GEOD.geometry_length(g) / 1000
    geo_total += length
    if p["cvia_km"] and length and not (0.8 <= length / p["cvia_km"] <= 1.25): ratio_bad.append((p["objectid"], p["cvia_km"], round(length, 3)))
    pieces = {}
    for i in tree.query(g):
        inter = g.intersection(geoms[i])
        if not inter.is_empty:
            km = GEOD.geometry_length(inter) / 1000
            if km > 0.001: pieces[names[i]] = km
    clipped_total += sum(pieces.values())
    if len(pieces) > 1: crossing += 1
    for n, km in pieces.items(): by_ra_geo[n] += km
    main = max(pieces, key=pieces.get) if pieces else None
    by_ra_declared[norm(p["cvia_ra"] or "")] += p["cvia_km"] or 0
    if main == norm(p["cvia_ra"] or ""): agree += 1
    else: disagree += 1
print(f"km declarado {declared_total:.1f} | km geodésico {geo_total:.1f} | km recortado nas RAs {clipped_total:.1f} | sem geometria {no_geom}")
print(f"RA declarada = RA majoritária da geometria: {agree} concordam, {disagree} discordam | trechos que cruzam divisa: {crossing}")
print(f"trechos com km declarado fora de [0,8x ; 1,25x] do geométrico: {len(ratio_bad)} ex {ratio_bad[:8]}")
print("anos:", sorted(years.items(), key=lambda kv: str(kv[0])))
print("tipologia:", typ.most_common()); print("tipo_via:", tipo_via.most_common())
print("nomes de RA declarados não reconhecidos:", {k: v for k, v in declared_names.items() if k not in names})
print("\nkm por RA  declarado vs geométrico (top 40):")
for n in sorted(set(by_ra_declared) | set(by_ra_geo), key=lambda k: -by_ra_geo.get(k, 0))[:40]:
    print(f"  {n:28} decl {by_ra_declared.get(n, 0):8.1f}  geo {by_ra_geo.get(n, 0):8.1f}")

for layer in (140, 127):
    feats = all_features(layer)
    print(f"\nlayer {layer}: {len(feats)} pontos")
    c = collections.Counter()
    for f in feats:
        p = f["properties"]; g = shape(f["geometry"])
        ra = next((names[i] for i in tree.query(g) if geoms[i].covers(g)), "FORA")
        key = tuple(v for k, v in p.items() if k.endswith(("situacao", "tipo")))
        c[key] += 1
        print("  ", ra, "|", json.dumps({k: v for k, v in p.items() if k != "objectid"}, ensure_ascii=False))
    print("  situação/tipo:", c.most_common())
