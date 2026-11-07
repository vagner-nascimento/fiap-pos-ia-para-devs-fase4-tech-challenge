import { useEffect, useState, useCallback } from 'react';
import { Card } from './ds/Card';
import { Button } from './ds/Button';
import { StatusChip } from './ds/StatusChip';
import {
  listSessions,
  createSessionReference,
  createSessionUpload,
  listReferenceClips,
  listExercises,
  getDatasetStatus,
  downloadDataset,
} from '../api/sessions';
import { Plus, RefreshCw, PlayCircle, FileText, Upload, Film, X, Download, ShieldCheck } from 'lucide-react';

/**
 * SessionsListView — Histórico de sessões e modal para nova análise biomecânica.
 */
export function SessionsListView({ onSelectSession, onSelectProcessing }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterPatient, setFilterPatient] = useState('');

  // Estado do Modal de Nova Análise
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTab, setModalTab] = useState('reference'); // 'reference' | 'upload'
  const [referenceClips, setReferenceClips] = useState([]);
  const [exerciseOptions, setExerciseOptions] = useState([]);
  const [selectedExerciseId, setSelectedExerciseId] = useState('');
  const [selectedClip, setSelectedClip] = useState('');
  const [pacienteId, setPacienteId] = useState('PAC-001');
  const [targetReps, setTargetReps] = useState(5);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [datasetStatus, setDatasetStatus] = useState(null);
  const [isDownloadingDataset, setIsDownloadingDataset] = useState(false);

  const fetchSessionsList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSessions(filterPatient || null);
      setSessions(data);
    } catch (err) {
      setError(err.message || 'Erro ao carregar lista de sessões.');
    } finally {
      setLoading(false);
    }
  }, [filterPatient]);

  useEffect(() => {
    fetchSessionsList();
  }, [fetchSessionsList]);

  // Carrega clipes de referência ao abrir o modal
  const openNewAnalysisModal = async () => {
    setIsModalOpen(true);
    setSubmitError(null);
    try {
      const [exercises, status] = await Promise.all([listExercises(), getDatasetStatus()]);
      setExerciseOptions(exercises);
      setDatasetStatus(status);
      const clips = status.status === 'ready' ? await listReferenceClips() : [];
      setReferenceClips(clips);
      if (exercises.length > 0 && !selectedExerciseId) {
        setSelectedExerciseId(exercises[0].case_id);
      }
      if (clips.length > 0 && !selectedClip) {
        setSelectedClip(clips[0].filename);
      }
    } catch (err) {
      setSubmitError(err.message || 'Falha ao carregar os exercícios disponíveis.');
    }
  };

  const handleDownloadDataset = async () => {
    setIsDownloadingDataset(true);
    setSubmitError(null);
    try {
      let status = await downloadDataset();
      while (status.status === 'downloading' || status.status === 'not_downloaded') {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        status = await getDatasetStatus();
      }
      setDatasetStatus(status);
      if (status.status !== 'ready') {
        throw new Error(status.message || 'O dataset não pôde ser disponibilizado.');
      }
      const clips = await listReferenceClips();
      setReferenceClips(clips);
      if (clips.length > 0) {
        setSelectedClip(clips[0].filename);
        setSelectedExerciseId(clips[0].case_id);
      }
    } catch (err) {
      setSubmitError(err.message || 'Falha ao baixar o dataset.');
    } finally {
      setIsDownloadingDataset(false);
    }
  };

  const handleStartAnalysis = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      if (modalTab === 'reference') {
        const clipInfo = referenceClips.find((c) => c.filename === selectedClip);
        const payload = {
          exercicio_id: clipInfo?.case_id || selectedExerciseId,
          paciente_id: pacienteId || 'PAC-001',
          dataset_clip: selectedClip,
          target_repetitions: Number(targetReps) || 5,
          side: 'auto',
        };
        const res = await createSessionReference(payload);
        setIsModalOpen(false);
        onSelectProcessing(res.session_id);
      } else {
        if (!selectedFile) {
          throw new Error('Por favor selecione um arquivo de vídeo (.mp4).');
        }
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('exercicio_id', selectedExerciseId);
        formData.append('paciente_id', pacienteId || 'PAC-001');
        formData.append('side', 'auto');
        formData.append('target_repetitions', String(targetReps || 5));

        const res = await createSessionUpload(formData);
        setIsModalOpen(false);
        onSelectProcessing(res.session_id);
      }
    } catch (err) {
      setSubmitError(err.message || 'Falha ao iniciar análise.');
      setIsSubmitting(false);
    }
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return '--';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="sessions-list-view">
      <div className="sessions-header-bar">
        <div>
          <h1>Sessões de Fisioterapia</h1>
          <p className="mu">Histórico de gravações e relatórios analíticos individuais</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <Button variant="secondary" onClick={fetchSessionsList} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin' : ''} /> Atualizar
          </Button>
          <Button onClick={openNewAnalysisModal}>
            <Plus size={16} /> Nova Análise de Vídeo
          </Button>
        </div>
      </div>

      {/* Filtro simples por Paciente */}
      <Card style={{ padding: '16px 20px', marginTop: '16px' }}>
        <div className="f" style={{ gap: '12px', flexWrap: 'wrap' }}>
          <label style={{ margin: 0, alignSelf: 'center' }}>Filtrar por paciente:</label>
          <input
            type="text"
            className="in"
            style={{ width: '220px', height: '38px' }}
            placeholder="Ex: PAC-001"
            value={filterPatient}
            onChange={(e) => setFilterPatient(e.target.value)}
          />
          {filterPatient && (
            <Button
              variant="secondary"
              style={{ height: '38px', padding: '0 12px' }}
              onClick={() => setFilterPatient('')}
            >
              Limpar filtro
            </Button>
          )}
        </div>
      </Card>

      {/* Tabela de Sessões */}
      <div style={{ marginTop: '20px' }}>
        {loading && sessions.length === 0 ? (
          <Card>
            <p className="mu" style={{ textAlign: 'center', padding: '24px 0' }}>
              Carregando sessões registradas no MongoDB...
            </p>
          </Card>
        ) : error ? (
          <Card>
            <p className="mu" style={{ color: 'var(--fc-crit-fg)' }}>
              {error}
            </p>
          </Card>
        ) : sessions.length === 0 ? (
          <Card>
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <Film size={40} className="mu" style={{ margin: '0 auto 12px' }} />
              <h2>Nenhuma sessão encontrada</h2>
              <p className="mu" style={{ maxWidth: '420px', margin: '0 auto 16px' }}>
                Você ainda não possui análises registradas. Clique abaixo para rodar uma análise sobre um clipe de teste do dataset.
              </p>
              <Button onClick={openNewAnalysisModal}>Disparar Análise com Clipe do Dataset</Button>
            </div>
          </Card>
        ) : (
          <div className="sessions-table-container">
            <table className="sessions-table">
              <thead>
                <tr>
                  <th>Sessão</th>
                  <th>Paciente</th>
                  <th>Exercício</th>
                  <th>Data</th>
                  <th>Conformidade</th>
                  <th>Classificação</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Ação</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((sess) => {
                  const isDone = sess.status === 'concluido';
                  const isProc = sess.status === 'processando' || sess.status === 'enviado';
                  const riskLevel =
                    sess.risk_classification === 'critico'
                      ? 'crit'
                      : sess.risk_classification === 'atencao'
                      ? 'warn'
                      : 'ok';
                  const riskLabel =
                    sess.risk_classification === 'critico'
                      ? 'Crítico'
                      : sess.risk_classification === 'atencao'
                      ? 'Atenção'
                      : 'Verde';

                  return (
                    <tr
                      key={sess.session_id}
                      className="session-row"
                      onClick={() => {
                        if (isDone) onSelectSession(sess.session_id);
                        else onSelectProcessing(sess.session_id);
                      }}
                    >
                      <td className="session-id-cell">
                        <strong>{sess.session_id}</strong>
                        {sess.slot_id && (
                          <small className="mu" style={{ display: 'block', fontSize: '11px' }}>
                            {sess.slot_id}
                          </small>
                        )}
                      </td>
                      <td>
                        <div>{sess.paciente_id || 'PAC-001'}</div>
                        {sess.lgpd_aceite !== false && (
                          <span
                            className="ch ok"
                            style={{ fontSize: '10px', padding: '1px 6px', marginTop: '3px' }}
                            title="Termo de Consentimento LGPD aceito pelo paciente"
                          >
                            <ShieldCheck size={11} /> ● LGPD aceito
                          </span>
                        )}
                      </td>
                      <td>{sess.exercicio_id}</td>
                      <td className="mu">{formatDateTime(sess.created_at)}</td>
                      <td>
                        <strong>{(sess.compliance_score ?? 100).toFixed(0)}%</strong>
                        <small className="mu" style={{ marginLeft: '6px' }}>
                          ({sess.valid_repetitions || 0}/{sess.target_repetitions || 5} reps)
                        </small>
                      </td>
                      <td>
                        <StatusChip level={riskLevel} label={riskLabel} />
                      </td>
                      <td>
                        <span className={`status-pill ${isDone ? 'done' : isProc ? 'proc' : 'err'}`}>
                          {sess.status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {isDone ? (
                          <Button
                            variant="secondary"
                            style={{ height: '34px', padding: '0 12px', fontSize: '13px' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectSession(sess.session_id);
                            }}
                          >
                            <FileText size={14} /> Relatório
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            style={{ height: '34px', padding: '0 12px', fontSize: '13px' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectProcessing(sess.session_id);
                            }}
                          >
                            <PlayCircle size={14} /> Acompanhar
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Nova Análise de Vídeo */}
      {isModalOpen && (
        <div className="lightbox-backdrop" onClick={() => !isSubmitting && setIsModalOpen(false)}>
          <div className="lightbox-modal modal-new-session" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-header">
              <div>
                <h2>Nova Análise de Biomecânica</h2>
                <p className="mu">Selecione um clipe de demonstração do dataset ou envie seu arquivo</p>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={() => setIsModalOpen(false)}
                disabled={isSubmitting}
                aria-label="Fechar"
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-tabs">
              <button
                type="button"
                className={`modal-tab ${modalTab === 'reference' ? 'active' : ''}`}
                onClick={() => setModalTab('reference')}
              >
                <Film size={16} /> Clipes de Teste do Dataset
              </button>
              <button
                type="button"
                className={`modal-tab ${modalTab === 'upload' ? 'active' : ''}`}
                onClick={() => setModalTab('upload')}
              >
                <Upload size={16} /> Enviar Arquivo MP4
              </button>
            </div>

            <form onSubmit={handleStartAnalysis} className="modal-form">
              {modalTab === 'reference' ? (
                <div>
                  <label htmlFor="select-clip">Selecione o clipe do dataset sintético:</label>
                  {datasetStatus?.status !== 'ready' ? (
                    <div className="dataset-download-state">
                      <p className="mu">
                        {datasetStatus?.status === 'downloading'
                          ? 'Download do dataset em andamento...'
                          : 'Os vídeos do dataset ainda não estão disponíveis nesta aplicação.'}
                      </p>
                      <Button type="button" onClick={handleDownloadDataset} disabled={isDownloadingDataset}>
                        <Download size={16} />
                        {isDownloadingDataset ? 'Baixando Dataset...' : 'Download Dataset'}
                      </Button>
                    </div>
                  ) : (
                  <select
                    id="select-clip"
                    className="in"
                    value={selectedClip}
                    onChange={(e) => {
                      const filename = e.target.value;
                      setSelectedClip(filename);
                      const clipInfo = referenceClips.find((clip) => clip.filename === filename);
                      if (clipInfo?.case_id) {
                        setSelectedExerciseId(clipInfo.case_id);
                      }
                    }}
                    required
                  >
                    {referenceClips.map((clip) => (
                      <option key={clip.filename} value={clip.filename}>
                        {clip.filename} — {clip.descricao}
                      </option>
                    ))}
                  </select>
                  )}
                </div>
              ) : (
                <div>
                  <label htmlFor="file-input">Selecione o arquivo de vídeo (.mp4):</label>
                  <input
                    id="file-input"
                    type="file"
                    accept="video/mp4,video/*"
                    className="in"
                    style={{ paddingTop: '8px' }}
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    required
                  />
                </div>
              )}

              <div style={{ marginTop: '16px' }}>
                <label htmlFor="exercise-id">Exercício:</label>
                <select
                  id="exercise-id"
                  className="in"
                  value={selectedExerciseId}
                  onChange={(e) => setSelectedExerciseId(e.target.value)}
                  disabled={modalTab === 'reference'}
                  required
                >
                  <option value="" disabled>Selecione um exercício</option>
                  {exerciseOptions.map((exercise) => (
                    <option key={exercise.case_id} value={exercise.case_id}>
                      {exercise.case_id} — {exercise.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div className="g" style={{ gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px' }}>
                <div>
                  <label htmlFor="paciente-id">ID do Paciente:</label>
                  <input
                    id="paciente-id"
                    type="text"
                    className="in"
                    value={pacienteId}
                    onChange={(e) => setPacienteId(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="target-reps">Meta de repetições (alvo):</label>
                  <input
                    id="target-reps"
                    type="number"
                    min="1"
                    max="50"
                    className="in"
                    value={targetReps}
                    onChange={(e) => setTargetReps(e.target.value)}
                    required
                  />
                </div>
              </div>

              {submitError && (
                <p className="mu" style={{ color: 'var(--fc-crit-fg)', marginTop: '12px' }}>
                  {submitError}
                </p>
              )}

              <div className="modal-actions" style={{ marginTop: '24px' }}>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  disabled={
                    isSubmitting ||
                    (modalTab === 'reference' &&
                      (datasetStatus?.status !== 'ready' || !selectedClip))
                  }
                >
                  {isSubmitting ? 'Iniciando Esteira...' : 'Iniciar Análise Biomecânica'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
