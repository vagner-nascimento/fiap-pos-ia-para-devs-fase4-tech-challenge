"""Extrator determinístico de entidades clínicas a partir de laudos médicos em pt-BR."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


def _normalize_text(text: str) -> str:
    """Normaliza texto para minúsculas e sem acentos para matching robusto."""
    lowered = (text or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


@dataclass
class ExtractedMedicalReportInfo:
    """Resultado da extração automática de entidades do texto do laudo."""

    regiao: Optional[str] = None
    lesao: Optional[str] = None
    movimentos_restritos: list[str] = field(default_factory=list)
    limite_amplitude_max: Optional[float] = None


# Padrões de regiões anatômicas (do mais específico para o mais geral)
_REGION_PATTERNS: list[tuple[str, str]] = [
    (r"\bombro\s+direito\b", "ombro direito"),
    (r"\bombro\s+esquerdo\b", "ombro esquerdo"),
    (r"\bambos\s+os\s+ombros\b|\bombros\b", "ombros"),
    (r"\bombro\b", "ombro"),
    (r"\bjoelho\s+direito\b", "joelho direito"),
    (r"\bjoelho\s+esquerdo\b", "joelho esquerdo"),
    (r"\bjoelhos\b|\bjoelho\b", "joelho"),
    (r"\bcotovelo\s+direito\b", "cotovelo direito"),
    (r"\bcotovelo\s+esquerdo\b", "cotovelo esquerdo"),
    (r"\bcotovelos\b|\bcotovelo\b", "cotovelo"),
    (r"\bcoluna\s+lombar\s+e\s+pelve\b", "coluna lombar e pelve"),
    (r"\bcoluna\s+lombar\b|\blombar\b", "coluna lombar"),
    (r"\bpelve\b|\bquadril\b", "pelve / quadril"),
    (r"\btronco\b", "tronco"),
]

# Padrões de lesões / condições ortopédicas
_LESION_PATTERNS: list[tuple[str, str]] = [
    (r"\btendinopatia\b|\btendinite\b|\bmanguito\s+rotador\b", "tendinopatia"),
    (r"\bp[oó]s[-\s]?lca\b|\bligamento\s+cruzado\s+anterior\b|\blca\b", "pós-LCA"),
    (r"\bosteoartrite\b|\bartrose\b|\bgonartrose\b", "osteoartrite"),
    (r"\blombalgia\b|\bdor\s+lombar\b|\bh[eé]rnia\s+de\s+disco\b", "lombalgia"),
    (r"\bepicondilite\s+lateral\b", "epicondilite lateral"),
    (r"\bepicondilite\s+medial\b", "epicondilite medial"),
    (r"\bepicondilite\b", "epicondilite"),
    (r"\bbursite\b", "bursite"),
    (r"\bcapsulite\s+adesiva\b", "capsulite adesiva"),
    (r"\brigidez\s+articular\b|\brigidez\b", "rigidez articular"),
]


def extract_medical_report_entities(texto_original: str) -> ExtractedMedicalReportInfo:
    """
    Extrai região anatômica, lesão, movimentos restritos e limite angular máximo
    a partir do texto livre de um laudo médico sintético em português.
    """
    raw = (texto_original or "").strip()
    if not raw:
        return ExtractedMedicalReportInfo()

    norm = _normalize_text(raw)

    regiao: Optional[str] = None
    for pattern, label in _REGION_PATTERNS:
        if re.search(pattern, norm):
            regiao = label
            break

    lesao: Optional[str] = None
    for pattern, label in _LESION_PATTERNS:
        if re.search(pattern, norm):
            lesao = label
            break

    movimentos_restritos: list[str] = []
    limite_amplitude_max: Optional[float] = None

    # 1. Restrições explícitas de ângulo (ex: "evitar elevação acima de 90°", "limite de 120 graus")
    angle_restriction_match = re.search(
        r"(?:evitar|evite|restrit[oa]|nao\s+ultrapassar|acima\s+de|alem\s+de|limite\s+(?:maximo\s+)?de)\s+"
        r"([a-z\s]{0,30}?)"
        r"(?:acima\s+de|alem\s+de|>\s*|maior\s+que\s*)?"
        r"(\d{2,3})\s*(?:°|º|graus?)",
        norm,
    )
    if angle_restriction_match:
        mov_raw = angle_restriction_match.group(1).strip()
        deg_str = angle_restriction_match.group(2)
        try:
            limite_amplitude_max = float(deg_str)
        except ValueError:
            pass

        mov_label = "amplitude"
        if "elevacao" in mov_raw:
            mov_label = "elevação"
        elif "abducao" in mov_raw:
            mov_label = "abdução"
        elif "flexao" in mov_raw:
            mov_label = "flexão"
        elif "extensao" in mov_raw:
            mov_label = "extensão"
        elif "rotacao" in mov_raw:
            mov_label = "rotação"

        movimentos_restritos.append(f"{mov_label} > {int(limite_amplitude_max or int(deg_str))}°")
    else:
        # Fallback: busca qualquer "<movimento> acima de XX°"
        generic_angle_match = re.search(
            r"\b(elevacao|abducao|flexao|extensao|rotacao|amplitude)\b[^.]{0,25}?\b(?:acima\s+de|>\s*|alem\s+de)\s*(\d{2,3})\s*(?:°|º|graus?)",
            norm,
        )
        if generic_angle_match:
            mov_map = {
                "elevacao": "elevação",
                "abducao": "abdução",
                "flexao": "flexão",
                "extensao": "extensão",
                "rotacao": "rotação",
                "amplitude": "amplitude",
            }
            mov_name = mov_map.get(generic_angle_match.group(1), generic_angle_match.group(1))
            deg_val = int(generic_angle_match.group(2))
            limite_amplitude_max = float(deg_val)
            movimentos_restritos.append(f"{mov_name} > {deg_val}°")

    # 2. Restrições qualitativas comuns do domínio fisioterapêutico (PRD seção 8.3)
    qualitative_rules: list[tuple[str, str]] = [
        (r"extensao\s+forcada", "extensão forçada"),
        (r"rotacao\s+lombar\s+ampla", "rotação lombar ampla sob carga"),
        (r"carga\s+acima\s+do\s+limite|sobrecarga|carga\s+externa\s+elevada", "carga acima do limite"),
        (r"nao\s+utilizar\s+carga\s+externa|sem\s+carga\s+externa", "uso de carga externa"),
        (r"elevacao\s+ativa\s+do\s+ombro", "elevação ativa do ombro"),
        (r"compensac(?:ao|oes)\s+(?:do\s+|de\s+)?tronco|inclinacao\s+do\s+tronco", "compensação de tronco"),
    ]
    for pattern, label in qualitative_rules:
        if re.search(pattern, norm) and label not in movimentos_restritos:
            movimentos_restritos.append(label)

    return ExtractedMedicalReportInfo(
        regiao=regiao,
        lesao=lesao,
        movimentos_restritos=movimentos_restritos,
        limite_amplitude_max=limite_amplitude_max,
    )


def parse_amplitude_range(texto: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    Extrai os valores mínimo e máximo de uma string de faixa angular (ex: '60 – 90', '60 a 90', '150-180').
    Caso haja apenas um número (ex: '90'), retorna (None, 90.0).
    """
    if not texto:
        return None, None
    numbers = re.findall(r"\d+(?:[.,]\d+)?", texto)
    if not numbers:
        return None, None
    parsed = [float(n.replace(",", ".")) for n in numbers]
    if len(parsed) >= 2:
        low, high = min(parsed[0], parsed[1]), max(parsed[0], parsed[1])
        return low, high
    return None, parsed[0]

