"""Sinks de resultado de análise de pose (File, MongoDB e Composto).

Permite que o pipeline processe a visão computacional de forma desacoplada
e grave os resultados em arquivos locais e/ou no MongoDB conforme o contrato do PRD.
"""

from abc import ABC, abstractmethod
import json
import logging
from pathlib import Path
from typing import Any, Optional

from config.media_paths import MediaStorage
from infra.database.repositories.alert_repository import AlertRepository
from infra.database.repositories.event_repository import EventRepository
from infra.database.repositories.medical_report_repository import MedicalReportRepository
from infra.database.repositories.patient_repository import PatientRepository
from infra.database.repositories.plan_repository import PlanRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.event import EventDocument, EventType
from models.database.session import RiskClassification, SessionDocument, SessionStatus
from services.audio_transcription import SpeechSegment
from services.evolution_service import (
    compute_session_evolution_metrics,
    generate_alerts_for_session,
)
from services.pose.models import DeviationSeverity, ExerciseAnalysisResult

logger = logging.getLogger(__name__)


def classify_session_risk(result: ExerciseAnalysisResult) -> tuple[RiskClassification, list[str]]:
    """Calcula a classificação de risco clínico e gera justificativas explicáveis."""
    justifications: list[str] = []
    has_grave = any(d.severity == DeviationSeverity.GRAVE for d in result.deviations)
    has_moderada = any(d.severity == DeviationSeverity.MODERADA for d in result.deviations)
    has_leve = any(d.severity == DeviationSeverity.LEVE for d in result.deviations)
    score = result.session_summary.compliance_score

    # Avaliação por desvios posturais
    if has_grave:
        risk = RiskClassification.CRITICO
        justifications.append("Detectado desvio postural de severidade grave durante o exercício.")
    elif score < 50.0:
        risk = RiskClassification.CRITICO
        justifications.append(f"Score de conformidade crítico ({score:.1f}% abaixo do limite mínimo de 50%).")
    elif has_moderada or has_leve or score < 80.0:
        risk = RiskClassification.ATENCAO
        if has_moderada or has_leve:
            types = sorted({d.deviation_type for d in result.deviations})
            justifications.append(f"Detectados desvios posturais ({', '.join(types)}) que exigem atenção.")
        if score < 80.0:
            justifications.append(f"Score de conformidade em nível de atenção ({score:.1f}%).")
    else:
        risk = RiskClassification.VERDE
        justifications.append(f"Exercício executado com alta conformidade biomecânica ({score:.1f}%).")

    # Informações complementares de contexto
    s = result.session_summary
    target = s.target_repetitions or 0
    if target > 0:
        if s.completed_repetitions >= target:
            justifications.append(f"Meta de repetições atingida ({s.completed_repetitions}/{target}).")
        else:
            justifications.append(f"Meta de repetições incompleta ({s.completed_repetitions}/{target}).")

    if s.frames_without_pose > 0:
        justifications.append(
            f"Presença de {s.frames_without_pose} frames sem rastreamento de pose identificado."
        )

    return risk, justifications


class ResultSink(ABC):
    """Contrato base para sinks de persistência de análise."""

    @abstractmethod
    def save(
        self,
        result: ExerciseAnalysisResult,
        run_id: str,
        video_path: Optional[str] = None,
        paciente_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Salva os resultados da análise."""
        pass


class FileResultSink(ResultSink):
    """Grava os resultados em arquivos locais (analysis.json e telemetry.json)."""

    def __init__(self, media_storage: Optional[MediaStorage] = None):
        self.storage = media_storage or MediaStorage.from_env()

    def save(
        self,
        result: ExerciseAnalysisResult,
        run_id: str,
        video_path: Optional[str] = None,
        paciente_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        analysis_json_path = self.storage.analysis_json(run_id)
        with open(analysis_json_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        telemetry_json_path = self.storage.telemetry_json(run_id)
        with open(telemetry_json_path, "w", encoding="utf-8") as f:
            json.dump([pt.model_dump() for pt in result.telemetry], f, indent=2)

        logger.info("Artefatos JSON gravados em disco para run_id=%s.", run_id)
        return {
            "analysis_json_path": str(analysis_json_path),
            "telemetry_json_path": str(telemetry_json_path),
            "analysis_relative_path": self.storage.relative(analysis_json_path),
            "telemetry_relative_path": self.storage.relative(telemetry_json_path),
        }


class MongoResultSink(ResultSink):
    """Persiste o resumo da sessão e eventos biomecânicos no MongoDB (coleções 'sessoes' e 'eventos')."""

    def __init__(
        self,
        session_repository: Optional[SessionRepository] = None,
        event_repository: Optional[EventRepository] = None,
        media_storage: Optional[MediaStorage] = None,
    ):
        self.session_repo = session_repository or SessionRepository()
        self.event_repo = event_repository or EventRepository()
        self.storage = media_storage or MediaStorage.from_env()

    def save(
        self,
        result: ExerciseAnalysisResult,
        run_id: str,
        video_path: Optional[str] = None,
        paciente_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        risk, justifications = classify_session_risk(result)

        # Resolução de caminhos relativos
        relative_video_path = None
        if video_path:
            try:
                relative_video_path = self.storage.relative(Path(video_path))
            except Exception:
                relative_video_path = str(video_path)

        analysis_rel = None
        telemetry_rel = None
        try:
            analysis_p = self.storage.analysis_json(run_id)
            if analysis_p.exists():
                analysis_rel = self.storage.relative(analysis_p)
            telemetry_p = self.storage.telemetry_json(run_id)
            if telemetry_p.exists():
                telemetry_rel = self.storage.relative(telemetry_p)
        except Exception:
            pass

        # Preserva metadados cadastrais/slot previamente registrados na criação da sessão
        existing_session = None
        try:
            existing_session = self.session_repo.get_session(run_id)
        except Exception:
            existing_session = None

        merged_extra = dict(existing_session.extra if existing_session and existing_session.extra else {})
        merged_extra.update(result.extra or {})

        resolved_paciente_id = paciente_id or (existing_session.paciente_id if existing_session else None)
        resolved_slot_id = kwargs.get("slot_id") or (existing_session.slot_id if existing_session else None)
        resolved_dia = int(
            kwargs.get("dia_tratamento")
            or (existing_session.dia_tratamento if existing_session else 1)
            or 1
        )
        resolved_series = int(
            kwargs.get("series_prescritas")
            or (existing_session.series_prescritas if existing_session else 1)
            or 1
        )
        resolved_reps_serie = int(
            kwargs.get("repeticoes_por_serie")
            or (existing_session.repeticoes_por_serie if existing_session else None)
            or result.session_summary.target_repetitions
            or 5
        )
        resolved_serie_index = (
            kwargs.get("serie_index")
            if kwargs.get("serie_index") is not None
            else (existing_session.serie_index if existing_session else None)
        )

        speech_segments = kwargs.get("speech_segments", [])
        evo_metrics = compute_session_evolution_metrics(
            result=result,
            speech_segments=speech_segments,
            series_prescritas=resolved_series,
            repeticoes_por_serie=resolved_reps_serie,
        )

        # Criação do documento da sessão
        session_doc = SessionDocument(
            session_id=run_id,
            paciente_id=resolved_paciente_id,
            slot_id=resolved_slot_id,
            dia_tratamento=resolved_dia,
            series_prescritas=resolved_series,
            repeticoes_por_serie=resolved_reps_serie,
            serie_index=resolved_serie_index,
            exercicio_id=result.session_summary.exercise_id,
            case_id=result.session_summary.case_id,
            side_evaluated=result.session_summary.side_evaluated,
            lgpd_aceite=(
                kwargs["lgpd_aceite"]
                if "lgpd_aceite" in kwargs
                else (existing_session.lgpd_aceite if existing_session else True)
            ),
            original_filename=(
                kwargs.get("original_filename")
                or (existing_session.original_filename if existing_session else None)
            ),
            file_size_bytes=(
                kwargs.get("file_size_bytes")
                if kwargs.get("file_size_bytes") is not None
                else (existing_session.file_size_bytes if existing_session else None)
            ),
            status=SessionStatus.CONCLUIDO,
            etapa="pose_concluida",
            risk_classification=risk,
            video_path=relative_video_path,
            annotated_video_path=result.annotated_video_path,
            analysis_path=analysis_rel,
            telemetry_path=telemetry_rel,
            compliance_score=result.session_summary.compliance_score,
            amplitude_maxima=evo_metrics["amplitude_maxima"],
            amplitude_media=evo_metrics["amplitude_media"],
            consistencia_score=evo_metrics["consistencia_score"],
            dor_score_0_10=evo_metrics["dor_score_0_10"],
            dor_percentual_tempo=evo_metrics["dor_percentual_tempo"],
            series_breakdown=evo_metrics["series_breakdown"],
            avaliado_fisioterapeuta=(
                existing_session.avaliado_fisioterapeuta if existing_session else False
            ),
            target_repetitions=result.session_summary.target_repetitions,
            completed_repetitions=result.session_summary.completed_repetitions,
            valid_repetitions=result.session_summary.valid_repetitions,
            invalid_repetitions=result.session_summary.invalid_repetitions,
            total_deviations=len(result.deviations),
            summary=result.session_summary,
            justificativas=justifications,
            created_at=existing_session.created_at if existing_session else SessionDocument.model_fields["created_at"].default_factory(),
            extra=merged_extra,
        )

        # Mapeamento dos eventos de repetição
        events: list[EventDocument] = []
        for rep in result.repetitions:
            events.append(
                EventDocument(
                    session_id=run_id,
                    tipo=EventType.REPETICAO,
                    instante_inicio=rep.start_time,
                    instante_fim=rep.end_time,
                    instante_pico=rep.peak_time,
                    duracao=rep.duration,
                    valores={
                        "repetition_index": rep.index,
                        "peak_angle": rep.peak_angle,
                        "peak_progress": rep.peak_progress,
                        "completed": rep.completed,
                        "is_valid": rep.is_valid,
                        "deviations": rep.deviations,
                    },
                    evidencia={},
                    descricao=f"Repetição {rep.index} ({'válida' if rep.is_valid else 'com desvios'})",
                )
            )

        # Mapeamento dos eventos de desvio
        for dev in result.deviations:
            events.append(
                EventDocument(
                    session_id=run_id,
                    tipo=EventType.DESVIO,
                    instante_inicio=dev.start_time,
                    instante_fim=dev.end_time,
                    duracao=max(0.0, dev.end_time - dev.start_time),
                    valores={
                        "deviation_type": dev.deviation_type,
                        "repetition_index": dev.repetition_index,
                        "start_frame": dev.start_frame,
                        "end_frame": dev.end_frame,
                        "evidence_frame": dev.evidence_frame,
                    },
                    evidencia={
                        "evidence_frame_path": dev.evidence_frame_path,
                        "evidence_frame": dev.evidence_frame,
                    },
                    descricao=dev.description,
                    severidade=dev.severity.value,
                )
            )

        speech_segments = kwargs.get("speech_segments", [])
        for segment in speech_segments:
            if not isinstance(segment, SpeechSegment):
                raise TypeError("speech_segments deve conter objetos SpeechSegment.")
            events.append(
                EventDocument(
                    session_id=run_id,
                    tipo=EventType.FALA_DOR,
                    instante_inicio=segment.start_seconds,
                    instante_fim=segment.end_seconds,
                    duracao=max(0.0, segment.end_seconds - segment.start_seconds),
                    valores={
                        "nivel": segment.nivel,
                        "score": segment.score,
                        "timestamp": segment.timestamp,
                    },
                    evidencia={"transcricao": segment.texto},
                    descricao=segment.texto,
                )
            )

        events.sort(key=lambda event: event.instante_inicio)

        # Persistência via repositórios
        saved_session_id = self.session_repo.save_session(session_doc)
        inserted_events = self.event_repo.save_events(events)

        # Geração automática de alertas clínicos na coleção 'alertas' quando aplicável
        try:
            if session_doc.paciente_id:
                patient_doc = PatientRepository().get_patient(session_doc.paciente_id)
                plan_doc = PlanRepository().get_plan_by_patient(session_doc.paciente_id)
                report_doc = MedicalReportRepository().get_report_by_patient(session_doc.paciente_id)
                generated_alerts = generate_alerts_for_session(
                    session=session_doc,
                    paciente_nome=patient_doc.nome if patient_doc else session_doc.paciente_id,
                    plano=plan_doc,
                    laudo=report_doc,
                )
                alert_repo = AlertRepository()
                for alt in generated_alerts:
                    alert_repo.save_alert(alt)
        except Exception as exc:
            logger.warning("Não foi possível registrar alertas automáticos para run_id=%s: %s", run_id, exc)

        logger.info(
            "MongoDB: Sessão %s persistida com classificação %s e %d eventos associados.",
            saved_session_id,
            risk.value,
            inserted_events,
        )

        return {
            "session_id": saved_session_id,
            "risk_classification": risk.value,
            "events_saved": inserted_events,
            "justificativas": justifications,
        }


class CompositeResultSink(ResultSink):
    """Executa múltiplos ResultSinks em cadeia sequencial."""

    def __init__(self, sinks: list[ResultSink]):
        if not sinks:
            raise ValueError("CompositeResultSink requer pelo menos um ResultSink.")
        self.sinks = sinks

    def save(
        self,
        result: ExerciseAnalysisResult,
        run_id: str,
        video_path: Optional[str] = None,
        paciente_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        combined_output: dict[str, Any] = {}
        for sink in self.sinks:
            output = sink.save(
                result=result,
                run_id=run_id,
                video_path=video_path,
                paciente_id=paciente_id,
                **kwargs,
            )
            if isinstance(output, dict):
                combined_output.update(output)
        return combined_output
