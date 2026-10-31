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
