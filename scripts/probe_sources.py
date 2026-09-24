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

def head_rows(url, n=4):
    """Baixa só o começo do arquivo (streaming) e mostra as primeiras linhas."""
    r = s.get(url, timeout=(15, 120), stream=True)
    buf = b""
    for chunk in r.iter_content(65536):
        buf += chunk
        if buf.count(b"\n") > n + 2 or len(buf) > 400000: break
    r.close()
    text, enc = decode(buf)
    delim = max(";,\t|", key=text[:5000].count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))[:n]
    print(f"  enc={enc} delim={delim!r}")
    for row in rows: print("  >", row)

def by_year(res, fmt="CSV"):
    out = {}
    for rs in res:
        if (rs.get("format") or "").upper() != fmt: continue
        for y in range(2014, 2027):
            if str(y) in (rs.get("name") or "") + rs["url"]:
                out[y] = rs["url"]
    return dict(sorted(out.items()))

target = sys.argv[1]
if target == "escolas_all":
    res = resources("relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal")
    for y, url in by_year(res).items():
        section(f"ESCOLAS {y}")
        header, rows = show_csv(url)
        # pares (código RA, nome RA) — localizados pelo NOME da coluna
        flat = [h.strip().upper() for h in (rows[1] if "NU_ANO_CENSO" not in [h.strip() for h in header] and len(rows) > 1 else header)]
        hdr_idx = 1 if flat != [h.strip().upper() for h in header] else 0
        cols = [h.strip().upper() for h in rows[hdr_idx]]
        ra_i = next((i for i, c in enumerate(cols) if c in ("CO_RA", "RA")), None)
        nm_i = next((i for i, c in enumerate(cols) if c in ("NO_RA", "NOME RA")), None)
        rede_i = next((i for i, c in enumerate(cols) if c in ("CO_REDE", "REDE")), None)
        if ra_i is not None and nm_i is not None:
            pairs = collections.Counter((r[ra_i], r[nm_i]) for r in rows[hdr_idx + 1:] if len(r) > nm_i)
            print("  RA PAIRS:", sorted(pairs.items(), key=lambda kv: int(kv[0][0]) if kv[0][0].isdigit() else 999))
        if rede_i is not None:
            print("  REDE:", collections.Counter(r[rede_i] for r in rows[hdr_idx + 1:] if len(r) > rede_i))
        print("  linhas de dados:", len(rows) - hdr_idx - 1)
elif target == "matriculas_all":
    res = resources("quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df")
    for y, url in by_year(res).items():
        section(f"MATRICULAS {y}")
        head_rows(url)
