const apiBaseUrl = import.meta.env.VITE_BACKEND_API_URL || '/api';

async function handleResponse(response, defaultErrorMsg) {
  if (!response.ok) {
    let errorDetail = defaultErrorMsg;
    try {
      const errorJson = await response.json();
      if (typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail) && errorJson.detail[0]?.msg) {
        errorDetail = errorJson.detail[0].msg;
      }
    } catch {
      // Ignora erro de parse caso a resposta não seja JSON
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

/**
 * Lista os alertas clínicos do Painel de Alertas com filtros opcionais.
 */
export async function listAlerts({ pacienteId = '', severidade = '', estado = '' } = {}) {
  const params = new URLSearchParams();
  if (pacienteId) params.set('paciente_id', pacienteId);
  if (severidade) params.set('severidade', severidade);
  if (estado) params.set('estado', estado);
  const qs = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${apiBaseUrl}/alertas${qs}`);
  return handleResponse(response, 'Falha ao carregar alertas clínicos.');
}

/**
 * Atualiza o estado operacional de um alerta ('novo', 'lido' ou 'tratado').
 */
export async function updateAlertStatus(alertaId, estado) {
  const response = await fetch(`${apiBaseUrl}/alertas/${encodeURIComponent(alertaId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ estado }),
  });
  return handleResponse(response, 'Falha ao atualizar status do alerta.');
}

