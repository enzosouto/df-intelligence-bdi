"""Sonda TEMPORÁRIA: escolas do cadastro ausentes do arquivo de matrículas."""
import collections, sys
import requests
sys.path.insert(0, ".")
from ingestion.education import decode, read_table, parse_file, norm

s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 DFIntelligence/probe"
API = "https://data.se.df.gov.br/api/3/action/package_show?id="
SCH = "relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal"
ENR = "quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df"

def urls(ds):
    out = {}
    for r in s.get(API + ds, timeout=60).json()["result"]["resources"]:
        if (r.get("format") or "").upper() != "CSV" or "DICION" in norm(r.get("name") or ""): continue
        for y in range(2014, 2026):
            if str(y) in r["url"]: out[y] = r["url"]
    return out

su, eu = urls(SCH), urls(ENR)
enrolled_by_year = {}
for y in [int(a) for a in sys.argv[1:]]:
    text = decode(s.get(su[y], timeout=120).content)
    hdr, rows = read_table(text)
    ix = {c: i for i, c in enumerate(hdr)}
    _, enr = parse_file(decode(s.get(eu[y], timeout=300).content), with_enrollment=True)
    enrolled_by_year[y] = enr
    offer_cols = [c for c in ("ESCOLAS", "ESC_EI_TOTAL", "ESC_EF_TOTAL", "ESC_EM_TOTAL", "ESC_EP_TOTAL", "ESC_EJA_TOTAL", "ESC_EE_TOTAL") if c in ix]
    missing = [r for r in rows if r[ix["CO_ENTIDADE"]].isdigit() and int(r[ix["CO_ENTIDADE"]]) not in enr]
    print(f"\n=== {y}: cadastro={len(rows)} matriculas={len(enr)} ausentes={len(missing)}")
    by_net = collections.Counter(r[ix["CO_REDE"]] for r in missing)
    print("  ausentes por rede:", dict(by_net))
    offers = collections.Counter(tuple(r[ix[c]] for c in offer_cols) for r in missing)
    print("  oferta (", offer_cols, ") das ausentes:", offers.most_common(8))
    present = [r for r in rows if r[ix["CO_ENTIDADE"]].isdigit() and int(r[ix["CO_ENTIDADE"]]) in enr]
    offers_p = collections.Counter(tuple(r[ix[c]] for c in offer_cols) for r in present)
    print("  oferta das presentes (top):", offers_p.most_common(4))
    zero = sum(1 for v in enr.values() if not v.counts.get("total_published") and not v.counts.get("elementary"))
    print("  escolas no arquivo de matrículas com total 0/nulo:", zero)
    for r in missing[:6]:
        print("   ex:", r[ix["CO_ENTIDADE"]], r[ix["NO_ENTIDADE"]][:40], "rede", r[ix["CO_REDE"]], [r[ix[c]] for c in offer_cols])
    # as mesmas escolas aparecem no ano seguinte/anterior com matrícula?
    for other, enr_o in enrolled_by_year.items():
        if other == y: continue
        hits = [enr_o[int(r[ix["CO_ENTIDADE"]])] for r in missing if int(r[ix["CO_ENTIDADE"]]) in enr_o]
        tot = sum((h.counts.get("total_published") or 0) for h in hits)
        print(f"  das ausentes em {y}, {len(hits)} têm matrícula em {other}, somando {tot}")
