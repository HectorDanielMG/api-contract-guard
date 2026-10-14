"""Comparación conservadora de cambios entre contratos OpenAPI 3.x."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


class ContractError(ValueError):
    """La especificación no se pudo leer o no tiene una estructura OpenAPI válida."""


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    location: str
    message: str
    before: Any = None
    after: Any = None


@dataclass(frozen=True)
class Report:
    before: str
    after: str
    breaking: int
    compatible: int
    recommendation: str
    findings: tuple[Finding, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["findings"] = [asdict(item) for item in self.findings]
        return result


def load_spec(path: str | Path) -> dict[str, Any]:
    """Carga JSON o YAML y valida los campos estructurales básicos."""
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8-sig") as stream:
            spec = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"No se pudo leer {source}: {exc}") from exc

    if not isinstance(spec, dict):
        raise ContractError(f"{source} debe contener un objeto OpenAPI.")
    version = str(spec.get("openapi", ""))
    if not version.startswith("3."):
        raise ContractError(f"{source} debe declarar una versión OpenAPI 3.x.")
    if not isinstance(spec.get("paths"), dict):
        raise ContractError(f"{source} debe incluir un objeto 'paths'.")
    return spec


def _resolve(value: Any, spec: dict[str, Any], stack: frozenset[str] = frozenset()) -> Any:
    """Expande referencias locales; deja intactas las referencias circulares."""
    if isinstance(value, list):
        return [_resolve(item, spec, stack) for item in value]
    if not isinstance(value, dict):
        return value

    ref = value.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        if ref in stack:
            return {"$ref": ref}
        target: Any = spec
        try:
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError) as exc:
            raise ContractError(f"Referencia local no encontrada: {ref}") from exc
        expanded = _resolve(target, spec, stack | {ref})
        siblings = {key: item for key, item in value.items() if key != "$ref"}
        if siblings and isinstance(expanded, dict):
            expanded = {**expanded, **_resolve(siblings, spec, stack)}
        return expanded

    return {key: _resolve(item, spec, stack) for key, item in value.items()}


def _add(
    findings: list[Finding], severity: str, rule: str, location: str,
    message: str, before: Any = None, after: Any = None,
) -> None:
    findings.append(Finding(severity, rule, location, message, before, after))


def _compare_schema(
    old: Any, new: Any, location: str, findings: list[Finding], *, direction: str,
) -> None:
    if not isinstance(old, dict) or not isinstance(new, dict):
        return

    old_type, new_type = old.get("type"), new.get("type")
    if old_type != new_type and old_type is not None and new_type is not None:
        _add(findings, "breaking", "schema.type_changed", location,
             f"El tipo del esquema cambió de {old_type} a {new_type}.", old_type, new_type)

    old_enum, new_enum = old.get("enum"), new.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        removed = [item for item in old_enum if item not in new_enum]
        if removed:
            _add(findings, "breaking", "schema.enum_values_removed", location,
                 "La nueva versión acepta menos valores que la anterior.", old_enum, new_enum)

    for bound in ("minimum", "minLength", "minItems"):
        old_bound, new_bound = old.get(bound), new.get(bound)
        if isinstance(old_bound, (int, float)) and isinstance(new_bound, (int, float)) and new_bound > old_bound:
            _add(findings, "breaking", "schema.constraint_tightened", f"{location}.{bound}",
                 f"La restricción {bound} ahora es más estricta.", old_bound, new_bound)
    for bound in ("maximum", "maxLength", "maxItems"):
        old_bound, new_bound = old.get(bound), new.get(bound)
        if isinstance(old_bound, (int, float)) and isinstance(new_bound, (int, float)) and new_bound < old_bound:
            _add(findings, "breaking", "schema.constraint_tightened", f"{location}.{bound}",
                 f"La restricción {bound} ahora es más estricta.", old_bound, new_bound)

    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))
    added_required = sorted(new_required - old_required)
    if added_required:
        _add(findings, "breaking", "schema.required_added", location,
             "La nueva versión exige propiedades que antes eran opcionales.",
             sorted(old_required), sorted(new_required))

    old_props, new_props = old.get("properties", {}), new.get("properties", {})
    if isinstance(old_props, dict) and isinstance(new_props, dict):
        for name in sorted(old_props.keys() - new_props.keys()):
            _add(findings, "breaking", "schema.property_removed", f"{location}.{name}",
                 f"Se eliminó la propiedad '{name}'.")
        for name in sorted(old_props.keys() & new_props.keys()):
            _compare_schema(old_props[name], new_props[name], f"{location}.{name}", findings, direction=direction)
        for name in sorted(new_props.keys() - old_props.keys()):
            if name not in new_required:
                _add(findings, "compatible", "schema.optional_property_added", f"{location}.{name}",
                     f"Se agregó la propiedad opcional '{name}'.")

    if "items" in old and "items" in new:
        _compare_schema(old["items"], new["items"], f"{location}[]", findings, direction=direction)


def _parameter_map(parameters: Any, spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    resolved = _resolve(parameters or [], spec)
    if not isinstance(resolved, list):
        return {}
    return {
        (str(item.get("in", "")), str(item.get("name", ""))): item
        for item in resolved if isinstance(item, dict)
    }


def _compare_operation(
    old: dict[str, Any], new: dict[str, Any], old_spec: dict[str, Any],
    new_spec: dict[str, Any], path: str, method: str, findings: list[Finding],
) -> None:
    location = f"{method.upper()} {path}"
    old_params = _parameter_map(old.get("parameters", []), old_spec)
    new_params = _parameter_map(new.get("parameters", []), new_spec)
    for key in sorted(old_params.keys() - new_params.keys()):
        _add(findings, "breaking", "parameter.removed", f"{location} · {key[0]}:{key[1]}",
             f"Se eliminó el parámetro '{key[1]}'.")
    for key in sorted(new_params.keys() - old_params.keys()):
        param = new_params[key]
        if param.get("required"):
            _add(findings, "breaking", "parameter.required_added", f"{location} · {key[0]}:{key[1]}",
                 f"Se agregó el parámetro obligatorio '{key[1]}'.")
        else:
            _add(findings, "compatible", "parameter.optional_added", f"{location} · {key[0]}:{key[1]}",
                 f"Se agregó el parámetro opcional '{key[1]}'.")

    old_body = _resolve(old.get("requestBody", {}), old_spec)
    new_body = _resolve(new.get("requestBody", {}), new_spec)
    if isinstance(old_body, dict) and isinstance(new_body, dict):
        if not old_body.get("required", False) and new_body.get("required", False):
            _add(findings, "breaking", "request_body.required", f"{location} · requestBody",
                 "El cuerpo de la solicitud ahora es obligatorio.")
        old_content = old_body.get("content", {})
        new_content = new_body.get("content", {})
        for media_type in sorted(old_content.keys() & new_content.keys()):
            a = _resolve(old_content[media_type].get("schema", {}), old_spec)
            b = _resolve(new_content[media_type].get("schema", {}), new_spec)
            _compare_schema(a, b, f"{location} · requestBody.{media_type}", findings, direction="request")
    elif old_body and not new_body:
        _add(findings, "breaking", "request_body.removed", f"{location} · requestBody",
             "Se eliminó el cuerpo de la solicitud.")

    old_responses = _resolve(old.get("responses", {}), old_spec)
    new_responses = _resolve(new.get("responses", {}), new_spec)
    if isinstance(old_responses, dict) and isinstance(new_responses, dict):
        for code in sorted(old_responses.keys() - new_responses.keys()):
            _add(findings, "breaking", "response.removed", f"{location} · respuesta {code}",
                 f"Se eliminó la respuesta '{code}'.")
        for code in sorted(old_responses.keys() & new_responses.keys()):
            old_resp, new_resp = old_responses[code], new_responses[code]
            old_content = old_resp.get("content", {}) if isinstance(old_resp, dict) else {}
            new_content = new_resp.get("content", {}) if isinstance(new_resp, dict) else {}
            for media_type in sorted(old_content.keys() & new_content.keys()):
                a = _resolve(old_content[media_type].get("schema", {}), old_spec)
                b = _resolve(new_content[media_type].get("schema", {}), new_spec)
                _compare_schema(a, b, f"{location} · {code}.{media_type}", findings, direction="response")


def compare_specs(old_spec: dict[str, Any], new_spec: dict[str, Any], before: str, after: str) -> Report:
    """Compara dos OpenAPI 3.x; los hallazgos son reglas estáticas conservadoras."""
    old_paths = old_spec.get("paths", {})
    new_paths = new_spec.get("paths", {})
    findings: list[Finding] = []

    for path in sorted(old_paths.keys() - new_paths.keys()):
        _add(findings, "breaking", "path.removed", path, f"Se eliminó la ruta '{path}'.")
    for path in sorted(new_paths.keys() - old_paths.keys()):
        _add(findings, "compatible", "path.added", path, f"Se agregó la ruta '{path}'.")

    for path in sorted(old_paths.keys() & new_paths.keys()):
        old_item = _resolve(old_paths[path], old_spec)
        new_item = _resolve(new_paths[path], new_spec)
        if not isinstance(old_item, dict) or not isinstance(new_item, dict):
            continue
        old_methods = {key for key in old_item if key.lower() in HTTP_METHODS}
        new_methods = {key for key in new_item if key.lower() in HTTP_METHODS}
        for method in sorted(old_methods - new_methods):
            _add(findings, "breaking", "operation.removed", f"{method.upper()} {path}",
                 f"Se eliminó la operación {method.upper()} {path}.")
        for method in sorted(new_methods - old_methods):
            _add(findings, "compatible", "operation.added", f"{method.upper()} {path}",
                 f"Se agregó la operación {method.upper()} {path}.")
        for method in sorted(old_methods & new_methods):
            a = old_item[method]
            b = new_item[method]
            if isinstance(a, dict) and isinstance(b, dict):
                inherited_a = old_item.get("parameters", [])
                inherited_b = new_item.get("parameters", [])
                a = {**a, "parameters": inherited_a + a.get("parameters", [])}
                b = {**b, "parameters": inherited_b + b.get("parameters", [])}
                _compare_operation(a, b, old_spec, new_spec, path, method, findings)

    # Deduplicar hallazgos idénticos que puedan surgir de parámetros heredados.
    unique = {(item.severity, item.rule, item.location, item.message): item for item in findings}
    ordered = tuple(sorted(unique.values(), key=lambda item: (item.severity != "breaking", item.location, item.rule)))
    breaking = sum(item.severity == "breaking" for item in ordered)
    compatible = sum(item.severity == "compatible" for item in ordered)
    recommendation = "major" if breaking else "minor" if compatible else "patch"
    return Report(before, after, breaking, compatible, recommendation, ordered)


def compare_files(before: str | Path, after: str | Path) -> Report:
    return compare_specs(load_spec(before), load_spec(after), str(before), str(after))
