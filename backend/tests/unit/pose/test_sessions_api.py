"""Testes dos endpoints de API de sessões e eventos MongoDB."""

from fastapi.testclient import TestClient
import mongomock
import pytest

from infra.database import mongodb_client
from infra.database.repositories.event_repository import EventRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.event import EventDocument, EventType
from models.database.session import RiskClassification, SessionDocument, SessionStatus
from server import create_app
from services.pose.models import SessionSummary


@pytest.fixture
def mock_mongo():
    """Mock do cliente MongoDB para testes de API sem dependência de daemon ativo."""
    client = mongomock.MongoClient()
    mongodb_client.set_client(client)
    yield client
    mongodb_client.close_connection()


@pytest.fixture
def client(mock_mongo):
    app = create_app()
    return TestClient(app)


def test_list_and_get_sessions_endpoint(client, mock_mongo):
    db = mock_mongo["fiap-pos-ia-db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    event_repo = EventRepository(collection=db["eventos"])

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
    session = SessionDocument(
        session_id="sess_api_001",
        paciente_id="PAC-API-1",
        exercicio_id="FISIO-001",
        case_id="FISIO-001",
        side_evaluated="direito",
        risk_classification=RiskClassification.VERDE,
        compliance_score=100.0,
        summary=summary,
    )
    session_repo.save_session(session)

    # 1. GET /api/sessoes
    res = client.get("/api/sessoes")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["session_id"] == "sess_api_001"
    assert data[0]["paciente_id"] == "PAC-API-1"

    # 2. GET /api/sessoes/{id}
    res = client.get("/api/sessoes/sess_api_001")
    assert res.status_code == 200
    detail = res.json()
    assert detail["session_id"] == "sess_api_001"
    assert detail["compliance_score"] == 100.0

    # 3. GET /api/sessoes/inexistente -> 404
    res_404 = client.get("/api/sessoes/inexistente")
    assert res_404.status_code == 404


def test_get_session_events_endpoint(client, mock_mongo):
    db = mock_mongo["fiap-pos-ia-db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    event_repo = EventRepository(collection=db["eventos"])

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
    session = SessionDocument(
        session_id="sess_api_002",
        paciente_id="PAC-API-2",
        exercicio_id="FISIO-001",
        case_id="FISIO-001",
        side_evaluated="direito",
        compliance_score=100.0,
        summary=summary,
    )
    session_repo.save_session(session)

    events = [
        EventDocument(
            session_id="sess_api_002",
            tipo=EventType.REPETICAO,
            instante_inicio=1.0,
            instante_fim=2.0,
            valores={"index": 1, "is_valid": True},
        ),
        EventDocument(
            session_id="sess_api_002",
            tipo=EventType.DESVIO,
            instante_inicio=2.5,
            instante_fim=3.5,
            severidade="moderada",
            valores={"deviation_type": "compensacao_tronco"},
        ),
    ]
    event_repo.save_events(events)

    # Todos os eventos
    res = client.get("/api/sessoes/sess_api_002/eventos")
    assert res.status_code == 200
    evs = res.json()
    assert len(evs) == 2

    # Filtrados por tipo=desvio
    res_filter = client.get("/api/sessoes/sess_api_002/eventos?tipo=desvio")
    assert res_filter.status_code == 200
    dev_only = res_filter.json()
    assert len(dev_only) == 1
    assert dev_only[0]["tipo"] == "desvio"


def test_post_session_json_reference(client, mock_mongo, tmp_path):
    import cv2
    import numpy as np

    # Cria vídeo sintético
    video_path = tmp_path / "dummy.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (320, 240))
    for _ in range(30):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    # Disparo assíncrono (default, 202 Accepted)
    res_async = client.post(
        "/api/sessoes/referencia",
        json={
            "exercicio_id": "FISIO-001",
            "paciente_id": "PAC-JSON-1",
            "video_path": str(video_path),
            "side": "auto",
            "target_repetitions": 5,
        },
    )
    assert res_async.status_code == 202
    data = res_async.json()
    assert data["status"] == "processando"
    assert data["paciente_id"] == "PAC-JSON-1"
    session_id = data["session_id"]

    # Verifica se a sessão foi registrada no MongoDB
    db = mock_mongo["fiap-pos-ia-db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    saved = session_repo.get_session(session_id)
    assert saved is not None
    assert saved.status in (SessionStatus.PROCESSANDO, SessionStatus.CONCLUIDO)


def test_post_session_multipart_upload(client, mock_mongo, tmp_path):
    import cv2
    import numpy as np

    # Cria vídeo sintético para upload
    video_path = tmp_path / "upload_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (320, 240))
    for _ in range(15):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    with open(video_path, "rb") as f:
        file_bytes = f.read()

    # Upload multipart
    res = client.post(
        "/api/sessoes",
        data={
            "exercicio_id": "FISIO-001",
            "paciente_id": "PAC-UPLOAD-1",
            "side": "direito",
            "target_repetitions": "5",
        },
        files={"file": ("upload_test.mp4", file_bytes, "video/mp4")},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "processando"
    assert data["paciente_id"] == "PAC-UPLOAD-1"


def test_post_session_validation_error(client):
    # Sem arquivo nem referência
    res = client.post(
        "/api/sessoes/referencia",
        json={"exercicio_id": "FISIO-001"},
    )
    assert res.status_code == 400
    assert "É necessário enviar um arquivo de vídeo" in res.json()["detail"]


def test_list_reference_clips(client):
    res = client.get("/api/sessoes/clips-referencia")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Verifica que o clipe padrão FISIO-001 está presente
    clip_names = [c["filename"] for c in data]
    assert any("FISIO-001" in name for name in clip_names)
    first = data[0]
    assert "case_id" in first
    assert "exercicio_id" in first
    assert "exercicio_nome" in first
    assert "filename" in first
    assert "tipo" in first


def test_list_exercises_for_manual_upload(client):
    res = client.get("/api/sessoes/exercicios")
    assert res.status_code == 200
    data = res.json()
    assert [exercise["case_id"] for exercise in data] == [
        "FISIO-001",
        "FISIO-002",
        "FISIO-006",
        "FISIO-007",
    ]
    assert all(exercise["exercise_id"] for exercise in data)
    assert all(exercise["nome"] for exercise in data)


def test_create_session_rejects_unknown_exercise_before_video_resolution(client):
    res = client.post(
        "/api/sessoes",
        data={"exercicio_id": "FISIO-999"},
    )
    assert res.status_code == 422
    assert "Exercício não suportado" in res.json()["detail"]


def test_get_session_report(client, mock_mongo):
    from datetime import datetime, timezone

    session_repo = SessionRepository()
    event_repo = EventRepository()

    session_id = "REP-TEST-001"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = SessionDocument(
        session_id=session_id,
        paciente_id="PAC-TEST-REP",
        exercicio_id="KNEE_EXTENSION_SEATED",
        case_id="FISIO-001",
        side_evaluated="direito",
        status=SessionStatus.CONCLUIDO,
        etapa="relatorio_pronto",
        compliance_score=85.5,
        target_repetitions=5,
        valid_repetitions=4,
        invalid_repetitions=1,
        total_deviations=1,
        risk_classification=RiskClassification.ATENCAO,
        justificativas=["Desvio moderado de amplitude do joelho"],
        annotated_video_path="outputs/REP-TEST-001/pose/annotated.mp4",
        analysis_path="outputs/REP-TEST-001/pose/analysis.json",
        telemetry_path="outputs/REP-TEST-001/pose/telemetry.json",
        created_at=now_iso,
        updated_at=now_iso,
    )
    session_repo.save_session(doc)

    event_repo.save_events([
        EventDocument(
            session_id=session_id,
            tipo=EventType.REPETICAO,
            instante_inicio=0.5,
            instante_fim=2.6,
            instante_pico=1.5,
            duracao=2.1,
            valores={"index": 1, "is_valid": True, "peak_angle": 88.0},
            evidencia={"evidence_frame_path": "outputs/REP-TEST-001/pose/evidence/rep01_pico.jpg"},
            descricao="Repetição 1 (válida)",
        ),
        EventDocument(
            session_id=session_id,
            tipo=EventType.DESVIO,
            instante_inicio=1.5,
            instante_fim=2.0,
            duracao=0.5,
            valores={"deviation_type": "amplitude_reduzida", "repetition_index": 1},
            evidencia={"evidence_frame_path": "outputs/REP-TEST-001/pose/evidence/rep01_desvio.jpg"},
            descricao="Amplitude de joelho reduzida",
            severidade="moderada",
        ),
    ])

    res = client.get(f"/api/sessoes/{session_id}/relatorio")
    assert res.status_code == 200
    report = res.json()

    assert report["session_id"] == session_id
    assert report["paciente_id"] == "PAC-TEST-REP"
    assert report["exercicio_nome"] == "Extensão de joelho sentado"
    assert report["status"] == "concluido"
    assert report["compliance_score"] == 85.5
    assert report["risk_classification"] == "atencao"
    assert report["risk_symbol"] == "▲"
    assert report["total_deviations"] == 1
    assert report["annotated_video_url"] == "/media/outputs/REP-TEST-001/pose/annotated.mp4"
    assert len(report["evidence_urls"]) == 2
    assert report["evidence_urls"][0]["url"] == "/media/outputs/REP-TEST-001/pose/evidence/rep01_pico.jpg"
    assert report["aviso_legal"] == "Apoio à decisão, não diagnóstico."
    assert "comparacao_clinica" in report

