"""Ponto de entrada da API no Vercel (função serverless em /api).

O `vercel.json` reescreve `/api/*`, `/docs`, `/redoc` e `/openapi.json` para
esta função; o FastAPI recebe o caminho original e roteia normalmente.
"""

import sys
from pathlib import Path

# A função roda a partir da raiz do projeto, mas o pacote `api` só é
# importável se a raiz estiver no sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api._app import app  # noqa: E402

__all__ = ["app"]
