"""Sonda TEMPORÁRIA de fontes de mobilidade. Não faz parte do produto."""
import json, re, sys, requests
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0 DFIntelligence/probe"

def get(url, **kw):
    try:
        r = s.get(url, timeout=(15, 60), **kw)
        print(f"GET {r.status_code} {r.headers.get('content-type')} {len(r.content)}B {url[:160]}", flush=True)
        return r
    except Exception as e:
        print(f"GET !! {url[:160]} {type(e).__name__}: {str(e)[:200]}", flush=True)

def section(t): print("\n" + "=" * 90 + f"\n{t}\n" + "=" * 90, flush=True)

t = sys.argv[1]
if t == "semob":
    section("SEMOB GeoServer WFS")
    base = "https://geoserver.semob.df.gov.br/geoserver/semob/ows"
    r = get(base, params={"service": "WFS", "version": "1.1.0", "request": "GetCapabilities"})
    if r is not None and r.ok:
        names = re.findall(r"<Name>([^<]+)</Name>", r.text)
        titles = re.findall(r"<Title>([^<]+)</Title>", r.text)
        print("layers:", names[:80]); print("titles:", titles[:80])
        for name in names:
            if any(k in name.lower() for k in ("parada", "linha", "terminal", "metro", "estac", "ciclo", "brt")):
                rr = get(base, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": name,
                                       "outputFormat": "application/json", "maxFeatures": 2})
                if rr is not None and rr.ok:
                    try:
                        d = rr.json(); print(f"  {name}: totalFeatures={d.get('totalFeatures')} crs={d.get('crs')}")
                        for f in d.get("features", [])[:2]: print("   ", json.dumps(f, ensure_ascii=False)[:700])
                    except Exception as e: print("  não-JSON:", rr.text[:300])
    for u in ("https://www.semob.df.gov.br/pontos-de-parada", "https://www.semob.df.gov.br/plano-de-dados-abertos-pda/"):
        r = get(u)
        if r is not None and r.ok:
            links = sorted(set(re.findall(r'href="([^"]+)"', r.text)))
            print("  links úteis:", [l for l in links if any(k in l.lower() for k in ("gtfs", ".zip", ".csv", "geoserver", "geomobi", "dados", "json", "wfs"))][:40])
elif t == "idedf":
    section("IDE-DF")
    for u in ("https://www.geoservicos.ide.df.gov.br/arcgis/rest/services?f=json",
              "https://www.geoservicos.ide.df.gov.br/arcgis/rest/services/Publico/IDEDF/FeatureServer?f=json"):
        r = get(u)
        if r is not None and r.ok:
            try:
                d = r.json()
                print("  folders:", d.get("folders")); print("  services:", [x.get("name") for x in d.get("services", [])][:60])
                print("  layers:", [(l["id"], l["name"]) for l in d.get("layers", [])][:400])
            except Exception: print(r.text[:300])
elif t == "detran":
    section("DETRAN-DF")
    for u in ("https://www.dados.df.gov.br/dataset/acidentes-de-transito-nas-vias-urbanas-do-distrito-federal-nos-ultimos-10-anos-com-vitimas-fatais",
              "https://www.dados.df.gov.br/organization/departamento-de-transito-do-distrito-federal-detran-df",
              "https://www.detran.df.gov.br/dados-anuais/",
              "https://www.detran.df.gov.br/plano-de-dados-abertos/"):
        r = get(u)
        if r is not None and r.ok:
            links = sorted(set(re.findall(r'href="([^"]+)"', r.text)))
            print("  links:", [l for l in links if any(k in l.lower() for k in (".csv", ".xls", ".zip", "download", "resource", "dataset/", ".json", "acident", "sinistr"))][:60])
            print("  trecho:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:600])
