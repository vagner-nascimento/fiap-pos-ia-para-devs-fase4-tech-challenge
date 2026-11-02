import { useEffect, useState, useCallback } from 'react';
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

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getSession(sessionId);
      setSession(data);

      if (data.status === 'concluido' || data.status === 'erro') {
        setIsPolling(false);
      }
    } catch (err) {
      setError(err.message || 'Erro ao consultar status da sessão.');
      setIsPolling(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchStatus();
    if (!isPolling) return;

    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus, isPolling]);

  // Mapeamento das 7 etapas da arquitetura para a StepList
  const isFinished = session?.status === 'concluido';
  const isFailed = session?.status === 'erro';

  const steps = [
    { title: 'Vídeo enviado e recebido', status: 'completed' },
    { title: 'Separando vídeo e áudio', status: 'completed' },
    {
      title: 'Postura e biomecânica (MediaPipe Pose)',
      status: isFinished ? 'completed' : isFailed ? 'error' : 'active',
      description: 'Extração de landmarks, rastreio angular e histerese',
    },
    {
      title: 'Expressão facial (Índice facial de dor)',
      status: isFinished ? 'completed' : 'pending',
    },
    {
      title: 'Áudio: transcrição, termos de dor, voz (Whisper pt-BR)',
      status: isFinished ? 'completed' : 'pending',
    },
    {
      title: 'Fusão e comparação com plano e laudo',
      status: isFinished ? 'completed' : 'pending',
    },
    {
      title: 'Relatório pronto e classificação de risco',
      status: isFinished ? 'completed' : 'pending',
    },
  ];

  const currentStep = isFinished ? 7 : isFailed ? 3 : 3;
  const progressPercent = isFinished ? 100 : isFailed ? 42 : 55;

  return (
    <div className="processing-view">
      <div className="processing-header">
        <h1>{isFinished ? 'Análise concluída' : isFailed ? 'Falha no processamento' : 'Análise em andamento'}</h1>
        <p className="mu">
          Sessão: <strong>{sessionId}</strong> · {session?.exercicio_id || 'Exercício'} ·{' '}
          {isFinished ? 'O relatório individual está pronto para visualização.' : 'Você pode acompanhar aqui ou aguardar a notificação.'}
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
              <StatusChip level="info" label={`Em processamento · etapa ${currentStep} de 7`} symbol="…" />
            )}
          </div>

          <div className="progress-bar-container">
            <div
              className={`progress-bar-fill ${isFailed ? 'progress-failed' : ''}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          <p className="mu">
            {isFinished
              ? 'A persistência no MongoDB e a renderização do vídeo anotado com HUD foram finalizadas.'
              : isFailed
              ? error || 'Ocorreu um erro ao processar o vídeo. Você pode reprocessar a sessão ou voltar à lista.'
              : 'O vídeo está sendo analisado frame a frame. Repetições, desvios e evidências estão sendo estruturados.'}
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
