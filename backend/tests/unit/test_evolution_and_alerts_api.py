"""Testes unitários e de API para a Jornada Multi-Dias, Relatório Final de Evolução e Painel de Alertas (Issue #7)."""

from fastapi.testclient import TestClient
import mongomock
import pytest

from infra.database import mongodb_client
from infra.database.repositories.session_repository import SessionRepository
from models.database.session import RiskClassification, SessionDocument, SessionStatus
from server import create_app
from services.audio_transcription import SpeechSegment
from services.evolution_service import (
    build_series_breakdown,
    compute_consistency_score,
    compute_pain_score_0_10,
    compute_session_evolution_metrics,
)
from services.pose.models import (
    ExerciseAnalysisResult,
    RepetitionEvent,
    SessionSummary,
)


@pytest.fixture
def mock_mongo():
    client = mongomock.MongoClient()
    mongodb_client.set_client(client)
    yield client
    mongodb_client.close_connection()


@pytest.fixture
def client(mock_mongo):
    app = create_app()
    return TestClient(app)


# -------------------------------------------------------------------------
# 1. Testes Unitários das Métricas Biomecânicas e Séries (N x M)
# -------------------------------------------------------------------------

def test_build_series_breakdown_and_consistency_score():
    # Simula 3 séries x 4 repetições = 12 repetições
    reps = [
        RepetitionEvent(
            index=i,
            start_time=float((i - 1) * 2),
            peak_time=float((i - 1) * 2 + 1),
            end_time=float(i * 2),
            duration=2.0,
            peak_angle=82.0 + (i % 3),
            peak_progress=0.95,
            completed=True,
            is_valid=(i != 12),
            deviations=["inclinacao_tronco"] if i == 12 else [],
        )
        for i in range(1, 13)
    ]

    breakdown = build_series_breakdown(
        repetitions=reps,
        series_prescritas=3,
        repeticoes_por_serie=4,
    )
    assert len(breakdown) == 3
    assert breakdown[0]["serie_index"] == 1
    assert breakdown[0]["repeticoes_completadas"] == 4
    assert breakdown[0]["repeticoes_validas"] == 4
    assert breakdown[0]["concluida"] is True
    assert breakdown[2]["serie_index"] == 3
    assert breakdown[2]["repeticoes_validas"] == 3
    assert breakdown[2]["desvios_count"] == 1

    cons_score = compute_consistency_score(
        completed_repetitions=12,
        valid_repetitions=11,
        target_repetitions=12,
        peak_angles=[r.peak_angle for r in reps],
        durations=[r.duration for r in reps],
    )
    assert 85.0 <= cons_score <= 100.0


def test_compute_pain_score_0_10_from_speech_segments():
    segments = [
        SpeechSegment(
            start_seconds=2.0,
            end_seconds=5.5,
            timestamp="0:02",
            nivel="dor",
            score=2,
            texto="Agora deu uma fisgada no ombro, uns 6 de 10.",
        )
    ]
    score, pct = compute_pain_score_0_10(segments, video_duration_seconds=20.0)
    assert score == 6.0
    assert pct == 17.5


def test_compute_session_evolution_metrics_full():
    reps = [
        RepetitionEvent(
            index=i,
            start_time=float((i - 1) * 3),
            peak_time=float((i - 1) * 3 + 1.5),
            end_time=float(i * 3),
            duration=3.0,
            peak_angle=80.0 + i,
            peak_progress=0.92,
            completed=True,
            is_valid=True,
            deviations=[],
        )
        for i in range(1, 7)
    ]
    summary = SessionSummary(
        exercise_id="SHOULDER_ABDUCTION_BAND",
        case_id="FISIO-006",
        side_evaluated="direito",
        target_repetitions=6,
        completed_repetitions=6,
        valid_repetitions=6,
        invalid_repetitions=0,
        duration_seconds=20.0,
        fps=30.0,
        total_frames=600,
        frames_without_pose=0,
        compliance_score=100.0,
    )
    analysis = ExerciseAnalysisResult(
        session_summary=summary,
        repetitions=reps,
        deviations=[],
        telemetry=[],
    )
    metrics = compute_session_evolution_metrics(
        result=analysis,
        speech_segments=[],
        series_prescritas=2,
        repeticoes_por_serie=3,
    )
    assert metrics["amplitude_maxima"] == 86.0
    assert metrics["amplitude_media"] == 83.5
    assert metrics["consistencia_score"] >= 95.0
    assert metrics["dor_score_0_10"] == 0.0
    assert len(metrics["series_breakdown"]) == 2


# -------------------------------------------------------------------------
# 2. Testes do Relatório Final de Evolução Longitudinal (Multi-Dias)
# -------------------------------------------------------------------------

def test_get_patient_evolution_report_auto_seeds_multi_day_journey(client):
    res = client.get("/api/pacientes/PAC-001/relatorio-evolucao")
    assert res.status_code == 200
    report = res.json()

    assert report["patient"]["paciente_id"] == "PAC-001"
    assert report["plano"]["dias_tratamento"] == 3

    # Verifica KPIs globais (Dia 1 -> Dia 3)
    globais = report["metricas_globais"]
    assert globais["dias_previstos"] == 3
    assert globais["dias_concluidos"] == 3
    assert globais["total_sessoes_concluidas"] == 9  # 3 dias x 3 exercícios
    assert globais["amplitude_atual"] > globais["amplitude_inicial"]
    assert globais["amplitude_tendencia"] == "melhora"
    assert globais["consistencia_atual"] > globais["consistencia_inicial"]
    assert globais["consistencia_tendencia"] == "melhora"
    assert globais["dor_atual_0_10"] < globais["dor_inicial_0_10"]
    assert globais["dor_tendencia"] == "melhora"
    assert globais["classificacao_geral"] == "verde"

    # Verifica evolução dia a dia (Dia 1, Dia 2, Dia 3)
    por_dia = report["evolucao_por_dia"]
    assert len(por_dia) == 3
    assert [d["dia_tratamento"] for d in por_dia] == [1, 2, 3]
    assert all(d["concluido"] is True for d in por_dia)
    assert por_dia[2]["amplitude_media_dia"] > por_dia[0]["amplitude_media_dia"]
    assert por_dia[2]["consistencia_media_dia"] > por_dia[0]["consistencia_media_dia"]
    assert por_dia[2]["dor_maxima_dia_0_10"] < por_dia[0]["dor_maxima_dia_0_10"]

    # Verifica evolução por exercício (3 slots prescritos com N séries x M repetições)
    por_exercicio = report["evolucao_por_exercicio"]
    assert len(por_exercicio) == 3
    slot1 = por_exercicio[0]
    assert slot1["slot_id"] == "SLOT-1"
    assert slot1["exercicio_id"] == "FISIO-006"
    assert slot1["series_prescritas"] == 3
    assert slot1["repeticoes_por_serie"] == 10
    assert slot1["total_repeticoes_dia"] == 30
    assert slot1["dias_executados"] == 3
    assert len(slot1["sessoes"]) == 3
    assert len(slot1["sessoes"][0]["series_breakdown"]) == 3

    # Verifica parecer clínico explicável
    assert len(report["parecer_clinico"]) >= 3


def test_evaluate_patient_evolution_and_mark_alerts_treated(client):
    # Carrega relatório inicial
    client.get("/api/pacientes/PAC-001/relatorio-evolucao")

    # Médico / fisioterapeuta registra avaliação final da evolução
    res = client.post(
        "/api/pacientes/PAC-001/avaliar-evolucao",
        json={
            "avaliado": True,
            "observacoes": "Paciente evoluiu com ganho de 21° em abdução, alta consistência nas 3 séries e remissão da dor. Apta para progressão de carga.",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["avaliado_evolucao"] is True
    assert "Apta para progressão" in data["observacoes_avaliacao_final"]
    # Todos os alertas do paciente devem estar marcados como 'tratado'
    assert all(a["estado"] == "tratado" for a in data["alertas_paciente"])


# -------------------------------------------------------------------------
# 3. Testes do Painel de Alertas (/api/alertas) e Avaliação de Sessão
# -------------------------------------------------------------------------

def test_alerts_panel_listing_filters_and_status_update(client):
    res = client.get("/api/alertas")
    assert res.status_code == 200
    body = res.json()
    assert body["contadores"]["total"] >= 4
    assert body["contadores"]["criticos"] >= 1
    assert len(body["alertas"]) >= 4

    # Filtra apenas severidade 'critico'
    res_crit = client.get("/api/alertas?severidade=critico")
    assert res_crit.status_code == 200
    assert all(a["severidade"] == "critico" for a in res_crit.json()["alertas"])

    # Atualiza estado de um alerta para 'tratado'
    first_id = body["alertas"][0]["alerta_id"]
    res_patch = client.patch(f"/api/alertas/{first_id}", json={"estado": "tratado"})
    assert res_patch.status_code == 200
    assert res_patch.json()["estado"] == "tratado"

    # Estado inválido deve retornar 422
    res_bad = client.patch(f"/api/alertas/{first_id}", json={"estado": "invalido"})
    assert res_bad.status_code == 422


def test_mark_individual_session_evaluated_endpoint(client):
    client.get("/api/pacientes")
    session_repo = SessionRepository()
    session_repo.save_session(
        SessionDocument(
            session_id="SESS-EVAL-TEST-01",
            paciente_id="PAC-001",
            slot_id="SLOT-1",
            dia_tratamento=2,
            series_prescritas=3,
            repeticoes_por_serie=10,
            exercicio_id="FISIO-006",
            case_id="FISIO-006",
            side_evaluated="direito",
            status=SessionStatus.CONCLUIDO,
            compliance_score=90.0,
            risk_classification=RiskClassification.VERDE,
        )
    )

    patch_res = client.patch("/api/sessoes/SESS-EVAL-TEST-01/avaliar")
    assert patch_res.status_code == 200
    assert patch_res.json()["avaliado_fisioterapeuta"] is True

    rep_res = client.get("/api/sessoes/SESS-EVAL-TEST-01/relatorio")
    assert rep_res.status_code == 200
    rep = rep_res.json()
    assert rep["avaliado_fisioterapeuta"] is True
    assert rep["dia_tratamento"] == 2
    assert rep["series_prescritas"] == 3
    assert rep["repeticoes_por_serie"] == 10
    assert len(rep["series_breakdown"]) == 3


def test_save_plan_with_different_exercises_per_day_and_evolution_report(client):
    """
    Valida que o plano permite prescrever exercícios diferentes por dia de tratamento
    (ex.: Dia 1 = FISIO-002 + FISIO-006; Dia 2 = FISIO-006 + FISIO-005; Dia 3 = FISIO-005 + FISIO-007)
    e que o Relatório Final de Evolução respeita a programação específica de cada dia.
    """
    client.post(
        "/api/pacientes",
        json={
            "paciente_id": "PAC-MULTI-DIA",
            "nome": "Eduardo P.",
            "idade": 41,
        },
    )

    plan_res = client.post(
        "/api/pacientes/PAC-MULTI-DIA/plano",
        json={
            "dias_tratamento": 3,
            "dor_maxima_aceitavel": 4,
            "amplitude_esperada_texto": "60 – 90",
            "exercicios": [
                {
                    "exercicio_id": "FISIO-002",
                    "series": 2,
                    "repeticoes": 10,
                    "dias_prescritos": [1],
                },
                {
                    "exercicio_id": "FISIO-006",
                    "series": 3,
                    "repeticoes": 10,
                    "dias_prescritos": [1, 2],
                },
                {
                    "exercicio_id": "FISIO-005",
                    "series": 3,
                    "repeticoes": 8,
                    "dias_prescritos": [2, 3],
                },
                {
                    "exercicio_id": "FISIO-007",
                    "series": 3,
                    "repeticoes": 10,
                    "dia_tratamento": 3,
                },
            ],
        },
    )
    assert plan_res.status_code == 200
    saved_plan = plan_res.json()
    assert saved_plan["dias_tratamento"] == 3
    assert len(saved_plan["exercicios"]) == 4
    assert saved_plan["exercicios"][0]["dias_prescritos"] == [1]
    assert saved_plan["exercicios"][0]["dia_tratamento"] == 1
    assert saved_plan["exercicios"][1]["dias_prescritos"] == [1, 2]
    assert saved_plan["exercicios"][2]["dias_prescritos"] == [2, 3]
    assert saved_plan["exercicios"][3]["dias_prescritos"] == [3]
    assert saved_plan["exercicios"][3]["dia_tratamento"] == 3

    # Simula a jornada multi-dias para este plano personalizado
    evo_res = client.post("/api/pacientes/PAC-MULTI-DIA/seed-evolucao")
    assert evo_res.status_code == 200
    report = evo_res.json()

    # Dia 1 tem 2 exercícios (FISIO-002, FISIO-006)
    # Dia 2 tem 2 exercícios (FISIO-006, FISIO-005)
    # Dia 3 tem 2 exercícios (FISIO-005, FISIO-007) -> total = 6 sessões previstas e concluídas
    assert report["metricas_globais"]["total_sessoes_previstas"] == 6
    assert report["metricas_globais"]["total_sessoes_concluidas"] == 6
    assert report["metricas_globais"]["percentual_adesao_plano"] == 100.0

    por_dia = report["evolucao_por_dia"]
    assert len(por_dia) == 3
    assert por_dia[0]["exercicios_prescritos"] == 2
    assert por_dia[0]["exercicios_concluidos"] == 2
    assert por_dia[0]["total_repeticoes_prescritas"] == (2 * 10) + (3 * 10)  # 50
    assert por_dia[1]["exercicios_prescritos"] == 2
    assert por_dia[1]["total_repeticoes_prescritas"] == (3 * 10) + (3 * 8)   # 54
    assert por_dia[2]["exercicios_prescritos"] == 2
    assert por_dia[2]["total_repeticoes_prescritas"] == (3 * 8) + (3 * 10)   # 54

    por_ex = {ex["exercicio_id"]: ex for ex in report["evolucao_por_exercicio"]}
    assert por_ex["FISIO-002"]["dias_prescritos"] == [1]
    assert por_ex["FISIO-002"]["dias_executados"] == 1
    assert por_ex["FISIO-006"]["dias_prescritos"] == [1, 2]
    assert por_ex["FISIO-006"]["dias_executados"] == 2
    assert por_ex["FISIO-005"]["dias_prescritos"] == [2, 3]
    assert por_ex["FISIO-005"]["dias_executados"] == 2
    assert por_ex["FISIO-007"]["dias_prescritos"] == [3]
    assert por_ex["FISIO-007"]["dias_executados"] == 1


