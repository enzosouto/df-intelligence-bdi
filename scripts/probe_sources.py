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

import unicodedata
def norm(c):
    c = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode().upper()
    return " ".join(c.replace("/", " ").split())

def table(url):
    text, enc = decode(s.get(url, timeout=(15, 300)).content)
    rows = list(csv.reader(io.StringIO(text), delimiter=","))
    h = next(i for i, r in enumerate(rows[:5]) if any(norm(c) in ("NU_ANO_CENSO", "ANO DO CENSO") for c in r))
    return [norm(c) for c in rows[h]], rows[h + 1:]

def num(v):
    v = (v or "").strip()
    if v in ("", "NUL.L"): return None
    return int(v.replace(",", "").replace(".", ""))

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
elif target == "reconcile":
    res = resources("quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df")
    for y, url in by_year(res).items():
        hdr, rows = table(url)
        def col(*cands):
            for c in cands:
                if c in hdr: return hdr.index(c)
        idx = {
          "total": col("MATRICULA", "TOTAL GERAL (MATRICULAS DE ESCOLARIZACAO)"),
          "ei": col("MAT_EI_TOTAL", "EDUCACAO INFANTIL - TOTAL"),
          "creche": col("MAT_CRECHE", "EDUCACAO INFANTIL - CRECHE"),
          "pre": col("MAT_PRE", "EDUCACAO INFANTIL - PRE-ESCOLA"),
          "ef": col("ESC_EF_TOTAL", "MAT_EF_TOTAL", "ENSINO FUNDAMENTAL - TOTAL"),
          "em": col("MAT_EM_TOTAL", "ENSINO MEDIO - TOTAL (EM EMM)", "ENSINO MEDIO - TOTAL"),
          "ep": col("MAT_EP_TOTAL", "EDUCACAO PROFISSIONAL - TOTAL (EMI CT FIC EJAI EAD)"),
          "emi": col("MAT_EMI", "ENSINO MEDIO INTEGRADO (EMI) - TOTAL"),
          "eja": col("MAT_EJA_TOTAL", "EJA - TOTAL ( EF EM EAD )"),
          "ee": col("MAT_EE_TOTAL", "EDUCACAO ESPECIAL - TOTAL"),
          "ee_ce": col("MAT_EE_CE", "EDUCACAO ESPECIAL - CLASSE EXCLUSIVA"),
          "school": col("CO_ENTIDADE", "CODIGO INEP"),
        }
        tot = collections.Counter(); blanks = collections.Counter()
        for r in rows:
            for k, i in idx.items():
                if i is None or k == "school": continue
                v = num(r[i]) if i < len(r) else None
                if v is None: blanks[k] += 1
                else: tot[k] += v
        schools = len({r[idx["school"]] for r in rows})
        print(f"{y} rows={len(rows)} schools={schools} missing_cols={[k for k,i in idx.items() if i is None]}")
        print(f"   sums={dict(tot)}")
        print(f"   blanks={dict(blanks)}")
        for label, parts in {"ei+ef+em+ep+eja": ["ei","ef","em","ep","eja"], "ei+ef+em+emi+eja": ["ei","ef","em","emi","eja"],
                             "ei+ef+em+ep+eja+ee_ce": ["ei","ef","em","ep","eja","ee_ce"], "creche+pre+ef+em+ep+eja": ["creche","pre","ef","em","ep","eja"]}.items():
            print(f"   {label:28} = {sum(tot[p] for p in parts):>9}  vs total {tot['total']:>9}  diff={sum(tot[p] for p in parts)-tot['total']}")
elif target == "ra3435":
    res = resources("relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal")
    for y, url in by_year(res).items():
        if y < 2023: continue
        hdr, rows = table(url)
        def col(*c): return next((hdr.index(x) for x in c if x in hdr), None)
        ra, nm, sc, en = col("CO_RA", "RA"), col("NO_RA", "NOME RA"), col("CO_ENTIDADE"), col("NO_ENTIDADE", "NOME DA ESCOLA")
        la, lo, ba = col("NU_LATITUDE"), col("NU_LONGITUDE"), col("NO_BAIRRO")
        print(f"\n## {y} cols ok: ra={ra} nm={nm} sc={sc} en={en} lat={la}")
        for r in rows:
            if r[ra].strip() in ("34", "35", "6", "15") and (r[ra].strip() in ("34","35") or any(k in (r[en] or "").upper() for k in ("ARAPOANGA","AGUA QUENTE","ÁGUA QUENTE"))):
                print("  ", r[ra], r[nm], r[sc], r[en], r[la] if la is not None else "", r[lo] if lo is not None else "", r[ba] if ba is not None else "")
elif target == "matriculas_all":
    res = resources("quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df")
    for y, url in by_year(res).items():
        section(f"MATRICULAS {y}")
        head_rows(url)
