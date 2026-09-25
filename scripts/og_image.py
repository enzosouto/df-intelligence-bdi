"""Gera a miniatura de compartilhamento (frontend/public/og.png, 1200x630).

É a imagem que WhatsApp, LinkedIn, X e iMessage mostram quando alguém cola o
link do site. A malha é a cobertura REAL das 35 RAs, lida da API — seis
células por região, cheia quando a fonte publica, vazada em magenta quando
não publica. Nenhum número vai escrito na imagem: ela não é regerada a cada
carga e um número parado envelheceria errado.

Uso (precisa de Playwright com Chromium):
    python scripts/og_image.py [URL_DA_API]
"""

from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

API = sys.argv[1] if len(sys.argv) > 1 else "https://df-intelligence-api.onrender.com"
OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "og.png"

# Mesma ordem de células da Malha.vue (2 colunas x 3 linhas).
DOMAINS = [
    lambda r: r["population_2022_available"],
    lambda r: r["security_years_with_data"] > 0,
    lambda r: r["health_facilities"] > 0,
    lambda r: r["education_schools"] > 0,
    lambda r: r["mobility_bikeway_km"] > 0,
    lambda r: r["weather_days"] > 0,
]
CELL, GAP, PITCH = 11, 3, 31

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@100..125,400..700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1200px;height:630px;background:#060010;overflow:hidden}}
.card{{position:relative;width:1200px;height:630px;padding:64px 72px;color:#fff;
  background-image:linear-gradient(rgba(247,242,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(247,242,255,.045) 1px,transparent 1px);
  background-size:44px 44px;background-position:-1px -1px}}
.card::after{{content:"";position:absolute;inset:0;background:radial-gradient(900px 480px at 88% 0%,rgba(255,0,106,.16),transparent 60%);pointer-events:none}}
.top{{display:flex;align-items:center;justify-content:space-between}}
.brand{{display:flex;align-items:center;gap:18px}}
.df{{font:700 40px/1 Archivo;font-stretch:118%;letter-spacing:-.01em}}
.bar{{width:2px;height:30px;background:#2C1549}}
.intel{{font:500 17px/1 "IBM Plex Mono";letter-spacing:.32em;color:#DCD5EC}}
.meta{{font:500 15px/1 "IBM Plex Mono";letter-spacing:.24em;color:#BFB4D6}}
h1{{margin-top:62px;font:700 104px/.9 Archivo;font-stretch:118%;letter-spacing:-.02em;text-transform:uppercase}}
h1 span{{color:#FF006A;display:block}}
.foot{{position:absolute;left:72px;right:72px;bottom:56px}}
.legend{{margin-top:18px;display:flex;justify-content:space-between;font:500 15px/1.3 "IBM Plex Mono";letter-spacing:.14em;color:#BFB4D6;text-transform:uppercase}}
.legend b{{color:#fff;font-weight:500}}
.url{{color:#FF006A}}
</style></head><body><div class="card">
<div class="top"><div class="brand"><span class="df">DF</span><span class="bar"></span><span class="intel">INTELLIGENCE</span></div>
<div class="meta">35 RA · 6 DOMÍNIOS · 10 FONTES</div></div>
<h1>Brasília<span>através dos dados</span></h1>
<div class="foot">
{malha}
<div class="legend"><span>Dados públicos por <b>Região Administrativa</b></span><span class="url">df-intelligence-bdi.vercel.app</span></div>
</div></div></body></html>"""


def malha(coverage: list[dict]) -> str:
    rects = []
    for index, region in enumerate(coverage):
        for position, has in enumerate(DOMAINS):
            x = index * PITCH + (position % 2) * (CELL + GAP)
            y = (position // 2) * (CELL + GAP)
            if has(region):
                rects.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="#FFFFFF" fill-opacity="0.88"/>')
            else:
                rects.append(
                    f'<rect x="{x + 0.75}" y="{y + 0.75}" width="{CELL - 1.5}" height="{CELL - 1.5}" '
                    'fill="none" stroke="#FF006A" stroke-width="1.5"/>'
                )
    width = len(coverage) * PITCH - (PITCH - 2 * CELL - GAP)
    height = 3 * CELL + 2 * GAP
    return f'<svg width="1056" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMid meet">{"".join(rects)}</svg>'


def main() -> None:
    with urllib.request.urlopen(f"{API}/api/coverage", timeout=120) as response:
        coverage = json.load(response)
    html = TEMPLATE.format(malha=malha(coverage))
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / "card.html"
        page_path.write_text(html, encoding="utf-8")
        raw = Path(tmp) / "og.png"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(page_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(500)
            page.screenshot(path=str(raw), type="png")
            browser.close()
        # Paleta de 64 cores: arte chapada, ~40 KB (o WhatsApp ignora imagem pesada).
        Image.open(raw).convert("P", palette=Image.ADAPTIVE, colors=64).save(OUT, optimize=True)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
