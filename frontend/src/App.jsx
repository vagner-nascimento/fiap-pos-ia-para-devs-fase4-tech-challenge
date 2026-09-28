import { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle2, CircleAlert, Clock3, Database, LoaderCircle, RefreshCw } from 'lucide-react';
import { fetchHealth } from './api/health';

function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);

  const checkHealth = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const result = await fetchHealth();
      setHealth(result);
      setLastCheckedAt(new Date());
    } catch (requestError) {
      setHealth(null);
      setError(requestError.message || 'Não foi possível conectar à API.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { checkHealth(); }, [checkHealth]);

  const isHealthy = health?.status === 'healthy' && health?.database === 'healthy';
  const formattedCheckTime = lastCheckedAt
    ? lastCheckedAt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--:--';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark" aria-hidden="true">F</div>
        <div className="brand-copy"><strong>FIAP POS IA</strong><span>Operations</span></div>
        <nav className="main-nav" aria-label="Menu principal">
          <span className="nav-label">Monitoramento</span>
          <a className="nav-item active" href="#api-health" aria-current="page">
            <Activity size={18} strokeWidth={2.2} /><span>API Health</span>
          </a>
        </nav>
        <div className="sidebar-footer">
          <span className={`status-dot ${isHealthy ? '' : 'offline'}`} aria-hidden="true" /><span>Ambiente local</span>
        </div>
      </aside>

      <main className="content" id="api-health">
        <header className="page-header">
          <div>
            <p className="eyebrow">Monitoramento / Serviço</p>
            <h1>API Health</h1>
            <p className="page-description">Acompanhe a disponibilidade da API.</p>
          </div>
          <button className="refresh-button" type="button" onClick={checkHealth} disabled={isLoading}>
            <RefreshCw size={17} className={isLoading ? 'spin' : ''} /><span>{isLoading ? 'Consultando' : 'Atualizar'}</span>
          </button>
        </header>

        <section className={`health-banner ${isLoading ? 'pending' : isHealthy ? 'healthy' : 'unhealthy'}`} aria-live="polite">
          <div className="banner-icon">
            {isLoading ? <LoaderCircle className="spin" size={25} /> : isHealthy ? <CheckCircle2 size={25} /> : <CircleAlert size={25} />}
          </div>
          <div>
            <p className="banner-kicker">Status da aplicação</p>
            <h2>{isLoading ? 'Verificando conexão...' : isHealthy ? 'API operacional' : 'API indisponível'}</h2>
            <p>{isLoading ? 'Aguardando resposta do backend.' : error || 'A API e o banco de dados responderam corretamente.'}</p>
          </div>
        </section>

        <section className="metrics-grid" aria-label="Detalhes do health check">
          <article className="metric-card">
            <div className="metric-heading"><span>Status da API</span><Activity size={17} /></div>
            <strong>{health?.status || (error ? 'Erro' : '--')}</strong><small>GET /api/health</small>
          </article>
          <article className="metric-card">
            <div className="metric-heading"><span>Última consulta</span><Clock3 size={17} /></div>
            <strong>{formattedCheckTime}</strong><small>Horário local</small>
          </article>
          <article className="metric-card">
            <div className="metric-heading"><span>Banco de dados</span><Database size={17} /></div>
            <strong>{health?.database || (error ? 'Indisponível' : '--')}</strong><small>Conexão MongoDB</small>
          </article>
        </section>

        <section className="response-panel" aria-label="Resposta da API">
          <div className="panel-heading">
            <div><p className="eyebrow">Resposta recebida</p><h2>Health check</h2></div>
            <span className="method-badge">GET</span>
          </div>
          <pre>{health ? JSON.stringify(health, null, 2) : error ? JSON.stringify({ error }, null, 2) : '{ }'}</pre>
        </section>
      </main>
    </div>
  );
}

export default App;
