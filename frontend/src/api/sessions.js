const apiBaseUrl = import.meta.env.VITE_BACKEND_API_URL || '/api';

/**
 * Utilitário interno para parsing seguro de resposta HTTP
 */
async function handleResponse(response, defaultErrorMsg) {
  if (!response.ok) {
    let errorDetail = defaultErrorMsg;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // Ignora erro de parse caso a resposta não seja JSON
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

/**
 * Lista as sessões gravadas no MongoDB, com filtro opcional por paciente
 */
export async function listSessions(pacienteId = null) {
  const query = pacienteId ? `?paciente_id=${encodeURIComponent(pacienteId)}` : '';
  const response = await fetch(`${apiBaseUrl}/sessoes${query}`);
  return handleResponse(response, 'Falha ao buscar a lista de sessões.');
}

/**
 * Retorna os detalhes consolidados de uma sessão pelo ID
 */
export async function getSession(sessionId) {
  const response = await fetch(`${apiBaseUrl}/sessoes/${encodeURIComponent(sessionId)}`);
  return handleResponse(response, `Sessão '${sessionId}' não encontrada.`);
}

/**
 * Retorna a linha do tempo de eventos de uma sessão (repetições e desvios)
 */
export async function getSessionEvents(sessionId, tipo = null) {
  const query = tipo ? `?tipo=${encodeURIComponent(tipo)}` : '';
  const response = await fetch(`${apiBaseUrl}/sessoes/${encodeURIComponent(sessionId)}/eventos${query}`);
  return handleResponse(response, 'Falha ao buscar os eventos da sessão.');
}

/**
 * Retorna o relatório individual estruturado da sessão para a interface clínica
 */
export async function getSessionReport(sessionId) {
  const response = await fetch(`${apiBaseUrl}/sessoes/${encodeURIComponent(sessionId)}/relatorio`);
  return handleResponse(response, 'Falha ao carregar o relatório individual da sessão.');
}

/**
 * Envia um novo arquivo de vídeo via multipart/form-data.
 * Quando onProgress é informado, utiliza XMLHttpRequest para reportar o percentual de upload (0..100).
 */
export async function createSessionUpload(formData, { onProgress } = {}) {
  if (typeof onProgress === 'function' && typeof XMLHttpRequest !== 'undefined') {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${apiBaseUrl}/sessoes`);

      if (xhr.upload) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && event.total > 0) {
            const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
            onProgress(percent);
          }
        };
      }

      xhr.onload = () => {
        let parsed = null;
        try {
          parsed = JSON.parse(xhr.responseText);
        } catch {
          parsed = null;
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress(100);
          resolve(parsed);
        } else {
          const detail = parsed?.detail || 'Falha ao enviar vídeo para análise.';
          reject(new Error(detail));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Falha de rede durante o upload do vídeo. Verifique sua conexão e tente novamente.'));
      };

      xhr.send(formData);
    });
  }

  const response = await fetch(`${apiBaseUrl}/sessoes`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse(response, 'Falha ao enviar vídeo para análise.');
}

/**
 * Dispara uma análise a partir de um clipe do dataset de referência
 */
export async function createSessionReference(payload) {
  const response = await fetch(`${apiBaseUrl}/sessoes/referencia`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response, 'Falha ao iniciar análise via clipe de referência.');
}

/**
 * Retorna a lista dos clipes de teste do dataset de referência disponíveis
 */
export async function listReferenceClips() {
  const response = await fetch(`${apiBaseUrl}/sessoes/clips-referencia`);
  return handleResponse(response, 'Falha ao listar os clipes de referência.');
}

export async function getDatasetStatus() {
  const response = await fetch(`${apiBaseUrl}/datasets/fisio/status`);
  return handleResponse(response, 'Falha ao consultar o status do dataset.');
}

export async function downloadDataset() {
  const response = await fetch(`${apiBaseUrl}/datasets/fisio/download`, { method: 'POST' });
  return handleResponse(response, 'Falha ao baixar o dataset.');
}

/**
 * Retorna os exercícios que podem ser selecionados antes do upload.
 */
export async function listExercises() {
  const response = await fetch(`${apiBaseUrl}/sessoes/exercicios`);
  return handleResponse(response, 'Falha ao listar os exercícios disponíveis.');
}
