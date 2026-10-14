# API Contract Guard

**Detecta cambios que pueden romper a los clientes de una API antes de publicar una nueva especificación.** API Contract Guard compara dos contratos OpenAPI 3.x, explica los hallazgos y puede detener una integración continua cuando encuentra incompatibilidades.

Proyecto de ingeniería de software enfocado en evolución segura de APIs. Acepta contratos JSON y YAML, resuelve referencias locales y produce informes para personas y herramientas.

## Funciones

- Compara rutas y operaciones HTTP.
- Detecta rutas y operaciones eliminadas, parámetros removidos y nuevos parámetros obligatorios.
- Revisa cuerpos de solicitud obligatorios, formatos aceptados y respuestas eliminadas.
- Analiza esquemas con referencias locales `#/components/...`.
- Detecta cambios de tipo, propiedades eliminadas, campos obligatorios nuevos, enumeraciones reducidas y restricciones más estrictas.
- Marca adiciones compatibles, como rutas, respuestas, formatos o propiedades opcionales.
- Recomienda una versión `major`, `minor` o `patch` según los hallazgos detectados.
- Genera salida legible, Markdown y JSON.
- Puede devolver código de salida distinto de cero ante cambios incompatibles para bloquear un pipeline.
- Incluye ejemplos de evolución compatible e incompatible y un flujo de GitHub Actions.

## Inicio rápido

Requiere Python 3.10 o superior.

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -e .
```

Compara las especificaciones de ejemplo:

```bash
contract-guard compare examples/catalog-v1.yaml examples/catalog-v2-compatible.yaml
```

El ejemplo compatible agrega una ruta y una propiedad opcional. Para ver cambios incompatibles:

```bash
contract-guard compare examples/catalog-v1.yaml examples/catalog-v2-breaking.yaml
```

También puedes ejecutar el módulo sin instalar el comando:

```bash
python -m contract_guard compare examples/catalog-v1.yaml examples/catalog-v2-breaking.yaml
```

## Uso en un proyecto

Compara la versión de producción de tu contrato con la propuesta:

```bash
contract-guard compare api/openapi.yaml api/openapi-proposed.yaml \
  --format markdown \
  --output reports/compatibility.md \
  --fail-on-breaking
```

Si el comando detecta incompatibilidades, `--fail-on-breaking` devuelve el código `1`. Sin esa opción, el análisis termina con código `0` aunque haya hallazgos incompatibles. Los errores al leer el archivo o interpretar la especificación devuelven `2`.

### Códigos de salida

| Código | Significado |
| --- | --- |
| `0` | El análisis terminó correctamente. Puede incluir incompatibilidades si no se indicó `--fail-on-breaking`. |
| `1` | Se encontraron incompatibilidades y se indicó `--fail-on-breaking`. |
| `2` | No se pudo leer una especificación o guardar el informe. |

### Formatos de informe

```bash
# Resumen en terminal (por defecto)
contract-guard compare anterior.yaml nueva.yaml

# Informe para adjuntar a una revisión
contract-guard compare anterior.yaml nueva.yaml --format markdown --output informe.md

# Salida estructurada para otra herramienta
contract-guard compare anterior.yaml nueva.yaml --format json --output informe.json
```

## Reglas de compatibilidad

El analizador marca como incompatibles, entre otros cambios:

| Cambio | Motivo |
| --- | --- |
| Eliminar una ruta u operación | Un cliente que la usa ya no encuentra el recurso o método. |
| Eliminar un parámetro o volverlo obligatorio | Puede invalidar solicitudes ya emitidas por clientes existentes. |
| Volver obligatorio el cuerpo de solicitud o una propiedad | Una solicitud válida antes puede dejar de serlo. |
| Eliminar una respuesta, formato o propiedad | Un cliente puede depender de esa salida. |
| Cambiar el tipo de un campo o reducir una enumeración | Los datos aceptados o devueltos dejan de cumplir el contrato anterior. |
| Endurecer restricciones numéricas o de longitud | Entradas válidas con las reglas anteriores pueden ser rechazadas. |

Las adiciones de rutas, operaciones, respuestas, formatos y propiedades opcionales se reportan como compatibles. La versión sugerida sigue una regla simple: cambios incompatibles recomiendan `major`; si solo hay adiciones compatibles, `minor`; si no hay cambios cubiertos, `patch`.

## Integración continua

El flujo incluido en `.github/workflows/contract-check.yml` compara `api/openapi.yaml` con la versión de la rama base en cada pull request o actualización de `main`. Si detecta un cambio incompatible, el trabajo falla y conserva el informe en el resumen de la ejecución.

Para usarlo en otro repositorio, copia el flujo, ajusta la ruta del contrato en el archivo YAML y adapta el comando a tu estructura. Contract Guard se instala como dependencia del proyecto; no requiere publicar una acción ni conceder permisos de escritura al workflow.

## Arquitectura

```text
Especificación anterior ─┐
                         ├─> carga JSON/YAML ─> comparación de reglas ─> terminal / Markdown / JSON
Especificación nueva ────┘
```

| Módulo | Responsabilidad |
| --- | --- |
| `contract_guard/analyzer.py` | Lectura, referencias locales, comparación de rutas, parámetros y esquemas. |
| `contract_guard/render.py` | Presentación de informes de terminal y Markdown. |
| `contract_guard/cli.py` | Argumentos, escritura de resultados y códigos de salida. |
| `api/openapi.yaml` | Contrato de ejemplo usado por la integración continua. |
| `examples/` | Casos de evolución compatible e incompatible. |

## Límites conocidos

- Es un analizador estático de reglas cubiertas, no un validador completo de OpenAPI ni una prueba de comportamiento en tiempo de ejecución.
- Expande referencias locales; no descarga ni analiza referencias externas.
- No modela todas las interacciones de `allOf`, `oneOf`, `anyOf`, seguridad, callbacks ni enlaces.
- La recomendación semántica depende de las reglas implementadas y debe revisarse antes de publicar una versión.
- Un informe sin hallazgos significa que no se detectó un cambio en las reglas cubiertas; no garantiza compatibilidad para todos los clientes.

## Desarrollo

```bash
python -m contract_guard --help
python -m contract_guard compare --help
```

Dependencia de ejecución: [PyYAML](https://pyyaml.org/). El código de análisis y la interfaz usan la biblioteca estándar de Python.

## Licencia

MIT. Consulta [LICENSE](LICENSE).
