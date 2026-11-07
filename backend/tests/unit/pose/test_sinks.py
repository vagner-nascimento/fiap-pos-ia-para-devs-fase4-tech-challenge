"""Testes unitários dos ResultSinks e repositórios MongoDB (Passo 2)."""

from datetime import datetime
import json
from pathlib import Path
import tempfile

import mongomock
import pytest

from config.media_paths import MediaStorage
from infra.database.repositories.event_repository import EventRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.event import EventType
from models.database.session import RiskClassification, SessionDocument, SessionStatus
from services.pose.models import (
    DeviationEvent,
    DeviationSeverity,
    ExerciseAnalysisResult,
    RepetitionEvent,
    SessionSummary,
    TelemetryPoint,
)
from services.pose.sinks import (
    CompositeResultSink,
    FileResultSink,
    MongoResultSink,
    classify_session_risk,
)


@pytest.fixture
def sample_result() -> ExerciseAnalysisResult:
    """Fixture com resultado de análise representativo do FISIO-001."""
    summary = SessionSummary(
        exercise_id="FISIO-001",
        case_id="FISIO-001",
        side_evaluated="direito",
        target_repetitions=5,
        completed_repetitions=5,
        valid_repetitions=4,
        invalid_repetitions=1,
        duration_seconds=10.0,
        fps=30.0,
        total_frames=300,
        frames_without_pose=2,
        compliance_score=80.0,
        status="concluido",
    )
    repetitions = [
        RepetitionEvent(
            index=1,
            start_time=1.0,
            peak_time=2.0,
            end_time=3.0,
            duration=2.0,
            peak_angle=165.0,
            peak_progress=1.0,
            completed=True,
            is_valid=True,
        ),
        RepetitionEvent(
            index=2,
            start_time=3.5,
            peak_time=4.5,
            end_time=5.5,
            duration=2.0,
            peak_angle=140.0,
            peak_progress=0.75,
            completed=True,
            is_valid=False,
            deviations=["amplitude_reduzida"],
        ),
    ]
    deviations = [
        DeviationEvent(
            deviation_type="amplitude_reduzida",
            severity=DeviationSeverity.MODERADA,
            repetition_index=2,
            start_time=3.5,
            end_time=5.5,
            start_frame=105,
            end_frame=165,
            evidence_frame=135,
            evidence_frame_path="outputs/run_test/pose/evidence/rep02_amplitude_reduzida.jpg",
            description="Extensão incompleta do joelho direito.",
        )
    ]
    telemetry = [
        TelemetryPoint(timestamp=1.0, progress=0.0, phase="repouso", metrics={"knee_angle": 90.0}),
        TelemetryPoint(timestamp=2.0, progress=1.0, phase="pico", metrics={"knee_angle": 165.0}),
    ]
    return ExerciseAnalysisResult(
        session_summary=summary,
        repetitions=repetitions,
        deviations=deviations,
        telemetry=telemetry,
        annotated_video_path="outputs/run_test/pose/annotated.mp4",
    )


def test_classify_session_risk_green():
    summary = SessionSummary(
        exercise_id="FISIO-001",
        case_id="FISIO-001",
        side_evaluated="direito",
        target_repetitions=5,
        completed_repetitions=5,
        valid_repetitions=5,
        invalid_repetitions=0,
        duration_seconds=10.0,
        fps=30.0,
        total_frames=300,
        frames_without_pose=0,
        compliance_score=100.0,
        status="concluido",
    )
    result = ExerciseAnalysisResult(session_summary=summary, repetitions=[], deviations=[], telemetry=[])
    risk, justs = classify_session_risk(result)
    assert risk == RiskClassification.VERDE
    assert any("alta conformidade" in j for j in justs)


def test_classify_session_risk_atencao(sample_result):
    risk, justs = classify_session_risk(sample_result)
    assert risk == RiskClassification.ATENCAO
    assert any("amplitude_reduzida" in j for j in justs)


def test_classify_session_risk_critico(sample_result):
    sample_result.deviations[0].severity = DeviationSeverity.GRAVE
    risk, justs = classify_session_risk(sample_result)
    assert risk == RiskClassification.CRITICO
    assert any("severidade grave" in j for j in justs)


def test_file_result_sink(tmp_path: Path, sample_result: ExerciseAnalysisResult):
    storage = MediaStorage(media_root=tmp_path)
    sink = FileResultSink(media_storage=storage)

    out = sink.save(result=sample_result, run_id="run_123")
    assert "analysis_json_path" in out
    assert Path(out["analysis_json_path"]).exists()
    assert Path(out["telemetry_json_path"]).exists()

    with open(out["analysis_json_path"], encoding="utf-8") as f:
        data = json.load(f)
    assert data["session_summary"]["exercise_id"] == "FISIO-001"
    assert len(data["deviations"]) == 1


def test_mongo_result_sink(tmp_path: Path, sample_result: ExerciseAnalysisResult):
    storage = MediaStorage(media_root=tmp_path)
    mock_client = mongomock.MongoClient()
    db = mock_client["test_db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    event_repo = EventRepository(collection=db["eventos"])

    sink = MongoResultSink(
        session_repository=session_repo,
        event_repository=event_repo,
        media_storage=storage,
    )

    out = sink.save(
        result=sample_result,
        run_id="run_mongo_1",
        video_path="inputs/sessions/s1/original.mp4",
        paciente_id="PAC-001",
    )

    assert out["session_id"] == "run_mongo_1"
    assert out["risk_classification"] == RiskClassification.ATENCAO.value
    assert out["events_saved"] == 3  # 2 repetitions + 1 deviation

    # Verifica sessão salva no repositório
    saved_session = session_repo.get_session("run_mongo_1")
    assert saved_session is not None
    assert saved_session.paciente_id == "PAC-001"
    assert saved_session.exercicio_id == "FISIO-001"
    assert saved_session.compliance_score == 80.0
    assert saved_session.status == SessionStatus.CONCLUIDO
    assert len(saved_session.justificativas) > 0

    # Verifica eventos salvos
    events = event_repo.list_events_by_session("run_mongo_1")
    assert len(events) == 3

    rep_events = [e for e in events if e.tipo == EventType.REPETICAO]
    assert len(rep_events) == 2
    assert rep_events[0].valores["peak_angle"] == 165.0
    assert rep_events[1].valores["is_valid"] is False

    dev_events = [e for e in events if e.tipo == EventType.DESVIO]
    assert len(dev_events) == 1
    assert dev_events[0].severidade == "moderada"
    assert dev_events[0].valores["deviation_type"] == "amplitude_reduzida"
    assert dev_events[0].evidencia["evidence_frame_path"] is not None


def test_composite_result_sink(tmp_path: Path, sample_result: ExerciseAnalysisResult):
    storage = MediaStorage(media_root=tmp_path)
    mock_client = mongomock.MongoClient()
    db = mock_client["test_db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    event_repo = EventRepository(collection=db["eventos"])

    file_sink = FileResultSink(media_storage=storage)
    mongo_sink = MongoResultSink(
        session_repository=session_repo,
        event_repository=event_repo,
        media_storage=storage,
    )

    composite = CompositeResultSink([file_sink, mongo_sink])
    out = composite.save(result=sample_result, run_id="run_composite")

    # Arquivos em disco gerados
    assert Path(out["analysis_json_path"]).exists()
    assert Path(out["telemetry_json_path"]).exists()

    # Documentos MongoDB gerados
    assert out["session_id"] == "run_composite"
    assert session_repo.get_session("run_composite") is not None
    assert len(event_repo.list_events_by_session("run_composite")) == 3


def test_session_repository_crud():
    mock_client = mongomock.MongoClient()
    collection = mock_client["test_db"]["sessoes"]
    repo = SessionRepository(collection=collection)

    summary = SessionSummary(
        exercise_id="FISIO-001",
        case_id="FISIO-001",
        side_evaluated="direito",
        target_repetitions=5,
        completed_repetitions=5,
        valid_repetitions=5,
        invalid_repetitions=0,
        duration_seconds=10.0,
        fps=30.0,
        total_frames=300,
        frames_without_pose=0,
        compliance_score=100.0,
        status="concluido",
    )
    doc = SessionDocument(
        session_id="sess_101",
        paciente_id="PAC-99",
        exercicio_id="FISIO-001",
        case_id="FISIO-001",
        side_evaluated="direito",
        compliance_score=100.0,
        summary=summary,
    )

    # Save
    repo.save_session(doc)

    # Get
    retrieved = repo.get_session("sess_101")
    assert retrieved is not None
    assert retrieved.paciente_id == "PAC-99"

    # List
    sessions = repo.list_sessions(paciente_id="PAC-99")
    assert len(sessions) == 1

    # Update status
    updated = repo.update_status("sess_101", SessionStatus.CONCLUIDO, etapa="relatorio_gerado")
    assert updated is True
    assert repo.get_session("sess_101").etapa == "relatorio_gerado"

    # Delete
    deleted = repo.delete_session("sess_101")
    assert deleted is True
    assert repo.get_session("sess_101") is None


def test_mongo_result_sink_preserves_slot_and_file_metadata(
    tmp_path: Path, sample_result: ExerciseAnalysisResult
):
    storage = MediaStorage(media_root=tmp_path)
    mock_client = mongomock.MongoClient()
    db = mock_client["test_db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    event_repo = EventRepository(collection=db["eventos"])

    # Simula registro inicial criado no POST /api/sessoes (status processando)
    session_repo.save_session(
        SessionDocument(
            session_id="run_slot_preserve",
            paciente_id="PAC-001",
            slot_id="SLOT-1",
            exercicio_id="FISIO-001",
            case_id="FISIO-001",
            side_evaluated="direito",
            lgpd_aceite=True,
            original_filename="gravacao_paciente.mp4",
            file_size_bytes=50331648,
            status=SessionStatus.PROCESSANDO,
        )
    )

    sink = MongoResultSink(
        session_repository=session_repo,
        event_repository=event_repo,
        media_storage=storage,
    )
    sink.save(
        result=sample_result,
        run_id="run_slot_preserve",
        video_path="inputs/sessions/run_slot_preserve/original.mp4",
        paciente_id="PAC-001",
    )

    final_doc = session_repo.get_session("run_slot_preserve")
    assert final_doc is not None
    assert final_doc.status == SessionStatus.CONCLUIDO
    assert final_doc.slot_id == "SLOT-1"
    assert final_doc.lgpd_aceite is True
    assert final_doc.original_filename == "gravacao_paciente.mp4"
    assert final_doc.file_size_bytes == 50331648

