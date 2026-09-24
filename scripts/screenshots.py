"""Captura as telas do DF Intelligence com os dados reais do banco.

Uso (com API em :8000 e frontend em :5173 já no ar):

    python scripts/screenshots.py                # grava em docs/screenshots/
    python scripts/screenshots.py --print-base64 # idem, e escreve cada imagem
                                                 # no stdout (para o log do CI)

As imagens do README vêm daqui. Não existe print montado à mão: se a tela
mudar, roda-se de novo.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

PAGES = {
    "dashboard": "/",
    "regiao-ceilandia": "/regiao/RA-IX",
    "regiao-plano-piloto": "/regiao/RA-I",
    "insights": "/insights",
    "fontes": "/fontes",
}

CHUNK = 20_000  # caracteres por linha de base64 no log


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-base64", action="store_true")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        errors: list[str] = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        for name, path in PAGES.items():
            page.goto(BASE_URL + path, wait_until="networkidle")
            # Gráficos e mapa terminam de desenhar depois das requisições.
            page.wait_for_timeout(1500)
            target = OUT_DIR / f"{name}.jpg"
            page.screenshot(path=str(target), full_page=True, type="jpeg", quality=72)
            print(f"{name}: {target.stat().st_size // 1024} KB", flush=True)
            if args.print_base64:
                encoded = base64.b64encode(target.read_bytes()).decode()
                print(f"=====BEGIN {name}.jpg=====")
                for start in range(0, len(encoded), CHUNK):
                    print(encoded[start : start + CHUNK])
                print(f"=====END {name}.jpg=====", flush=True)

        browser.close()
    if errors:
        print("ERROS NO NAVEGADOR:")
        for error in errors:
            print("  ", error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
