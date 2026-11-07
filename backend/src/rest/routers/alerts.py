"""Endpoints REST para o Painel de Alertas Clínicos do Fisioterapeuta/Médico (Issue #7)."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from infra.database.repositories.alert_repository import AlertRepository
from models.database.alert import AlertDocument, AlertSeverity, AlertStatus
from models.rest.patient import (
    AlertsListResponse,
    AlertSummaryCounters,
    UpdateAlertStatusRequest,
)
from rest.routers.patients import ensure_seed_alerts, ensure_seed_clinical_data

router = APIRouter(prefix="/alertas", tags=["Alertas Clínicos"])


@router.get(
    "",
    response_model=AlertsListResponse,
    summary="Listar alertas clínicos e contadores do Painel de Alertas",
    description=(
        "Retorna a lista de alertas clínicos gerados nas sessões e na evolução dos pacientes, "
        "com filtros opcionais por paciente, severidade e estado operacional (PRD v1.2 seção 6.3)."
    ),
)
def list_clinical_alerts(
    paciente_id: Optional[str] = Query(None, description="Filtrar por ID do paciente"),
    severidade: Optional[str] = Query(None, description="Filtrar por severidade ('critico', 'atencao', 'verde')"),
    estado: Optional[str] = Query(None, description="Filtrar por estado ('novo', 'lido', 'tratado')"),
    limit: int = Query(100, ge=1, le=200),
) -> AlertsListResponse:
    ensure_seed_clinical_data()
    alert_repo = AlertRepository()
    ensure_seed_alerts(alert_repo)

    all_alerts = alert_repo.list_alerts(paciente_id=paciente_id, limit=200)
    filtered = alert_repo.list_alerts(
        paciente_id=paciente_id,
        severidade=severidade,
        estado=estado,
        limit=limit,
    )

    contadores = AlertSummaryCounters(
        total=len(all_alerts),
        novos=sum(1 for a in all_alerts if a.estado == AlertStatus.NOVO),
        lidos=sum(1 for a in all_alerts if a.estado == AlertStatus.LIDO),
        tratados=sum(1 for a in all_alerts if a.estado == AlertStatus.TRATADO),
        criticos=sum(
            1 for a in all_alerts if a.severidade == AlertSeverity.CRITICO and a.estado != AlertStatus.TRATADO
        ),
        atencao=sum(
            1 for a in all_alerts if a.severidade == AlertSeverity.ATENCAO and a.estado != AlertStatus.TRATADO
        ),
        verdes=sum(
            1 for a in all_alerts if a.severidade == AlertSeverity.VERDE or a.estado == AlertStatus.TRATADO
        ),
    )

    return AlertsListResponse(
        contadores=contadores,
        alertas=filtered,
    )


@router.patch(
    "/{alerta_id}",
    response_model=AlertDocument,
    summary="Atualizar estado operacional de um alerta ('novo', 'lido', 'tratado')",
)
def update_clinical_alert_status(
    alerta_id: str,
    payload: UpdateAlertStatusRequest,
) -> AlertDocument:
    valid_states = {s.value for s in AlertStatus}
    target_state = (payload.estado or "").strip().lower()
    if target_state not in valid_states:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Estado de alerta inválido ('{payload.estado}'). Use: novo, lido ou tratado.",
        )

    alert_repo = AlertRepository()
    ensure_seed_alerts(alert_repo)
    updated = alert_repo.update_alert_status(alerta_id=alerta_id, estado=target_state)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta '{alerta_id}' não encontrado.",
        )
    return updated

