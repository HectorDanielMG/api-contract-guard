# API Contract Guard

CLI en Python para comparar contratos OpenAPI 3.x y detectar cambios que pueden romper a los clientes de una API. Genera informes para terminal, Markdown o automatizaciones.

## Vista rápida

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
contract-guard compare examples/catalog-v1.yaml examples/catalog-v2-breaking.yaml
```

## Licencia

MIT. Consulta [LICENSE](LICENSE).
