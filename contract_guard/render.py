"""Renderizadores de informes para terminal y Markdown."""

from __future__ import annotations

from .analyzer import Report


def render_text(report: Report) -> str:
    lines = [
        f"Compatibilidad OpenAPI: {report.before} → {report.after}",
        f"Hallazgos: {report.breaking} incompatibles · {report.compatible} compatibles",
        f"Versión sugerida: {report.recommendation}",
    ]
    for item in report.findings:
        label = "INCOMPATIBLE" if item.severity == "breaking" else "COMPATIBLE"
        lines.append(f"\n[{label}] {item.location}\n  {item.message} ({item.rule})")
    if not report.findings:
        lines.append("\nNo se detectaron cambios en las reglas cubiertas.")
    return "\n".join(lines)


def render_markdown(report: Report) -> str:
    lines = [
        "# Informe de compatibilidad OpenAPI", "",
        f"- **Anterior:** `{report.before}`",
        f"- **Nueva:** `{report.after}`",
        f"- **Cambios incompatibles:** {report.breaking}",
        f"- **Cambios compatibles:** {report.compatible}",
        f"- **Versión sugerida:** `{report.recommendation}`", "",
    ]
    if report.findings:
        lines.extend(["## Hallazgos", "", "| Nivel | Ubicación | Regla | Detalle |", "|---|---|---|---|"])
        for item in report.findings:
            severity = "Incompatible" if item.severity == "breaking" else "Compatible"
            message = item.message.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {severity} | `{item.location}` | `{item.rule}` | {message} |")
    else:
        lines.append("No se detectaron cambios en las reglas cubiertas.")
    lines.extend(["", "> El análisis es estático: revisa el informe antes de publicar cambios de contrato."])
    return "\n".join(lines) + "\n"
