"""Camada de ingestão do DF Intelligence.

Ordem de execução importa: `regions` estabelece as chaves (`ra_code` e
`subdistrict_id`) das quais `population`, `health` e `weather` dependem.
"""

__all__ = ["regions", "population", "security", "health", "weather"]
