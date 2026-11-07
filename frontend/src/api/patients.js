const apiBaseUrl = import.meta.env.VITE_BACKEND_API_URL || '/api';

/**
 * Utilitário interno para parsing seguro de respostas HTTP
 */
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
 * Lista os pacientes sintéticos cadastrados no MongoDB (com filtro opcional por nome/ID).
 */
export async function listPatients(nomeQuery = '') {
  const query = nomeQuery ? `?nome=${encodeURIComponent(nomeQuery)}` : '';
  const response = await fetch(`${apiBaseUrl}/pacientes${query}`);
  return handleResponse(response, 'Falha ao buscar lista de pacientes.');
}

/**
 * Cria ou atualiza um paciente sintético.
 */
export async function createPatient(payload) {
  const response = await fetch(`${apiBaseUrl}/pacientes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response, 'Falha ao salvar dados do paciente.');
}

/**
 * Retorna os dados consolidados do paciente (cadastro, laudo e plano ativo).
 */
export async function getPatientBundle(pacienteId) {
  const response = await fetch(`${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}`);
  return handleResponse(response, `Paciente '${pacienteId}' não encontrado.`);
}

/**
 * Retorna o catálogo completo dos 7 exercícios clínicos para prescrição.
 */
export async function listClinicalExerciseCatalog() {
  const response = await fetch(`${apiBaseUrl}/pacientes/catalogo-exercicios`);
  return handleResponse(response, 'Falha ao carregar catálogo de exercícios clínicos.');
}

/**
 * Extrai automaticamente entidades estruturadas do texto livre do laudo (preview).
 */
export async function extractReportPreview(textoOriginal) {
  const response = await fetch(`${apiBaseUrl}/pacientes/laudo/extrair`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texto_original: textoOriginal }),
  });
  return handleResponse(response, 'Falha ao extrair entidades do laudo.');
}

/**
 * Salva ou atualiza o laudo médico de um paciente.
 */
export async function savePatientMedicalReport(pacienteId, payload) {
  const response = await fetch(`${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/laudo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response, 'Falha ao salvar o laudo médico do paciente.');
}

/**
 * Salva ou atualiza o plano de prescrição de exercícios de um paciente.
 */
export async function savePatientPlan(pacienteId, payload) {
  const response = await fetch(`${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/plano`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(response, 'Falha ao salvar o plano de exercícios do paciente.');
}

/**
 * Obtém o laudo médico estruturado de um paciente (Issue #4).
 */
export async function getPatientMedicalReport(pacienteId) {
  const response = await fetch(`${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/laudo`);
  return handleResponse(response, 'Laudo médico não encontrado para este paciente.');
}

/**
 * Obtém o plano de prescrição de exercícios ativo de um paciente (Issue #4).
 */
export async function getPatientPlan(pacienteId) {
  const response = await fetch(`${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/plano`);
  return handleResponse(response, 'Plano de exercícios não encontrado para este paciente.');
}

/**
 * Lista o histórico de sessões enviadas/concluídas pelo paciente (Issue #4).
 */
export async function listPatientSessions(pacienteId) {
  const response = await fetch(`${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/sessoes`);
  return handleResponse(response, 'Falha ao carregar o histórico de sessões do paciente.');
}

/**
 * Obtém o Relatório Final de Evolução Longitudinal do Paciente (Issue #7).
 */
export async function getPatientEvolutionReport(pacienteId, { autoSeed = true } = {}) {
  const qs = autoSeed ? '?auto_seed=true' : '?auto_seed=false';
  const response = await fetch(
    `${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/relatorio-evolucao${qs}`
  );
  return handleResponse(response, 'Falha ao carregar o relatório final de evolução do paciente.');
}

/**
 * Popula/simula a jornada multi-dias completa de um paciente para demonstração imediata (Issue #7).
 */
export async function seedPatientEvolutionDemo(pacienteId) {
  const response = await fetch(
    `${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/seed-evolucao`,
    { method: 'POST' }
  );
  return handleResponse(response, 'Falha ao simular jornada multi-dias do paciente.');
}

/**
 * Registra a avaliação final do médico/fisioterapeuta sobre a evolução longitudinal do paciente (Issue #7).
 */
export async function evaluatePatientEvolution(pacienteId, payload) {
  const response = await fetch(
    `${apiBaseUrl}/pacientes/${encodeURIComponent(pacienteId)}/avaliar-evolucao`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }
  );
  return handleResponse(response, 'Falha ao registrar avaliação do relatório de evolução.');
}


