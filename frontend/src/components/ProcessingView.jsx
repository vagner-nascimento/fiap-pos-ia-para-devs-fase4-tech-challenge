import { useEffect, useState, useCallback, useRef } from 'react';
import { Card } from './ds/Card';
import { Button } from './ds/Button';
import { StatusChip } from './ds/StatusChip';
import { StepList } from './ds/StepList';
import { getSession } from '../api/sessions';

/**
 * ProcessingView — Tela 4 (Processamento):
 * Acompanhamento em tempo real das etapas da esteira assíncrona de IA.
 * Conforme Mock 4 (03-Processamento.dc.html).
 */
export function ProcessingView({ sessionId, onViewReport, onBackToSessions }) {
  const [session, setSession] = useState(null);
  const [error, setError] = useState(null);
  const [isPolling, setIsPolling] = useState(true);
  const latestRequest = useRef(0);

  const fetchStatus = useCallback(async () => {
    const requestId = ++latestRequest.current;
    try {
      const data = await getSession(sessionId);
      if (requestId !== latestRequest.current) return;
      setSession(data);
      setError(null);

      if (data.status === 'concluido' || data.status === 'erro') {
        setIsPolling(false);
      }
    } catch (err) {
      if (requestId !== latestRequest.current) return;
      setError(err.message || 'Erro ao consultar status da sessão.');
    }
  }, [sessionId]);

  useEffect(() => {
    fetchStatus();
    if (!isPolling) return;

    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus, isPolling]);

  const fallbackSteps = [
    { id: 'video_received', label: 'Vídeo recebido', description: 'Arquivo salvo e sessão criada para processamento.' },
    { id: 'pose_extraction', label: 'Extração de pose e landmarks', description: 'Landmarks corporais estão sendo extraídos frame a frame.' },
    { id: 'biomechanical_analysis', label: 'Análise biomecânica do movimento', description: 'Repetições, fases e desvios estão sendo analisados.' },
    { id: 'audio_transcription', label: 'Transcrição de áudio e fala de dor', description: 'O áudio está sendo transcrito e classificado.' },
    { id: 'artifact_generation', label: 'Vídeo anotado e evidências', description: 'Vídeo anotado e evidências visuais estão sendo gerados.' },
    { id: 'result_persistence', label: 'Persistência e relatório', description: 'Resultados finais estão sendo gravados para o relatório.' },
  ];
  const stepDefinitions = session?.processing_steps?.length ? session.processing_steps : fallbackSteps;
  const isFinished = session?.status === 'concluido';
  const isFailed = session?.status === 'erro';
  const currentStep = isFinished
    ? stepDefinitions.length - 1
    : Number.isInteger(session?.current_step_index)
    ? session.current_step_index
    : 0;
  const steps = stepDefinitions.map((step, index) => ({
    title: step.label || step.title,
    description: step.description,
    status: isFinished
      ? 'completed'
      : isFailed && index === currentStep
      ? 'error'
      : index < currentStep
      ? 'completed'
      : index === currentStep
      ? 'active'
      : 'pending',
  }));
  const progressPercent = isFinished ? 100 : Math.max(0, Math.min(100, session?.progress_percent ?? 0));
  const totalSteps = session?.total_steps || stepDefinitions.length;
  const currentStepNumber = Math.min(currentStep + 1, totalSteps);

  return (
    <div className="processing-view">
      <div className="processing-header">
        <h1>{isFinished ? 'Análise concluída' : isFailed ? 'Falha no processamento' : 'Análise em andamento'}</h1>
        <p className="mu">
          Sessão: <strong>{sessionId}</strong> · {session?.exercicio_id || 'Exercício'} ·{' '}
          {isFinished ? 'O relatório individual está pronto para visualização.' : 'Você pode acompanhar o progesso aqui.'}
        </p>
      </div>

      <div className="g" style={{ gridTemplateColumns: '1.2fr 1fr', marginTop: '20px' }}>
        <Card>
          <h2>Etapas da Esteira</h2>
          <StepList steps={steps} currentStepIndex={currentStep} />
        </Card>

        <Card style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h2>Status do Processamento</h2>
          <div>
            {isFinished ? (
              <StatusChip level="ok" label="Concluído com sucesso" symbol="●" />
            ) : isFailed ? (
              <StatusChip level="crit" label="Erro no processamento" symbol="■" />
            ) : (
              <StatusChip level="info" label={`Em processamento · etapa ${currentStepNumber} de ${totalSteps}`} symbol={null} />
            )}
          </div>

          <div className="progress-bar-container">
            <div
              className={`progress-bar-fill ${isFailed ? 'progress-failed' : !isFinished ? 'progress-active' : ''}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          <p className="mu">
            {isFinished
              ? 'A persistência no MongoDB e a renderização do vídeo anotado com HUD foram finalizadas.'
              : isFailed
              ? session?.error_message || error || 'Ocorreu um erro ao processar o vídeo. Você pode reprocessar a sessão ou voltar à lista.'
              : session?.progress_message || 'O processamento está em andamento.'}
          </p>

          <div style={{ marginTop: 'auto', display: 'flex', gap: '12px' }}>
            {isFinished && (
              <Button onClick={() => onViewReport(sessionId)}>
                Abrir Relatório da Sessão
              </Button>
            )}
            <Button variant="secondary" onClick={onBackToSessions}>
              Ver Minhas Sessões
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
