"""Sonda TEMPORÁRIA de fontes candidatas (educação). Não faz parte do produto."""
import csv, io, json, sys, collections, requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0 DFIntelligence/probe"}
s = requests.Session(); s.headers.update(UA)
BASE = "https://data.se.df.gov.br"

def section(t): print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100, flush=True)

def resources(pkg):
    r = s.get(f"{BASE}/api/3/action/package_show", params={"id": pkg}, timeout=(15, 60)).json()["result"]
    print(f"# {r['title']} | license={r.get('license_title')} | org={r.get('organization',{}).get('title')}")
    print("  notes:", (r.get("notes") or "")[:600].replace("\n", " "))
    for rs in r["resources"]:
        print(f"  - [{rs.get('format')}] {rs.get('name')} size={rs.get('size')} -> {rs['url']}")
    return r["resources"]

def fetch(url):
    r = s.get(url, timeout=(15, 120)); print(f"  GET {r.status_code} {r.headers.get('content-type')} {len(r.content)} bytes")
    return r.content

def decode(raw):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try: return raw.decode(enc), enc
        except UnicodeDecodeError: pass

def show_csv(url, full=False):
    raw = fetch(url); text, enc = decode(raw)
    sample = text[:5000]
    delim = max(";,\t|", key=sample.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    print(f"  encoding={enc} delim={delim!r} rows={len(rows)}")
    header = rows[0]; print("  HEADER:", header)
    for row in rows[1:4]: print("  ROW:", row)
    if full:
        for i, col in enumerate(header):
            vals = collections.Counter(r[i] for r in rows[1:] if len(r) > i)
            print(f"   col {col!r}: {len(vals)} distintos; top={vals.most_common(8)}")
    return header, rows

def show_geojson(url):
    raw = fetch(url); d = json.loads(decode(raw)[0])
    feats = d.get("features", [])
    print(f"  features={len(feats)} crs={d.get('crs')}")
    for f in feats[:2]: print("  FEATURE:", json.dumps(f, ensure_ascii=False)[:1500])
    nogeo = sum(1 for f in feats if not f.get("geometry"))
    print(f"  sem geometria: {nogeo}")

def pick(res, *needles, fmt=None):
    for rs in res:
        name = (rs.get("name") or "") + " " + rs["url"]
        if all(n.lower() in name.lower() for n in needles) and (fmt is None or (rs.get("format") or "").upper() == fmt):
            return rs["url"]

target = sys.argv[1]
if target == "escolas":
    section("UNIDADES ESCOLARES")
    res = resources("relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal")
    show_csv(pick(res, "dicionario"), full=False)
    show_csv(pick(res, "2025", fmt="CSV"), full=True)
    show_csv(pick(res, "2014", fmt="CSV"))
elif target == "matriculas":
    section("MATRÍCULAS")
    res = resources("quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df")
    show_csv(pick(res, "dicionario"))
    show_csv(pick(res, "2025", fmt="CSV"), full=True)
    g = pick(res, "2025", fmt="GEOJSON")
    if g: show_geojson(g)
elif target == "docentes":
    section("DOCENTES + INFRA")
    res = resources("total-de-docentes-abrangendo-todas-as-redes-de-ensino-do-df")
    show_csv(pick(res, "2025", fmt="CSV"))
    res = resources("dados-de-infraestrutura-abrangendo-todas-as-redes-de-ensino-df")
    show_csv(pick(res, "2025", fmt="CSV"))
