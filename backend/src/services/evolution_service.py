"""Serviço de cálculo de métricas biomecânicas por série e Relatório Final de Evolução Longitudinal (Issue #7).

Avalia a jornada do paciente ao longo de múltiplos dias de tratamento e múltiplos exercícios
(N séries x M repetições/série por exercício), consolidando:
1. Amplitude articular (média, máxima e evolução entre séries e dias);
2. Consistência biomecânica (taxa de repetições válidas, regularidade angular/temporal e aderência ao volume N x M);
3. Nível de dor (escala 0-10 e percentual temporal frente ao limite do plano).
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Optional

import numpy as np

from models.database.alert import AlertDocument, AlertSeverity, AlertStatus
from models.database.event import EventDocument
from models.database.medical_report import MedicalReportDocument
from models.database.patient import PatientDocument
from models.database.plan import PlanDocument, PrescribedExerciseItem
from models.database.session import RiskClassification, SessionDocument
from models.rest.patient import (
    DayEvolutionSummary,
    EvolutionGlobalMetrics,
    ExerciseEvolutionSeries,
    ExerciseSessionPoint,
    PatientEvolutionReportResponse,
)
from services.audio_transcription import SpeechSegment
from services.pose.models import ExerciseAnalysisResult, RepetitionEvent

RISK_SYMBOLS = {
    "verde": "●",
    "atencao": "▲",
    "critico": "■",
}

DEFAULT_REFERENCE_ANGLES = {
    "FISIO-001": 162.0,
    "KNEE_EXTENSION_SEATED": 162.0,
    "FISIO-002": 72.0,
    "SHOULDER_PENDULUM": 72.0,
    "FISIO-003": 32.0,
    "PELVIC_TILT_SUPINE": 32.0,
    "FISIO-004": 38.0,
    "KNEE_ROLLS_SUPINE": 38.0,
    "FISIO-005": 84.0,
    "SHOULDER_FLEXION_STICK": 84.0,
    "FISIO-006": 82.0,
    "SHOULDER_ABDUCTION_BAND": 82.0,
    "FISIO-007": 132.0,
    "ELBOW_FLEXION_LIGHT_DUMBBELL": 132.0,
}

EXERCISE_FRIENDLY_NAMES = {
    "FISIO-001": "Extensão de joelho sentado",
    "KNEE_EXTENSION_SEATED": "Extensão de joelho sentado",
    "FISIO-002": "Exercício pendular do ombro",
    "SHOULDER_PENDULUM": "Exercício pendular do ombro",
    "FISIO-003": "Inclinação pélvica em decúbito dorsal",
    "PELVIC_TILT_SUPINE": "Inclinação pélvica em decúbito dorsal",
    "FISIO-004": "Rotação controlada dos joelhos",
    "KNEE_ROLLS_SUPINE": "Rotação controlada dos joelhos",
    "FISIO-005": "Flexão de ombro com bastão leve",
    "SHOULDER_FLEXION_STICK": "Flexão de ombro com bastão leve",
    "FISIO-006": "Abdução de ombro com faixa elástica",
    "SHOULDER_ABDUCTION_BAND": "Abdução de ombro com faixa elástica",
    "FISIO-007": "Flexão de cotovelo com halter leve",
    "ELBOW_FLEXION_LIGHT_DUMBBELL": "Flexão de cotovelo com halter leve",
}


def _extract_explicit_pain_number(text: str) -> Optional[float]:
    """Extrai nota explícita de dor (ex.: '6 de 10', 'dor 7/10', 'nota 5') quando falada pelo paciente."""
    if not text:
        return None
    match = re.search(r"\b(10|[0-9])\s*(?:de\s*10|/\s*10)\b", text.lower())
    if match:
        return float(match.group(1))
    return None


def compute_pain_score_0_10(
    speech_segments: list[SpeechSegment] | list[dict[str, Any]],
    video_duration_seconds: float,
) -> tuple[float, float]:
    """
    Calcula o score de dor consolidado na escala 0..10 e o percentual de tempo com dor.
    Combina menções explícitas ('6 de 10'), níveis semânticos ('desconforto', 'dor', 'muita_dor')
    e proporção temporal de dor no vídeo.
    """
    level_to_scale = {
        "pouca_ou_nenhuma_dor": 0.0,
        "indeterminado": 0.0,
        "desconforto": 3.0,
        "dor": 6.0,
        "muita_dor": 8.5,
    }
    pain_levels = {"desconforto", "dor", "muita_dor"}

    max_level_score = 0.0
    explicit_scores: list[float] = []
    pain_duration = 0.0

    for seg in speech_segments or []:
        if isinstance(seg, SpeechSegment):
            nivel = seg.nivel
            texto = seg.texto
            dur = max(0.0, float(seg.end_seconds) - float(seg.start_seconds))
        else:
            nivel = str(seg.get("nivel") or "")
            texto = str(seg.get("texto") or seg.get("descricao") or "")
            dur = max(
                0.0,
                float(seg.get("end_seconds") or seg.get("instante_fim") or 0.0)
                - float(seg.get("start_seconds") or seg.get("instante_inicio") or 0.0),
            )

        explicit_val = _extract_explicit_pain_number(texto)
        if explicit_val is not None:
            explicit_scores.append(explicit_val)

        mapped = level_to_scale.get(nivel, 0.0)
        if mapped > max_level_score:
            max_level_score = mapped

        if nivel in pain_levels:
            pain_duration += dur

    dur_total = max(float(video_duration_seconds or 0.0), pain_duration, 1.0)
    pain_percent = round(min(100.0, (pain_duration / dur_total) * 100.0), 1) if pain_duration > 0 else 0.0

    if explicit_scores:
        base_score = max(explicit_scores)
    elif max_level_score > 0:
        # Ajusta levemente pela persistência temporal (até +1.2 pontos se dor persistente no vídeo)
        density_bonus = min(1.2, (pain_percent / 100.0) * 2.5)
        base_score = min(10.0, max_level_scale := max_level_score + density_bonus)
    else:
        base_score = 0.0

    return round(min(10.0, max(0.0, base_score)), 1), pain_percent


def build_series_breakdown(
    repetitions: list[RepetitionEvent] | list[dict[str, Any]],
    series_prescritas: int = 1,
    repeticoes_por_serie: int = 5,
    fallback_angle: Optional[float] = None,
) -> list[dict[str, Any]]:
    """
    Agrupa as repetições executadas nas N séries prescritas (de tamanho M = repeticoes_por_serie),
    permitindo avaliar consistência, fadiga e queda de amplitude entre a 1ª e a última série.
    """
    n_series = max(1, int(series_prescritas or 1))
    m_reps = max(1, int(repeticoes_por_serie or 5))

    normalized_reps: list[dict[str, Any]] = []
    for idx, rep in enumerate(repetitions or [], start=1):
        if isinstance(rep, RepetitionEvent):
            normalized_reps.append({
                "index": rep.index or idx,
                "peak_angle": rep.peak_angle,
                "peak_progress": rep.peak_progress,
                "duration": rep.duration,
                "is_valid": rep.is_valid,
                "deviations": list(rep.deviations or []),
            })
        else:
            valores = rep.get("valores") if "valores" in rep else rep
            normalized_reps.append({
                "index": (valores or {}).get("repetition_index") or idx,
                "peak_angle": (valores or {}).get("peak_angle"),
                "peak_progress": (valores or {}).get("peak_progress", 1.0),
                "duration": rep.get("duracao") or (valores or {}).get("duration") or 2.0,
                "is_valid": bool((valores or {}).get("is_valid", True)),
                "deviations": list((valores or {}).get("deviations") or []),
            })

    breakdown: list[dict[str, Any]] = []
    for s_idx in range(1, n_series + 1):
        start_pos = (s_idx - 1) * m_reps
        end_pos = s_idx * m_reps
        chunk = normalized_reps[start_pos:end_pos]

        # Se for a última série prescrita e houver repetições extras além de N*M, inclui na última série
        if s_idx == n_series and len(normalized_reps) > end_pos:
            chunk = normalized_reps[start_pos:]

        completed = len(chunk)
        valid = sum(1 for r in chunk if r["is_valid"])
        angles = [
            float(r["peak_angle"])
            for r in chunk
            if r.get("peak_angle") is not None and not math.isnan(float(r["peak_angle"]))
        ]
        if not angles and completed > 0 and fallback_angle is not None:
            angles = [float(fallback_angle)] * completed

        amp_media = round(float(np.mean(angles)), 1) if angles else 0.0
        amp_max = round(float(np.max(angles)), 1) if angles else 0.0
        devs_count = sum(len(r.get("deviations") or []) for r in chunk)
        taxa_validas = round((valid / completed) * 100.0, 1) if completed > 0 else 0.0

        breakdown.append({
            "serie_index": s_idx,
            "label": f"Série {s_idx}",
            "repeticoes_alvo": m_reps,
            "repeticoes_completadas": completed,
            "repeticoes_validas": valid,
            "amplitude_media": amp_media,
            "amplitude_maxima": amp_max,
            "desvios_count": devs_count,
            "consistencia_serie": taxa_validas,
            "concluida": completed >= m_reps,
        })

    return breakdown


def compute_consistency_score(
    completed_repetitions: int,
    valid_repetitions: int,
    target_repetitions: int,
    peak_angles: list[float],
    durations: list[float],
) -> float:
    """
    Calcula o Score de Consistência Biomecânica (0..100%):
    - 50% Taxa de repetições válidas (sem compensações posturais);
    - 30% Regularidade angular e temporal entre repetições/séries (1 - CV médio);
    - 20% Aderência ao volume prescrito (completed / target).
    """
    if completed_repetitions <= 0:
        return 0.0

    valid_rate = (max(0, valid_repetitions) / max(1, completed_repetitions)) * 100.0
    target = max(1, target_repetitions or completed_repetitions)
    volume_adherence = min(100.0, (completed_repetitions / target) * 100.0)

    cv_components: list[float] = []
    if len(peak_angles) >= 2:
        mean_ang = float(np.mean(peak_angles))
        if abs(mean_ang) > 1e-3:
            cv_ang = float(np.std(peak_angles) / abs(mean_ang))
            cv_components.append(min(1.0, cv_ang))
    if len(durations) >= 2:
        mean_dur = float(np.mean(durations))
        if mean_dur > 1e-3:
            cv_dur = float(np.std(durations) / mean_dur)
            cv_components.append(min(1.0, cv_dur))

    if cv_components:
        regularity = max(0.0, (1.0 - float(np.mean(cv_components))) * 100.0)
    else:
        regularity = valid_rate

    score = 0.50 * valid_rate + 0.30 * regularity + 0.20 * volume_adherence
    return round(min(100.0, max(0.0, score)), 1)


def compute_session_evolution_metrics(
    result: ExerciseAnalysisResult,
    speech_segments: Optional[list[SpeechSegment]] = None,
    series_prescritas: int = 1,
    repeticoes_por_serie: int = 5,
) -> dict[str, Any]:
    """Extrai todas as métricas evolutivas de uma sessão recém-processada pelo motor de visão e áudio."""
    reps = result.repetitions or []
    case_key = result.session_summary.case_id or result.session_summary.exercise_id
    default_angle = DEFAULT_REFERENCE_ANGLES.get(case_key, 80.0)

    peak_angles = [
        float(r.peak_angle)
        for r in reps
        if r.peak_angle is not None and not math.isnan(float(r.peak_angle))
    ]
    if not peak_angles and reps:
        peak_angles = [round(default_angle * max(0.5, float(r.peak_progress or 0.85)), 1) for r in reps]

    durations = [float(r.duration) for r in reps if r.duration and r.duration > 0]

    amplitude_media = round(float(np.mean(peak_angles)), 1) if peak_angles else 0.0
    amplitude_maxima = round(float(np.max(peak_angles)), 1) if peak_angles else 0.0

    target_total = (
        result.session_summary.target_repetitions
        or (max(1, series_prescritas) * max(1, repeticoes_por_serie))
    )
    consistencia_score = compute_consistency_score(
        completed_repetitions=result.session_summary.completed_repetitions,
        valid_repetitions=result.session_summary.valid_repetitions,
        target_repetitions=target_total,
        peak_angles=peak_angles,
        durations=durations,
    )

    dor_score, dor_pct = compute_pain_score_0_10(
        speech_segments=speech_segments or [],
        video_duration_seconds=result.session_summary.duration_seconds,
    )

    series_breakdown = build_series_breakdown(
        repetitions=reps,
        series_prescritas=series_prescritas,
        repeticoes_por_serie=repeticoes_por_serie,
        fallback_angle=amplitude_media or default_angle,
    )

    return {
        "amplitude_media": amplitude_media,
        "amplitude_maxima": amplitude_maxima,
        "consistencia_score": consistencia_score,
        "dor_score_0_10": dor_score,
        "dor_percentual_tempo": dor_pct,
        "series_breakdown": series_breakdown,
    }


def ensure_session_metrics_populated(
    session: SessionDocument,
    events: Optional[list[EventDocument]] = None,
    plan_item: Optional[PrescribedExerciseItem] = None,
) -> dict[str, Any]:
    """
    Garante que qualquer SessionDocument (inclusive sessões anteriores à Issue #7)
    possua valores consistentes de amplitude_media, amplitude_maxima, consistencia_score,
    dor_score_0_10 e series_breakdown.
    """
    series_prescritas = session.series_prescritas or (plan_item.series if plan_item else 1)
    reps_por_serie = session.repeticoes_por_serie or (
        plan_item.repeticoes if plan_item else (session.target_repetitions or 5)
    )
    target_reps = session.target_repetitions or (series_prescritas * reps_por_serie)

    case_key = session.case_id or session.exercicio_id
    base_ref_angle = DEFAULT_REFERENCE_ANGLES.get(case_key, 80.0)
    compliance_ratio = max(0.55, min(1.0, float(session.compliance_score or 85.0) / 100.0))

    rep_events = [ev for ev in (events or []) if ev.tipo.value == "repeticao"]
    pain_events = [ev for ev in (events or []) if ev.tipo.value == "fala_dor"]

    # Amplitude
    amp_media = session.amplitude_media
    amp_max = session.amplitude_maxima
    peak_angles: list[float] = []
    durations: list[float] = []

    for ev in rep_events:
        val_ang = (ev.valores or {}).get("peak_angle")
        if val_ang is not None:
            peak_angles.append(float(val_ang))
        if ev.duracao:
            durations.append(float(ev.duracao))

    if amp_media is None or amp_media <= 0:
        if peak_angles:
            amp_media = round(float(np.mean(peak_angles)), 1)
        else:
            amp_media = round(base_ref_angle * compliance_ratio, 1)

    if amp_max is None or amp_max <= 0:
        if peak_angles:
            amp_max = round(float(np.max(peak_angles)), 1)
        else:
            amp_max = round(min(180.0, amp_media + 4.0), 1)

    # Consistência
    consistencia = session.consistencia_score
    if consistencia is None or consistencia <= 0:
        completed = session.completed_repetitions or session.valid_repetitions or target_reps
        valid = session.valid_repetitions or 0
        consistencia = compute_consistency_score(
            completed_repetitions=completed,
            valid_repetitions=valid,
            target_repetitions=target_reps,
            peak_angles=peak_angles or [amp_media],
            durations=durations,
        )

    # Dor
    dor_score = session.dor_score_0_10
    dor_pct = session.dor_percentual_tempo
    if dor_score == 0.0 and pain_events:
        dur_video = session.summary.duration_seconds if session.summary else 20.0
        pain_dicts = [
            {
                "nivel": (ev.valores or {}).get("nivel"),
                "texto": (ev.evidencia or {}).get("transcricao") or ev.descricao or "",
                "instante_inicio": ev.instante_inicio,
                "instante_fim": ev.instante_fim,
            }
            for ev in pain_events
        ]
        dor_score, dor_pct = compute_pain_score_0_10(pain_dicts, dur_video)

    # Series breakdown
    breakdown = session.series_breakdown
    if not breakdown:
        if rep_events:
            breakdown = build_series_breakdown(
                repetitions=[ev.model_dump() for ev in rep_events],
                series_prescritas=series_prescritas,
                repeticoes_por_serie=reps_por_serie,
                fallback_angle=amp_media,
            )
        else:
            # Sintetiza divisão proporcional a partir dos totais da sessão
            total_comp = session.completed_repetitions or session.valid_repetitions or target_reps
            total_val = session.valid_repetitions or 0
            remaining_comp = total_comp
            remaining_val = total_val
            breakdown = []
            for s_idx in range(1, max(1, series_prescritas) + 1):
                comp_s = min(reps_por_serie, remaining_comp) if s_idx < series_prescritas else remaining_comp
                val_s = min(comp_s, remaining_val)
                remaining_comp = max(0, remaining_comp - comp_s)
                remaining_val = max(0, remaining_val - val_s)
                breakdown.append({
                    "serie_index": s_idx,
                    "label": f"Série {s_idx}",
                    "repeticoes_alvo": reps_por_serie,
                    "repeticoes_completadas": comp_s,
                    "repeticoes_validas": val_s,
                    "amplitude_media": amp_media,
                    "amplitude_maxima": amp_max,
                    "desvios_count": max(0, comp_s - val_s),
                    "consistencia_serie": round((val_s / comp_s) * 100.0, 1) if comp_s > 0 else 0.0,
                    "concluida": comp_s >= reps_por_serie,
                })

    return {
        "series_prescritas": series_prescritas,
        "repeticoes_por_serie": reps_por_serie,
        "target_repetitions": target_reps,
        "amplitude_media": round(float(amp_media), 1),
        "amplitude_maxima": round(float(amp_max), 1),
        "consistencia_score": round(float(consistencia), 1),
        "dor_score_0_10": round(float(dor_score), 1),
        "dor_percentual_tempo": round(float(dor_pct), 1),
        "series_breakdown": breakdown,
    }


def generate_alerts_for_session(
    session: SessionDocument,
    paciente_nome: Optional[str] = None,
    plano: Optional[PlanDocument] = None,
    laudo: Optional[MedicalReportDocument] = None,
) -> list[AlertDocument]:
    """
    Gera alertas clínicos explicáveis para o Painel de Alertas a partir dos indicadores da sessão
    confrontados com o Plano de Tratamento e o Laudo Médico (RF-14, RF-15, RF-18).
    """
    alerts: list[AlertDocument] = []
    if not session.paciente_id:
        return alerts

    now = datetime.now(timezone.utc)
    nome = paciente_nome or session.paciente_id
    ex_nome = EXERCISE_FRIENDLY_NAMES.get(session.case_id or session.exercicio_id, session.exercicio_id)
    limite_dor = plano.dor_maxima_aceitavel if plano else 4
    dor_atual = float(session.dor_score_0_10 or 0.0)
    amp_max = float(session.amplitude_maxima or 0.0)
    consistencia = float(session.consistencia_score or session.compliance_score or 100.0)

    # 1. Alerta de Dor acima do limite do plano
    if dor_atual > limite_dor:
        is_crit = dor_atual >= limite_dor + 2.5 or dor_atual >= 7.0
        sev = AlertSeverity.CRITICO if is_crit else AlertSeverity.ATENCAO
        regiao_txt = f" na região de {laudo.regiao}" if laudo and laudo.regiao else ""
        alerts.append(
            AlertDocument(
                alerta_id=f"ALT-DOR-{session.session_id}",
                paciente_id=session.paciente_id,
                paciente_nome=nome,
                session_id=session.session_id,
                slot_id=session.slot_id,
                exercicio_id=session.case_id or session.exercicio_id,
                dia_tratamento=session.dia_tratamento,
                severidade=sev,
                tipo="dor_acima_limite",
                titulo=f"{nome} · dor {dor_atual:.1f}/10 acima do limite ({limite_dor}/10) em {session.case_id or session.exercicio_id}",
                motivo=(
                    f"Relato de dor consolidado em {dor_atual:.1f}/10 durante {ex_nome}{regiao_txt} "
                    f"(Dia {session.dia_tratamento}), superando o limite prescrito de {limite_dor}/10."
                ),
                evidencia_resumo=(
                    f"Dia {session.dia_tratamento} · Dor {dor_atual:.1f}/10 ({session.dor_percentual_tempo:.1f}% do vídeo)"
                ),
                estado=AlertStatus.TRATADO if session.avaliado_fisioterapeuta else AlertStatus.NOVO,
                created_at=session.created_at or now,
                updated_at=now,
            )
        )

    # 2. Alerta de violação de amplitude máxima segura do laudo
    if laudo and laudo.limite_amplitude_max is not None and amp_max > laudo.limite_amplitude_max + 2.0:
        alerts.append(
            AlertDocument(
                alerta_id=f"ALT-LAU-{session.session_id}",
                paciente_id=session.paciente_id,
                paciente_nome=nome,
                session_id=session.session_id,
                slot_id=session.slot_id,
                exercicio_id=session.case_id or session.exercicio_id,
                dia_tratamento=session.dia_tratamento,
                severidade=AlertSeverity.CRITICO,
                tipo="violacao_laudo",
                titulo=f"{nome} · amplitude de {amp_max:.0f}° excedeu limite do laudo ({laudo.limite_amplitude_max:.0f}°)",
                motivo=(
                    f"Pico angular de {amp_max:.1f}° em {ex_nome} ultrapassou a restrição ortopédica "
                    f"do laudo ({laudo.lesao or 'restrição articular'}: máx. {laudo.limite_amplitude_max:.0f}°)."
                ),
                evidencia_resumo=f"Dia {session.dia_tratamento} · Pico {amp_max:.1f}° vs. limite {laudo.limite_amplitude_max:.0f}°",
                estado=AlertStatus.TRATADO if session.avaliado_fisioterapeuta else AlertStatus.NOVO,
                created_at=session.created_at or now,
                updated_at=now,
            )
        )

    # 3. Alerta de desvios posturais / baixa consistência entre séries
    if (session.total_deviations or 0) > 0 and not alerts:
        sev = (
            AlertSeverity.CRITICO
            if session.risk_classification == RiskClassification.CRITICO
            else AlertSeverity.ATENCAO
        )
        alerts.append(
            AlertDocument(
                alerta_id=f"ALT-BIO-{session.session_id}",
                paciente_id=session.paciente_id,
                paciente_nome=nome,
                session_id=session.session_id,
                slot_id=session.slot_id,
                exercicio_id=session.case_id or session.exercicio_id,
                dia_tratamento=session.dia_tratamento,
                severidade=sev,
                tipo="baixa_consistencia",
                titulo=f"{nome} · {session.total_deviations} desvio(s) postural(is) em {session.case_id or session.exercicio_id} (Dia {session.dia_tratamento})",
                motivo=(
                    f"Consistência de {consistencia:.1f}% nas séries de {ex_nome}, com "
                    f"{session.total_deviations} desvio(s) postural(is) detectado(s)."
                ),
                evidencia_resumo=(
                    f"Dia {session.dia_tratamento} · Consistência {consistencia:.0f}% · "
                    f"Amplitude média {float(session.amplitude_media or 0.0):.1f}°"
                ),
                estado=AlertStatus.TRATADO if session.avaliado_fisioterapeuta else AlertStatus.NOVO,
                created_at=session.created_at or now,
                updated_at=now,
            )
        )

    return alerts


def build_patient_evolution_report(
    patient: PatientDocument,
    laudo: Optional[MedicalReportDocument],
    plano: Optional[PlanDocument],
    sessions: list[SessionDocument],
    alerts: list[AlertDocument],
) -> PatientEvolutionReportResponse:
    """
    Constrói o Relatório Final de Evolução Longitudinal do Paciente ao longo dos dias de tratamento
    e dos exercícios prescritos (N séries x M repetições/série), avaliando:
    - Evolução da Amplitude Articular (graus);
    - Evolução da Consistência Biomecânica (%);
    - Evolução do Nível de Dor (0-10).
    """
    dias_previstos = plano.dias_tratamento if plano and plano.dias_tratamento else 3
    prescribed_items = list(plano.exercicios) if plano and plano.exercicios else []

    # Filtra sessões concluídas do paciente em ordem cronológica (da mais antiga para a mais recente)
    completed_sessions = [
        s for s in sessions
        if (s.status.value if hasattr(s.status, "value") else str(s.status)) == "concluido"
    ]
    completed_sessions.sort(key=lambda s: (s.dia_tratamento or 1, s.created_at or datetime.min.replace(tzinfo=timezone.utc)))

    # Se não houver plano cadastrado, infere slots a partir das sessões existentes
    if not prescribed_items and completed_sessions:
        seen_ex: dict[str, PrescribedExerciseItem] = {}
        for idx, sess in enumerate(completed_sessions, start=1):
            key = sess.slot_id or sess.case_id or sess.exercicio_id
            if key not in seen_ex:
                ex_code = sess.case_id or sess.exercicio_id
                seen_ex[key] = PrescribedExerciseItem(
                    slot_id=sess.slot_id or f"SLOT-{len(seen_ex) + 1}",
                    exercicio_id=ex_code,
                    exercicio_nome=EXERCISE_FRIENDLY_NAMES.get(ex_code, ex_code),
                    lado=sess.side_evaluated or "auto",
                    series=sess.series_prescritas or 3,
                    repeticoes=sess.repeticoes_por_serie or 5,
                )
        prescribed_items = list(seen_ex.values())

    # 1. Construção da evolução por exercício prescrito (agrupando slots do mesmo exercício em dias distintos)
    evolucao_por_exercicio: list[ExerciseEvolutionSeries] = []
    points_by_day: dict[int, list[ExerciseSessionPoint]] = {}

    exercise_groups: list[list[PrescribedExerciseItem]] = []
    group_index_by_ex: dict[tuple[str, str], int] = {}
    for idx, item in enumerate(prescribed_items, start=1):
        if not item.slot_id:
            item.slot_id = f"SLOT-{idx}"
        key = (item.exercicio_id, item.lado or "auto")
        if key in group_index_by_ex:
            existing_grp = exercise_groups[group_index_by_ex[key]]
            existing_days = {d for it in existing_grp for d in it.resolved_days(dias_previstos)}
            item_days = set(item.resolved_days(dias_previstos))
            # Se são dias disjuntos (ex: prescrição separada por dia), une na mesma série longitudinal
            if existing_days.isdisjoint(item_days):
                existing_grp.append(item)
                continue
        group_index_by_ex[key] = len(exercise_groups)
        exercise_groups.append([item])

    for idx, group in enumerate(exercise_groups, start=1):
        item = group[0]
        slot_key = item.slot_id or f"SLOT-{idx}"
        group_slot_ids = {it.slot_id for it in group if it.slot_id}
        prescribed_days = sorted({d for it in group for d in it.resolved_days(dias_previstos)})

        matching = [
            s for s in completed_sessions
            if (s.slot_id and s.slot_id in group_slot_ids)
            or (
                not s.slot_id
                and (s.case_id == item.exercicio_id or s.exercicio_id == item.exercicio_id)
            )
        ]

        # Se houver múltiplas sessões para o mesmo exercício e todas estiverem com dia_tratamento=1 (legado),
        # distribui sequencialmente pelos dias prescritos para preservar a linha evolutiva
        all_day_one = len(matching) > 1 and all((s.dia_tratamento or 1) == 1 for s in matching)

        # Agrupa por dia_tratamento (caso o paciente tenha enviado mais de 1 vídeo/série no mesmo dia)
        grouped_by_day: dict[int, list[SessionDocument]] = {}
        for s_pos, sess in enumerate(matching, start=1):
            day_num = s_pos if all_day_one else (sess.dia_tratamento or 1)
            grouped_by_day.setdefault(day_num, []).append(sess)

        session_points: list[ExerciseSessionPoint] = []
        for day_num in sorted(grouped_by_day.keys()):
            day_sessions = grouped_by_day[day_num]
            primary = day_sessions[-1]
            day_item = next((it for it in group if it.applies_to_day(day_num)), item)
            metrics_list = [ensure_session_metrics_populated(s, plan_item=day_item) for s in day_sessions]

            if len(day_sessions) == 1:
                m = metrics_list[0]
                comp_reps = primary.completed_repetitions or primary.valid_repetitions or 0
                val_reps = primary.valid_repetitions or 0
                inv_reps = primary.invalid_repetitions or 0
                tot_devs = primary.total_deviations or 0
                amp_med = m["amplitude_media"]
                amp_max = m["amplitude_maxima"]
                cons_score = m["consistencia_score"]
                dor_score = m["dor_score_0_10"]
                dor_pct = m["dor_percentual_tempo"]
                breakdown = m["series_breakdown"]
            else:
                # Consolida múltiplos envios (ex.: envio por série) no mesmo dia
                comp_reps = sum(s.completed_repetitions or 0 for s in day_sessions)
                val_reps = sum(s.valid_repetitions or 0 for s in day_sessions)
                inv_reps = sum(s.invalid_repetitions or 0 for s in day_sessions)
                tot_devs = sum(s.total_deviations or 0 for s in day_sessions)
                amp_med = round(float(np.mean([m["amplitude_media"] for m in metrics_list])), 1)
                amp_max = round(float(np.max([m["amplitude_maxima"] for m in metrics_list])), 1)
                cons_score = round(float(np.mean([m["consistencia_score"] for m in metrics_list])), 1)
                dor_score = round(float(np.max([m["dor_score_0_10"] for m in metrics_list])), 1)
                dor_pct = round(float(np.mean([m["dor_percentual_tempo"] for m in metrics_list])), 1)
                breakdown = []
                for s_i, m in enumerate(metrics_list, start=1):
                    first_b = (m["series_breakdown"] or [{}])[0]
                    breakdown.append({
                        **first_b,
                        "serie_index": s_i,
                        "label": f"Série {s_i}",
                    })

            risk_val = (
                primary.risk_classification.value
                if hasattr(primary.risk_classification, "value")
                else str(primary.risk_classification or "verde")
            ).lower()

            pt = ExerciseSessionPoint(
                session_id=primary.session_id,
                dia_tratamento=day_num,
                created_at=primary.created_at.isoformat() if primary.created_at else None,
                status="concluido",
                series_prescritas=day_item.series,
                repeticoes_por_serie=day_item.repeticoes,
                target_repetitions=day_item.series * day_item.repeticoes,
                completed_repetitions=comp_reps,
                valid_repetitions=val_reps,
                invalid_repetitions=inv_reps,
                total_deviations=tot_devs,
                amplitude_media=amp_med,
                amplitude_maxima=amp_max,
                consistencia_score=cons_score,
                compliance_score=round(float(primary.compliance_score or cons_score), 1),
                dor_score_0_10=dor_score,
                dor_percentual_tempo=dor_pct,
                risk_classification=risk_val,
                risk_symbol=RISK_SYMBOLS.get(risk_val, "●"),
                series_breakdown=breakdown,
                avaliado_fisioterapeuta=bool(primary.avaliado_fisioterapeuta),
            )
            session_points.append(pt)
            points_by_day.setdefault(day_num, []).append(pt)

        # Cálculo de deltas e tendências do exercício
        if session_points:
            first_pt = session_points[0]
            last_pt = session_points[-1]
            amp_ini = first_pt.amplitude_media
            amp_atu = last_pt.amplitude_media
            amp_delta = round(amp_atu - amp_ini, 1)
            amp_trend = "melhora" if amp_delta >= 3.0 else "piora" if amp_delta <= -3.0 else "estavel"

            cons_ini = first_pt.consistencia_score
            cons_atu = last_pt.consistencia_score
            cons_delta = round(cons_atu - cons_ini, 1)
            cons_trend = "melhora" if cons_delta >= 4.0 else "piora" if cons_delta <= -4.0 else "estavel"

            dor_ini = first_pt.dor_score_0_10
            dor_atu = last_pt.dor_score_0_10
            dor_delta = round(dor_atu - dor_ini, 1)
            # Para dor, redução (delta negativo) é melhora clínica!
            dor_trend = "melhora" if dor_delta <= -0.8 else "piora" if dor_delta >= 0.8 else "estavel"

            limite_dor = plano.dor_maxima_aceitavel if plano else 4
            if last_pt.dor_score_0_10 > limite_dor or last_pt.risk_classification == "critico":
                status_ex = "crit"
            elif last_pt.consistencia_score < 75.0 or amp_trend == "piora":
                status_ex = "warn"
            else:
                status_ex = "ok"

            resumo_ex = (
                f"Amplitude evoluiu de {amp_ini:.1f}° para {amp_atu:.1f}° ({amp_delta:+.1f}°); "
                f"consistência em {cons_atu:.1f}% ({cons_delta:+.1f} p.p.) e dor atual em {dor_atu:.1f}/10."
            )
        else:
            amp_ini = amp_atu = cons_ini = cons_atu = dor_ini = dor_atu = None
            amp_delta = cons_delta = dor_delta = 0.0
            amp_trend = cons_trend = dor_trend = "sem_dados"
            status_ex = "info"
            resumo_ex = "Nenhuma sessão concluída para este exercício até o momento."

        evolucao_por_exercicio.append(
            ExerciseEvolutionSeries(
                slot_id=slot_key,
                exercicio_id=item.exercicio_id,
                exercicio_nome=item.exercicio_nome,
                lado=item.lado or "auto",
                equipamento=item.equipamento,
                series_prescritas=item.series,
                repeticoes_por_serie=item.repeticoes,
                total_repeticoes_dia=item.series * item.repeticoes,
                dias_prescritos=prescribed_days,
                dias_executados=len(session_points),
                dias_previstos=len(prescribed_days) or dias_previstos,
                amplitude_inicial=amp_ini,
                amplitude_atual=amp_atu,
                amplitude_delta=amp_delta,
                amplitude_tendencia=amp_trend,
                consistencia_inicial=cons_ini,
                consistencia_atual=cons_atu,
                consistencia_delta=cons_delta,
                consistencia_tendencia=cons_trend,
                dor_inicial=dor_ini,
                dor_atual=dor_atu,
                dor_delta=dor_delta,
                dor_tendencia=dor_trend,
                status_evolucao=status_ex,
                resumo_exercicio=resumo_ex,
                sessoes=session_points,
            )
        )

    # 2. Construção da Matriz de Evolução por Dia de Tratamento (Dia 1..D)
    max_day_observed = max(points_by_day.keys(), default=0)
    total_days_grid = max(dias_previstos, max_day_observed)

    evolucao_por_dia: list[DayEvolutionSummary] = []
    for d in range(1, total_days_grid + 1):
        day_prescribed_items = [it for it in prescribed_items if it.applies_to_day(d)]
        total_ex_prescritos_dia = len(day_prescribed_items)
        total_reps_prescritas_dia = sum(it.series * it.repeticoes for it in day_prescribed_items)
        pts = points_by_day.get(d, [])
        if pts:
            amp_med_d = round(float(np.mean([p.amplitude_media for p in pts])), 1)
            amp_max_d = round(float(np.max([p.amplitude_maxima for p in pts])), 1)
            cons_med_d = round(float(np.mean([p.consistencia_score for p in pts])), 1)
            dor_med_d = round(float(np.mean([p.dor_score_0_10 for p in pts])), 1)
            dor_max_d = round(float(np.max([p.dor_score_0_10 for p in pts])), 1)
            reps_real = sum(p.completed_repetitions for p in pts)
            reps_val = sum(p.valid_repetitions for p in pts)
            devs_d = sum(p.total_deviations for p in pts)

            if any(p.risk_classification == "critico" for p in pts):
                risk_d = "critico"
            elif any(p.risk_classification == "atencao" for p in pts):
                risk_d = "atencao"
            else:
                risk_d = "verde"

            evolucao_por_dia.append(
                DayEvolutionSummary(
                    dia_tratamento=d,
                    label=f"Dia {d}",
                    exercicios_concluidos=len(pts),
                    exercicios_prescritos=total_ex_prescritos_dia,
                    total_repeticoes_prescritas=total_reps_prescritas_dia,
                    total_repeticoes_realizadas=reps_real,
                    total_repeticoes_validas=reps_val,
                    amplitude_media_dia=amp_med_d,
                    amplitude_maxima_dia=amp_max_d,
                    consistencia_media_dia=cons_med_d,
                    dor_media_dia_0_10=dor_med_d,
                    dor_maxima_dia_0_10=dor_max_d,
                    total_desvios_dia=devs_d,
                    risk_classification=risk_d,
                    risk_symbol=RISK_SYMBOLS.get(risk_d, "●"),
                    concluido=len(pts) >= max(1, total_ex_prescritos_dia),
                )
            )
        else:
            evolucao_por_dia.append(
                DayEvolutionSummary(
                    dia_tratamento=d,
                    label=f"Dia {d}",
                    exercicios_concluidos=0,
                    exercicios_prescritos=total_ex_prescritos_dia,
                    total_repeticoes_prescritas=total_reps_prescritas_dia,
                    concluido=False,
                )
            )

    # 3. KPIs Globais da Jornada e Parecer Clínico
    active_days = [day for day in evolucao_por_dia if day.exercicios_concluidos > 0]
    all_points = [pt for day_pts in points_by_day.values() for pt in day_pts]
    total_previstas = sum(day.exercicios_prescritos for day in evolucao_por_dia[:dias_previstos])
    if total_previstas <= 0:
        total_previstas = dias_previstos * max(1, len(prescribed_items))
    adesao = round(min(100.0, (len(all_points) / max(1, total_previstas)) * 100.0), 1)

    limite_dor = plano.dor_maxima_aceitavel if plano else 4
    dor_acima_count = sum(1 for pt in all_points if pt.dor_score_0_10 > limite_dor)

    if active_days:
        first_day = active_days[0]
        last_day = active_days[-1]

        g_amp_ini = first_day.amplitude_media_dia
        g_amp_atu = last_day.amplitude_media_dia
        g_amp_max = round(float(np.max([p.amplitude_maxima for p in all_points])), 1)
        g_amp_delta = round(g_amp_atu - g_amp_ini, 1)
        g_amp_trend = "melhora" if g_amp_delta >= 3.0 else "piora" if g_amp_delta <= -3.0 else "estavel"

        g_cons_ini = first_day.consistencia_media_dia
        g_cons_atu = last_day.consistencia_media_dia
        g_cons_med = round(float(np.mean([p.consistencia_score for p in all_points])), 1)
        g_cons_delta = round(g_cons_atu - g_cons_ini, 1)
        g_cons_trend = "melhora" if g_cons_delta >= 4.0 else "piora" if g_cons_delta <= -4.0 else "estavel"

        g_dor_ini = first_day.dor_maxima_dia_0_10
        g_dor_atu = last_day.dor_maxima_dia_0_10
        g_dor_max = round(float(np.max([p.dor_score_0_10 for p in all_points])), 1)
        g_dor_delta = round(g_dor_atu - g_dor_ini, 1)
        g_dor_trend = "melhora" if g_dor_delta <= -0.8 else "piora" if g_dor_delta >= 0.8 else "estavel"

        # Status de amplitude frente ao plano e laudo
        amp_status_plano = "ok"
        if plano and plano.amplitude_esperada_min is not None and g_amp_atu < plano.amplitude_esperada_min:
            amp_status_plano = "warn"

        amp_status_laudo = "ok"
        if laudo and laudo.limite_amplitude_max is not None and g_amp_max > laudo.limite_amplitude_max + 2.0:
            amp_status_laudo = "crit"

        if last_day.dor_maxima_dia_0_10 > limite_dor or amp_status_laudo == "crit":
            class_geral = "critico"
            label_geral = "Risco clínico na evolução"
        elif g_cons_atu < 78.0 or g_amp_trend == "piora" or g_dor_trend == "piora":
            class_geral = "atencao"
            label_geral = "Evolução requer atenção"
        else:
            class_geral = "verde"
            label_geral = "Evolução clínica favorável"
    else:
        g_amp_ini = g_amp_atu = g_amp_max = g_amp_delta = 0.0
        g_cons_ini = g_cons_atu = g_cons_med = g_cons_delta = 0.0
        g_dor_ini = g_dor_atu = g_dor_max = g_dor_delta = 0.0
        g_amp_trend = g_cons_trend = g_dor_trend = "sem_dados"
        amp_status_plano = amp_status_laudo = "info"
        class_geral = "atencao"
        label_geral = "Aguardando execução das sessões"

    metricas_globais = EvolutionGlobalMetrics(
        dias_previstos=dias_previstos,
        dias_concluidos=len(active_days),
        total_sessoes_concluidas=len(all_points),
        total_sessoes_previstas=total_previstas,
        percentual_adesao_plano=adesao,
        amplitude_inicial=g_amp_ini,
        amplitude_atual=g_amp_atu,
        amplitude_maxima_atingida=g_amp_max,
        amplitude_delta=g_amp_delta,
        amplitude_tendencia=g_amp_trend,
        amplitude_status_plano=amp_status_plano,
        amplitude_status_laudo=amp_status_laudo,
        consistencia_inicial=g_cons_ini,
        consistencia_atual=g_cons_atu,
        consistencia_media_global=g_cons_med,
        consistencia_delta=g_cons_delta,
        consistencia_tendencia=g_cons_trend,
        dor_inicial_0_10=g_dor_ini,
        dor_atual_0_10=g_dor_atu,
        dor_maxima_registrada_0_10=g_dor_max,
        dor_delta_0_10=g_dor_delta,
        dor_tendencia=g_dor_trend,
        dor_acima_limite_ocorrencias=dor_acima_count,
        classificacao_geral=class_geral,
        simbolo_geral=RISK_SYMBOLS.get(class_geral, "●"),
        label_geral=label_geral,
    )

    # 4. Geração do Parecer Clínico Explicável e Recomendações
    parecer: list[str] = []
    recomendacoes: list[str] = []

    if not active_days:
        parecer.append(
            "O paciente ainda não possui sessões concluídas no plano atual para análise longitudinal."
        )
        recomendacoes.append(
            "Orientar o paciente a enviar os vídeos do Dia 1 na tela 'Minha prescrição'."
        )
    else:
        parecer.append(
            f"Jornada de tratamento: {len(active_days)} de {dias_previstos} dia(s) realizado(s) "
            f"({len(all_points)} de {total_previstas} sessões de exercícios concluídas · {adesao:.0f}% de adesão)."
        )
        parecer.append(
            f"Amplitude Articular: evoluiu de {g_amp_ini:.1f}° (Dia {active_days[0].dia_tratamento}) "
            f"para {g_amp_atu:.1f}° (Dia {active_days[-1].dia_tratamento}), variação de {g_amp_delta:+.1f}° "
            f"(pico máximo registrado: {g_amp_max:.1f}°; faixa esperada do plano: "
            f"{plano.amplitude_esperada_texto if plano else '60 – 90'}°)."
        )
        parecer.append(
            f"Consistência Biomecânica entre Séries: passou de {g_cons_ini:.1f}% para {g_cons_atu:.1f}% "
            f"({g_cons_delta:+.1f} p.p.), refletindo a estabilidade postural ao longo das séries × repetições."
        )
        parecer.append(
            f"Nível de Dor Relatada: variou de {g_dor_ini:.1f}/10 no início para {g_dor_atu:.1f}/10 "
            f"na sessão mais recente ({g_dor_delta:+.1f} ponto(s); limite máximo aceitável do plano: {limite_dor}/10)."
        )

        if g_amp_trend == "melhora" and g_cons_atu >= 80.0 and g_dor_atu <= limite_dor:
            recomendacoes.append(
                "Indicadores sugerem evolução motora positiva com ganho de amplitude, controle de compensações "
                "entre as séries e dor dentro do limite seguro prescrito."
            )
        if dor_acima_count > 0:
            recomendacoes.append(
                f"Registrado(s) {dor_acima_count} episódio(s) de dor acima do limite ({limite_dor}/10) durante a jornada; "
                "recomenda-se revisar a carga/resistência antes de progredir o volume de séries."
            )
        if laudo and laudo.limite_amplitude_max is not None and g_amp_max > laudo.limite_amplitude_max:
            recomendacoes.append(
                f"Atenção: pico angular ({g_amp_max:.1f}°) aproximou-se ou excedeu o teto de segurança do laudo "
                f"({laudo.limite_amplitude_max:.0f}° para {laudo.lesao or 'a lesão'}). Reforçar instrução de controle de amplitude."
            )
        if not recomendacoes:
            recomendacoes.append(
                "Manter acompanhamento periódico das próximas sessões para consolidar a regularidade biomecânica."
            )

    return PatientEvolutionReportResponse(
        patient=patient,
        laudo=laudo,
        plano=plano,
        metricas_globais=metricas_globais,
        evolucao_por_dia=evolucao_por_dia,
        evolucao_por_exercicio=evolucao_por_exercicio,
        parecer_clinico=parecer,
        recomendacoes_plano=recomendacoes,
        alertas_paciente=alerts,
        avaliado_evolucao=bool(plano.avaliado_evolucao) if plano else False,
        observacoes_avaliacao_final=plano.observacoes_avaliacao_final if plano else None,
    )

