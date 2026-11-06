"""Testes unitários e de API para cadastro de pacientes, laudos médicos e planos de prescrição (Issue #3)."""

from fastapi.testclient import TestClient
import mongomock
import pytest

from infra.database import mongodb_client
from infra.database.repositories.session_repository import SessionRepository
from models.database.session import RiskClassification, SessionDocument, SessionStatus
from server import create_app
from services.clinical_extractor import extract_medical_report_entities, parse_amplitude_range


@pytest.fixture
def mock_mongo():
    """Mock do cliente MongoDB para testes sem necessidade de daemon ativo."""
    client = mongomock.MongoClient()
    mongodb_client.set_client(client)
    yield client
    mongodb_client.close_connection()


@pytest.fixture
def client(mock_mongo):
    app = create_app()
    return TestClient(app)


# -------------------------------------------------------------------------
# 1. Testes do Extrator Determinístico de Laudos Clínicos
# -------------------------------------------------------------------------

def test_extract_medical_report_entities_shoulder_tendinopathy():
    texto = "Tendinopatia de ombro direito. Evitar elevação acima de 90° sem controle."
    info = extract_medical_report_entities(texto)
    assert info.regiao == "ombro direito"
    assert info.lesao == "tendinopatia"
    assert "elevação > 90°" in info.movimentos_restritos
    assert info.limite_amplitude_max == 90.0


def test_extract_medical_report_entities_knee_lca():
    texto = "Pós-LCA no joelho esquerdo. Evitar extensão forçada com dor na região do joelho."
    info = extract_medical_report_entities(texto)
    assert info.regiao == "joelho esquerdo"
    assert info.lesao == "pós-LCA"
    assert "extensão forçada" in info.movimentos_restritos


def test_extract_medical_report_entities_lumbar_and_elbow():
    info_lombar = extract_medical_report_entities(
        "Quadro de lombalgia em coluna lombar e pelve. Restrito: rotação lombar ampla."
    )
    assert info_lombar.regiao == "coluna lombar e pelve"
    assert info_lombar.lesao == "lombalgia"
    assert "rotação lombar ampla sob carga" in info_lombar.movimentos_restritos

    info_cotovelo = extract_medical_report_entities(
        "Epicondilite lateral em cotovelo direito. Evitar flexão acima de 130 graus e carga acima do limite."
    )
    assert info_cotovelo.regiao == "cotovelo direito"
    assert info_cotovelo.lesao == "epicondilite lateral"
    assert info_cotovelo.limite_amplitude_max == 130.0
    assert "flexão > 130°" in info_cotovelo.movimentos_restritos
    assert "carga acima do limite" in info_cotovelo.movimentos_restritos


def test_parse_amplitude_range():
    assert parse_amplitude_range("60 – 90") == (60.0, 90.0)
    assert parse_amplitude_range("150 a 180 graus") == (150.0, 180.0)
    assert parse_amplitude_range("90") == (None, 90.0)
    assert parse_amplitude_range("") == (None, None)


# -------------------------------------------------------------------------
# 2. Testes dos Endpoints REST de Pacientes, Laudos e Planos
# -------------------------------------------------------------------------

def test_seed_and_list_patients(client):
    res = client.get("/api/pacientes")
    assert res.status_code == 200
    patients = res.json()
    assert len(patients) >= 4
    ids = [p["paciente_id"] for p in patients]
    assert "PAC-001" in ids

    # Filtro por nome (?nome=Marina)
    res_filtered = client.get("/api/pacientes?nome=Marina")
    assert res_filtered.status_code == 200
    filtered = res_filtered.json()
    assert len(filtered) == 1
    assert filtered[0]["paciente_id"] == "PAC-001"
    assert filtered[0]["nome"] == "Marina T."


def test_create_new_patient_and_get_bundle(client):
    res = client.post(
        "/api/pacientes",
        json={
            "paciente_id": "PAC-010",
            "nome": "Lucas B.",
            "idade": 29,
            "observacoes": "Paciente sintético de teste",
        },
    )
    assert res.status_code == 201
    created = res.json()
    assert created["paciente_id"] == "PAC-010"
    assert created["nome"] == "Lucas B."
    assert created["synthetic"] is True

    bundle_res = client.get("/api/pacientes/PAC-010")
    assert bundle_res.status_code == 200
    bundle = bundle_res.json()
    assert bundle["patient"]["nome"] == "Lucas B."
    assert bundle["laudo"] is None
    assert bundle["plano"] is None


def test_extract_preview_endpoint(client):
    res = client.post(
        "/api/pacientes/laudo/extrair",
        json={
            "texto_original": "Tendinopatia de ombro direito. Evitar elevação acima de 90° sem controle."
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["regiao"] == "ombro direito"
    assert data["lesao"] == "tendinopatia"
    assert "elevação > 90°" in data["movimentos_restritos"]
    assert data["limite_amplitude_max"] == 90.0


def test_save_and_get_medical_report_with_auto_extraction_and_manual_override(client):
    # 1. Salvando apenas com texto livre (extração automática)
    res = client.post(
        "/api/pacientes/PAC-010/laudo",
        json={
            "texto_original": "Osteoartrite no joelho direito. Evitar extensão acima de 165° e compensação de tronco."
        },
    )
    assert res.status_code == 200
    laudo = res.json()
    assert laudo["paciente_id"] == "PAC-010"
    assert laudo["regiao"] == "joelho direito"
    assert laudo["lesao"] == "osteoartrite"
    assert "extensão > 165°" in laudo["movimentos_restritos"]
    assert laudo["limite_amplitude_max"] == 165.0

    # 2. Atualizando com revisão manual do fisioterapeuta
    res_override = client.post(
        "/api/pacientes/PAC-010/laudo",
        json={
            "texto_original": "Osteoartrite no joelho direito. Evitar extensão acima de 165°.",
            "regiao": "joelho direito (revisado)",
            "lesao": "gonartrose leve",
            "movimentos_restritos": ["extensão > 160°", "carga externa"],
            "limite_amplitude_max": 160.0,
            "revisado_profissional": True,
        },
    )
    assert res_override.status_code == 200
    updated = res_override.json()
    assert updated["regiao"] == "joelho direito (revisado)"
    assert updated["lesao"] == "gonartrose leve"
    assert updated["movimentos_restritos"] == ["extensão > 160°", "carga externa"]
    assert updated["revisado_profissional"] is True

    get_res = client.get("/api/pacientes/PAC-010/laudo")
    assert get_res.status_code == 200
    assert get_res.json()["lesao"] == "gonartrose leve"


def test_save_and_get_plan_with_validation(client):
    # Salva plano com 2 exercícios prescritos
    res = client.post(
        "/api/pacientes/PAC-010/plano",
        json={
            "dor_maxima_aceitavel": 4,
            "amplitude_esperada_texto": "60 – 90",
            "exercicios": [
                {
                    "exercicio_id": "FISIO-006",
                    "series": 3,
                    "repeticoes": 10,
                    "lado": "direito",
                    "instrucoes": "Manter tronco alinhado",
                },
                {
                    "exercicio_id": "FISIO-005",
                    "series": 3,
                    "repeticoes": 8,
                },
            ],
        },
    )
    assert res.status_code == 200
    plano = res.json()
    assert plano["paciente_id"] == "PAC-010"
    assert plano["dor_maxima_aceitavel"] == 4
    assert plano["amplitude_esperada_min"] == 60.0
    assert plano["amplitude_esperada_max"] == 90.0
    assert len(plano["exercicios"]) == 2
    assert plano["exercicios"][0]["slot_id"] == "SLOT-1"
    assert plano["exercicios"][0]["exercicio_id"] == "FISIO-006"
    assert plano["exercicios"][0]["equipamento"] == "faixa elástica leve"
    assert plano["exercicios"][1]["slot_id"] == "SLOT-2"
    assert plano["exercicios"][1]["exercicio_id"] == "FISIO-005"

    # Consulta plano
    get_res = client.get("/api/pacientes/PAC-010/plano")
    assert get_res.status_code == 200
    assert len(get_res.json()["exercicios"]) == 2

    # Exercício inválido deve retornar 422
    bad_res = client.post(
        "/api/pacientes/PAC-010/plano",
        json={
            "dor_maxima_aceitavel": 4,
            "amplitude_esperada_texto": "60 – 90",
            "exercicios": [{"exercicio_id": "FISIO-999", "series": 3, "repeticoes": 10}],
        },
    )
    assert bad_res.status_code == 422


def test_list_clinical_exercise_catalog_returns_all_7_exercises(client):
    res = client.get("/api/pacientes/catalogo-exercicios")
    assert res.status_code == 200
    catalog = res.json()
    assert len(catalog) == 7
    assert [c["case_id"] for c in catalog] == [
        "FISIO-001",
        "FISIO-002",
        "FISIO-003",
        "FISIO-004",
        "FISIO-005",
        "FISIO-006",
        "FISIO-007",
    ]


def test_session_report_integrates_with_patient_plan_and_laudo(client):
    # Garante seed de PAC-001 (Marina T.)
    client.get("/api/pacientes")

    session_repo = SessionRepository()
    session_repo.save_session(
        SessionDocument(
            session_id="SESS-MARINA-01",
            paciente_id="PAC-001",
            exercicio_id="FISIO-006",
            case_id="FISIO-006",
            side_evaluated="direito",
            status=SessionStatus.CONCLUIDO,
            compliance_score=92.0,
            total_deviations=0,
            risk_classification=RiskClassification.VERDE,
        )
    )

    res = client.get("/api/sessoes/SESS-MARINA-01/relatorio")
    assert res.status_code == 200
    report = res.json()
    assert "Dor máx: 4/10" in report["comparacao_clinica"]["plano"]["label"]
    assert "tendinopatia" in report["comparacao_clinica"]["laudo"]["label"]


# -------------------------------------------------------------------------
# 3. Testes de Busca pelo Paciente e Sessões da Prescrição (Issue #4)
# -------------------------------------------------------------------------

def test_search_patients_accent_insensitive_and_by_id(client):
    # Busca sem acento deve encontrar "Cláudia M." (PAC-003)
    res_no_accent = client.get("/api/pacientes?nome=claudia")
    assert res_no_accent.status_code == 200
    data_no_accent = res_no_accent.json()
    assert len(data_no_accent) == 1
    assert data_no_accent[0]["paciente_id"] == "PAC-003"
    assert data_no_accent[0]["nome"] == "Cláudia M."

    # Busca com acento deve encontrar "Cláudia M." (PAC-003)
    res_with_accent = client.get("/api/pacientes?nome=Cláudia")
    assert res_with_accent.status_code == 200
    assert len(res_with_accent.json()) == 1
    assert res_with_accent.json()[0]["paciente_id"] == "PAC-003"

    # Busca por código sintético insensível a caixa
    res_by_id = client.get("/api/pacientes?nome=pac-004")
    assert res_by_id.status_code == 200
    assert len(res_by_id.json()) == 1
    assert res_by_id.json()[0]["nome"] == "Fernando L."

    # Busca sem correspondência retorna lista vazia
    res_empty = client.get("/api/pacientes?nome=PacienteInexistenteXYZ")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


def test_list_patient_sessions_and_bundle_includes_recent_sessions(client):
    # Inicializa seed
    client.get("/api/pacientes")

    session_repo = SessionRepository()
    session_repo.save_session(
        SessionDocument(
            session_id="SESS-PAC001-SLOT1",
            paciente_id="PAC-001",
            exercicio_id="FISIO-006",
            case_id="FISIO-006",
            side_evaluated="direito",
            status=SessionStatus.CONCLUIDO,
            compliance_score=95.0,
            risk_classification=RiskClassification.VERDE,
        )
    )

    # Endpoint dedicado GET /api/pacientes/{id}/sessoes
    res_sessions = client.get("/api/pacientes/PAC-001/sessoes")
    assert res_sessions.status_code == 200
    sessions_list = res_sessions.json()
    assert len(sessions_list) == 1
    assert sessions_list[0]["session_id"] == "SESS-PAC001-SLOT1"
    assert sessions_list[0]["exercicio_id"] == "FISIO-006"

    # Bundle consolidado GET /api/pacientes/{id} inclui sessoes_recentes
    res_bundle = client.get("/api/pacientes/PAC-001")
    assert res_bundle.status_code == 200
    bundle = res_bundle.json()
    assert bundle["patient"]["paciente_id"] == "PAC-001"
    assert bundle["laudo"]["laudo_id"] == "LAU-A"
    assert bundle["plano"]["plano_id"] == "PLN-PAC-001"
    assert len(bundle["sessoes_recentes"]) == 1
    assert bundle["sessoes_recentes"][0]["session_id"] == "SESS-PAC001-SLOT1"

    # Paciente inexistente retorna 404 em /sessoes
    res_404 = client.get("/api/pacientes/PAC-INEXISTENTE/sessoes")
    assert res_404.status_code == 404


