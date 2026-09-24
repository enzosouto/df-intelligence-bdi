"""Sonda TEMPORÁRIA de fontes candidatas (educação/mobilidade). Não faz parte do produto."""
import json, sys, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0 DFIntelligence/probe"}
s = requests.Session(); s.headers.update(UA)

def get(url, **kw):
    try:
        r = s.get(url, timeout=60, **kw)
        return r
    except Exception as e:
        print(f"  !! {url}: {type(e).__name__}: {e}"); return None

def section(t): print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100, flush=True)

def ckan(base, queries):
    section(f"CKAN {base}")
    r = get(f"{base}/api/3/action/package_list")
    if r is not None:
        print("package_list", r.status_code, r.headers.get("content-type"))
        try: print(json.dumps(r.json()["result"], ensure_ascii=False))
        except Exception: print(r.text[:500])
    for q in queries:
        r = get(f"{base}/api/3/action/package_search", params={"q": q, "rows": 40})
        if r is None: continue
        try: res = r.json()["result"]
        except Exception: print(q, r.status_code, r.text[:300]); continue
        print(f"\n--- q={q!r}: {res['count']} datasets")
        for p in res["results"]:
            print(f"* {p['name']} | {p.get('title')} | modified={p.get('metadata_modified','')[:10]}")
            for rs in p.get("resources", [])[:12]:
                print(f"    - [{rs.get('format')}] {rs.get('name')} -> {rs.get('url')}")

def arcgis(base):
    section(f"ArcGIS {base}")
    r = get(f"{base}?f=json")
    if r is None: return
    try: root = r.json()
    except Exception: print(r.status_code, r.text[:300]); return
    print("folders:", root.get("folders")); print("services:", [x["name"] for x in root.get("services", [])])
    for f in root.get("folders", []):
        rr = get(f"{base}/{f}?f=json")
        try: print(f"  {f}:", [x["name"] + ":" + x["type"] for x in rr.json().get("services", [])])
        except Exception: pass

def head(url):
    try:
        r = s.head(url, timeout=60, allow_redirects=True)
        print(f"HEAD {r.status_code} {r.headers.get('content-type')} len={r.headers.get('content-length')} {url}")
    except Exception as e: print(f"HEAD !! {url}: {e}")

ckan("https://data.se.df.gov.br", ["escola", "censo escolar", "matricula", "unidades escolares", "localizacao"])
ckan("https://dados.df.gov.br", ["escola", "onibus", "gtfs", "transporte", "parada", "metro", "linhas"])
arcgis("https://onda.ibram.df.gov.br/server/rest/services")
arcgis("https://sisdia.df.gov.br/server/rest/services")
section("INEP")
for y in (2023, 2024, 2025):
    head(f"https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{y}.zip")
