"""Ponto de entrada da API para uvicorn (Docker, CI, Render, testes).

    uvicorn api.main:app

O código vive em `_app.py`, `_db.py` e `_schemas.py`. O sublinhado não é
estilo: no Vercel, todo `.py` dentro de `api/` vira uma função serverless, e os
arquivos que começam com `_` são a exceção documentada. Assim só `index.py`
(e este arquivo) viram funções, e os módulos auxiliares são só importados.
"""

from api._app import app

__all__ = ["app"]
