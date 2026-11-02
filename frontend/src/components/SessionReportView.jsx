import { useEffect, useState } from 'react';
import { Card } from './ds/Card';
import { Button } from './ds/Button';
import { StatusChip } from './ds/StatusChip';
import { VideoPlayer } from './ds/VideoPlayer';
import { Timeline } from './ds/Timeline';
import { getSessionReport } from '../api/sessions';
import { Printer, ArrowLeft, CheckCircle2, ZoomIn, X } from 'lucide-react';

/**
 * SessionReportView — Tela 5 (Relatório da Sessão):
 * Exibição analítica individual do vídeo com player anotado, timeline sincronizada,
 * galeria de evidências e apoio à decisão clínica.
 * Conforme Mock 5 (04-Relatorio-Sessao.dc.html).
 */
export function SessionReportView({ sessionId, onBackToSessions }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(1);
  const [seekTarget, setSeekTarget] = useState(null);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [isEvaluated, setIsEvaluated] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadReport() {
      setLoading(true);
      setError(null);
      try {
        const data = await getSessionReport(sessionId);
        if (isMounted) {
          setReport(data);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Erro ao carregar relatório da sessão.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }
    loadReport();
    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  const handleSeek = (timeInSeconds) => {
    setSeekTarget(timeInSeconds);
  };

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="report-loading-state">
        <div className="spin-indicator" aria-hidden="true" />
        <p>Carregando relatório individual da sessão...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="report-error-state">
        <Card>
          <h2>Não foi possível exibir o relatório</h2>
          <p className="mu">{error || 'Sessão não encontrada.'}</p>
          <Button variant="secondary" onClick={onBackToSessions} style={{ marginTop: '16px' }}>
            <ArrowLeft size={16} /> Voltar para Sessões
          </Button>
        </Card>
      </div>
    );
  }

  const riskLevel = report.risk_classification === 'critico'
    ? 'crit'
    : report.risk_classification === 'atencao'
    ? 'warn'
    : 'ok';

  const riskLabel = report.risk_classification === 'critico'
    ? 'Crítico'
    : report.risk_classification === 'atencao'
    ? 'Atenção'
    : 'Verde';

  const complianceFormatted = (report.compliance_score ?? 100).toFixed(1);

  return (
    <div className="report-view-container">
      {/* Barra superior de ações e identificação */}
      <div className="report-top-bar no-print">
        <Button variant="secondary" onClick={onBackToSessions} className="btn-back">
          <ArrowLeft size={16} /> Voltar para Sessões
        </Button>
        <div className="report-top-actions">
          <Button variant="secondary" onClick={handlePrint}>
            <Printer size={16} /> Baixar PDF / Imprimir
          </Button>
          <Button
            onClick={() => setIsEvaluated(true)}
            disabled={isEvaluated}
            className={isEvaluated ? 'btn-evaluated' : ''}
          >
            {isEvaluated ? (
              <>
                <CheckCircle2 size={16} /> Avaliado pelo Fisioterapeuta
              </>
            ) : (
              'Marcar como avaliado'
            )}
          </Button>
        </div>
      </div>

      {/* Cabeçalho do Laudo Clínico */}
      <header className="report-header">
        <div>
          <h1>Relatório da sessão</h1>
          <p className="mu">
            {report.paciente_id || 'Paciente'} · {report.case_id || report.exercicio_id} {report.exercicio_nome} ·{' '}
            {report.valid_repetitions} de {report.target_repetitions || 5} repetições válidas
          </p>
        </div>
        <StatusChip
          level={riskLevel}
          label={riskLabel}
          symbol={report.risk_symbol}
          style={{ fontSize: '15px', padding: '8px 16px' }}
        />
      </header>

      {/* Grade Principal (1.6fr / 1fr conforme mock 04-Relatorio-Sessao.dc.html) */}
      <div className="g report-main-grid" style={{ gridTemplateColumns: '1.6fr 1fr' }}>
        {/* Coluna Esquerda: Player, Timeline e Evidências */}
        <div className="g" style={{ gap: '20px' }}>
          <Card className="player-card">
            <VideoPlayer
              src={report.annotated_video_url}
              seekTime={seekTarget}
              onTimeUpdate={(t) => setCurrentTime(t)}
              onLoadedMetadata={(d) => setDuration(d)}
            />

            <div style={{ marginTop: '16px' }}>
              <Timeline
                events={report.events}
                duration={duration}
                currentTime={currentTime}
                onSeek={handleSeek}
              />
            </div>
          </Card>

          {/* Galeria de Evidências Fotográficas dos Desvios e Picos */}
          <Card className="evidence-card">
            <div className="evidence-header">
              <h2>Evidências Visuais e Snapshots</h2>
              <span className="mu">{report.evidence_urls.length} captura(s) registradas</span>
            </div>

            {report.evidence_urls.length === 0 ? (
              <p className="mu">Nenhuma evidência fotográfica registrada para esta sessão.</p>
            ) : (
              <div className="evidence-grid">
                {report.evidence_urls.map((ev, idx) => (
                  <article
                    key={idx}
                    className="evidence-item"
                    onClick={() => setSelectedEvidence(ev)}
                    title="Clique para ampliar o frame de evidência"
                  >
                    <div className="evidence-thumb-wrapper">
                      <img
                        src={ev.url}
                        alt={ev.descricao}
                        loading="lazy"
                        className="evidence-thumb"
                      />
                      <span className="evidence-zoom-overlay">
                        <ZoomIn size={16} />
                      </span>
                    </div>
                    <div className="evidence-meta">
                      <strong>{ev.label}</strong>
                      <small className="mu">{ev.descricao}</small>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Coluna Direita: Métricas, Comparação Clínica e Justificativas */}
        <div className="g report-sidebar-column" style={{ alignContent: 'start', gap: '20px' }}>
          {/* Card: Conformidade Biomecânica */}
          <Card>
            <h2>Conformidade Biomecânica</h2>
            <div className="compliance-display">
              <span className="compliance-number">{complianceFormatted}</span>
              <span className="mu"> / 100%</span>
            </div>
            <p className="mu" style={{ marginTop: '4px' }}>
              Válidas: <strong>{report.valid_repetitions}</strong> · Inválidas: <strong>{report.invalid_repetitions}</strong> · Desvios: <strong>{report.total_deviations}</strong>
            </p>
            <div style={{ marginTop: '12px' }}>
              <StatusChip
                level={riskLevel}
                label={
                  report.total_deviations === 0
                    ? 'Execução em conformidade com o plano'
                    : `${report.total_deviations} desvio(s) biomecânico(s) detectado(s)`
                }
              />
            </div>
          </Card>

          {/* Card: Comparação Clínica */}
          <Card>
            <h2>Comparação clínica</h2>
            <div className="clinical-row">
              <span>Prescrição do plano</span>
              <StatusChip
                level={report.comparacao_clinica?.plano?.status || 'ok'}
                label={report.comparacao_clinica?.plano?.label || 'Conforme prescrição'}
              />
            </div>
            <div className="clinical-row">
              <span>Laudo médico</span>
              <StatusChip
                level={report.comparacao_clinica?.laudo?.status || 'ok'}
                label={report.comparacao_clinica?.laudo?.label || 'Amplitude dentro do limite'}
              />
            </div>
            <div className="clinical-row">
              <span>Inconsistência</span>
              <StatusChip
                level="info"
                label={report.comparacao_clinica?.inconsistencia?.label || 'Nenhuma detectada'}
              />
            </div>

            <p className="mu legal-disclaimer" style={{ marginTop: '14px' }}>
              {report.aviso_legal}
            </p>
          </Card>

          {/* Card: Justificativas Explicáveis */}
          <Card>
            <h2>Justificativas do Algoritmo</h2>
            {report.justificativas.length === 0 ? (
              <p className="mu">Nenhuma justificativa adversa: movimento executado dentro dos limiares de segurança.</p>
            ) : (
              <ul className="justificativas-list">
                {report.justificativas.map((just, idx) => (
                  <li key={idx} className="justificativa-item">
                    <span>{just}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* Modal Lightbox para Inspeção de Snapshot em Tamanho Real */}
      {selectedEvidence && (
        <div className="lightbox-backdrop" onClick={() => setSelectedEvidence(null)}>
          <div className="lightbox-modal" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-header">
              <div>
                <strong>{selectedEvidence.label}</strong>
                <p className="mu">{selectedEvidence.descricao}</p>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={() => setSelectedEvidence(null)}
                aria-label="Fechar"
              >
                <X size={20} />
              </button>
            </div>
            <div className="lightbox-body">
              <img
                src={selectedEvidence.url}
                alt={selectedEvidence.descricao}
                className="lightbox-image"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
