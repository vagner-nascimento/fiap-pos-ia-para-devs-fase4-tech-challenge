import { useState, useCallback, useEffect } from 'react';
import {
  Activity,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  Clock3,
  Database,
  Film,
  FileText,
  LoaderCircle,
  RefreshCw,
  HeartPulse,
} from 'lucide-react';
import { fetchHealth } from './api/health';
import { PlanAndReportView } from './components/PlanAndReportView';
import { SessionsListView } from './components/SessionsListView';
import { ProcessingView } from './components/ProcessingView';
import { SessionReportView } from './components/SessionReportView';
import { Card } from './components/ds/Card';
import { Button } from './components/ds/Button';

export default function App() {
  const [currentView, setCurrentView] = useState('sessions'); // 'plan' | 'sessions' | 'processing' | 'report' | 'health'
  const [activeSessionId, setActiveSessionId] = useState(null);

  // Estado da tela de Health Check
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState('');
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);

  const checkHealth = useCallback(async () => {
    setIsHealthLoading(true);
    setHealthError('');
    try {
      const result = await fetchHealth();
      setHealth(result);
      setLastCheckedAt(new Date());
    } catch (requestError) {
      setHealth(null);
      setHealthError(requestError.message || 'Não foi possível conectar à API.');
    } finally {
      setIsHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    if (currentView === 'health') {
      checkHealth();
    }
  }, [currentView, checkHealth]);

  const handleOpenReport = (sessionId) => {
    setActiveSessionId(sessionId);
    setCurrentView('report');
  };

  const handleOpenProcessing = (sessionId) => {
    setActiveSessionId(sessionId);
    setCurrentView('processing');
  };

  const handleBackToSessions = () => {
    setCurrentView('sessions');
  };

  const isHealthy = health?.status === 'healthy' && health?.database === 'healthy';
  const formattedCheckTime = lastCheckedAt
    ? lastCheckedAt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--:--';

  return (
    <div className="r app-container">
      {/* Sidebar Fixa 220px (Design System: --fc-primary-dark) */}
      <aside className="sb no-print" aria-label="Menu Principal">
        <b>Fisio Coach</b>
        <nav className="sidebar-nav">
          <button
            type="button"
            className={`sidebar-nav-item ${currentView === 'plan' ? 'on' : ''}`}
            onClick={() => setCurrentView('plan')}
          >
            <ClipboardList size={16} /> <span>Plano e laudo</span>
          </button>

          <button
            type="button"
            className={`sidebar-nav-item ${currentView === 'sessions' ? 'on' : ''}`}
            onClick={() => setCurrentView('sessions')}
          >
            <Film size={16} /> <span>Sessões</span>
          </button>

          {activeSessionId && (
            <button
              type="button"
              className={`sidebar-nav-item ${currentView === 'report' || currentView === 'processing' ? 'on' : ''}`}
              onClick={() => setCurrentView('report')}
            >
              <FileText size={16} /> <span>Relatório Atual</span>
            </button>
          )}

          <button
            type="button"
            className={`sidebar-nav-item ${currentView === 'health' ? 'on' : ''}`}
            onClick={() => setCurrentView('health')}
          >
            <HeartPulse size={16} /> <span>API Health</span>
          </button>
        </nav>
        <small>Fisioterapeuta</small>
      </aside>

      {/* Área de Conteúdo Principal */}
      <main className="m">
        {currentView === 'plan' && <PlanAndReportView />}

        {currentView === 'sessions' && (
          <SessionsListView
            onSelectSession={handleOpenReport}
            onSelectProcessing={handleOpenProcessing}
          />
        )}

        {currentView === 'processing' && activeSessionId && (
          <ProcessingView
            sessionId={activeSessionId}
            onViewReport={handleOpenReport}
            onBackToSessions={handleBackToSessions}
          />
        )}

        {currentView === 'report' && activeSessionId && (
          <SessionReportView
            sessionId={activeSessionId}
            onBackToSessions={handleBackToSessions}
          />
        )}

        {currentView === 'health' && (
          <div className="health-view">
            <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <p className="eyebrow mu">Monitoramento / Infraestrutura</p>
                <h1>API Health & Status</h1>
                <p className="page-description mu">Disponibilidade do backend FastAPI e do banco MongoDB</p>
              </div>
              <Button onClick={checkHealth} disabled={isHealthLoading}>
                <RefreshCw size={16} className={isHealthLoading ? 'spin' : ''} />
                <span>{isHealthLoading ? 'Consultando' : 'Atualizar'}</span>
              </Button>
            </header>

            <section
              className={`health-banner ${isHealthLoading ? 'pending' : isHealthy ? 'healthy' : 'unhealthy'}`}
              style={{
                background: isHealthy ? 'var(--fc-ok-bg)' : 'var(--fc-crit-bg)',
                color: isHealthy ? 'var(--fc-ok-fg)' : 'var(--fc-crit-fg)',
                padding: '20px',
                borderRadius: 'var(--fc-radius-card)',
                marginBottom: '20px',
                display: 'flex',
                gap: '16px',
                alignItems: 'center',
              }}
            >
              <div>
                {isHealthLoading ? (
                  <LoaderCircle className="spin" size={28} />
                ) : isHealthy ? (
                  <CheckCircle2 size={28} />
                ) : (
                  <CircleAlert size={28} />
                )}
              </div>
              <div>
                <strong style={{ fontSize: '18px', display: 'block' }}>
                  {isHealthLoading ? 'Verificando conexão...' : isHealthy ? 'API operacional' : 'API indisponível'}
                </strong>
                <p style={{ margin: 0, opacity: 0.9 }}>
                  {isHealthLoading
                    ? 'Aguardando resposta do container de backend.'
                    : healthError || 'O backend FastAPI e o banco de dados MongoDB responderam com sucesso.'}
                </p>
              </div>
            </section>

            <div className="g" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '20px' }}>
              <Card>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="mu">Status da API</span>
                  <Activity size={17} />
                </div>
                <strong style={{ fontSize: '20px', display: 'block', marginTop: '8px' }}>
                  {health?.status || (healthError ? 'Erro' : '--')}
                </strong>
                <small className="mu">GET /api/health</small>
              </Card>

              <Card>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="mu">Última consulta</span>
                  <Clock3 size={17} />
                </div>
                <strong style={{ fontSize: '20px', display: 'block', marginTop: '8px' }}>
                  {formattedCheckTime}
                </strong>
                <small className="mu">Horário local</small>
              </Card>

              <Card>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="mu">Banco de dados</span>
                  <Database size={17} />
                </div>
                <strong style={{ fontSize: '20px', display: 'block', marginTop: '8px' }}>
                  {health?.database || (healthError ? 'Indisponível' : '--')}
                </strong>
                <small className="mu">Conexão MongoDB 7</small>
              </Card>
            </div>

            <Card>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <h2>Resposta do Endpoint</h2>
                <span className="ch ne">GET /api/health</span>
              </div>
              <pre style={{ margin: 0, background: 'var(--fc-bg)', padding: '16px', borderRadius: '8px', fontSize: '13px', overflowX: 'auto' }}>
                {health ? JSON.stringify(health, null, 2) : healthError ? JSON.stringify({ error: healthError }, null, 2) : '{ }'}
              </pre>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
