import React, { useState, useEffect, useCallback } from 'react';
import { listAlerts, updateAlertStatus } from '../api/alerts';

function severityMeta(severidade) {
  switch (severidade) {
    case 'critico':
      return {
        symbol: '■',
        label: 'Crítico',
        chipClass: 'fc-status-chip fc-status-critico',
        rowClass: 'fc-alert-card fc-alert-critico',
      };
    case 'atencao':
      return {
        symbol: '▲',
        label: 'Atenção',
        chipClass: 'fc-status-chip fc-status-atencao',
        rowClass: 'fc-alert-card fc-alert-atencao',
      };
    case 'verde':
    default:
      return {
        symbol: '●',
        label: 'Adequado',
        chipClass: 'fc-status-chip fc-status-verde',
        rowClass: 'fc-alert-card fc-alert-verde',
      };
  }
}

export default function AlertsPanelView({ onSelectSession, onOpenEvolution }) {
  const [alerts, setAlerts] = useState([]);
  const [counters, setCounters] = useState({
    total: 0,
    novos: 0,
    lidos: 0,
    tratados: 0,
    criticos: 0,
    atencao: 0,
    verdes: 0,
  });
  const [severityFilter, setSeverityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState(null);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAlerts({
        severidade: severityFilter || undefined,
        estado: statusFilter || undefined,
      });
      setAlerts(res.alertas || res.items || []);
      if (res.contadores) {
        setCounters(res.contadores);
      }
    } catch (err) {
      setError(err.message || 'Erro ao carregar o painel de alertas clínicos.');
    } finally {
      setLoading(false);
    }
  }, [severityFilter, statusFilter]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleToggleStatus = async (alertItem, nextStatus) => {
    setUpdatingId(alertItem.alerta_id);
    setError(null);
    try {
      await updateAlertStatus(alertItem.alerta_id, nextStatus);
      await loadAlerts();
    } catch (err) {
      setError(err.message || 'Falha ao atualizar o status do alerta.');
    } finally {
      setUpdatingId(null);
    }
  };

  const pendingAlerts = alerts.filter((a) => (a.estado || a.status) !== 'tratado');
  const treatedAlerts = alerts.filter((a) => (a.estado || a.status) === 'tratado');
  const pendingCount = (counters.novos || 0) + (counters.lidos || 0);

  return (
    <div className="fc-alerts-page">
      <div className="fc-page-header">
        <div>
          <div className="fc-breadcrumb">Clínica &rsaquo; Painel de Alertas</div>
          <h2>Painel de Alertas Clínicos</h2>
          <p className="muted">
            Monitoramento automático de picos de dor, desvios de amplitude articular, compensações posturais e queda de adesão.
          </p>
        </div>

        {/* Contadores de Severidade (Padrão DESIGN.md: Símbolo + Texto + Cor) */}
        <div className="fc-alert-counters-bar">
          <span className="fc-status-chip fc-status-critico">
            ■ {counters.criticos} Crítico{counters.criticos === 1 ? '' : 's'}
          </span>
          <span className="fc-status-chip fc-status-atencao">
            ▲ {counters.atencao} Atenção
          </span>
          <span className="fc-status-chip fc-status-verde">
            ● {counters.verdes} Adequado{counters.verdes === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      {/* Barra de filtros */}
      <div className="card fc-filters-bar">
        <div className="fc-filter-group">
          <span className="fc-meta-label">Filtrar por Severidade:</span>
          <div className="fc-pill-group">
            {[
              { value: '', label: 'Todos' },
              { value: 'critico', label: '■ Críticos' },
              { value: 'atencao', label: '▲ Atenção' },
              { value: 'verde', label: '● Adequados' },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`fc-filter-pill ${severityFilter === opt.value ? 'active' : ''}`}
                onClick={() => setSeverityFilter(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="fc-filter-group">
          <span className="fc-meta-label">Status de Tratativa:</span>
          <div className="fc-pill-group">
            {[
              { value: '', label: `Todos (${counters.total || pendingCount + (counters.tratados || 0)})` },
              { value: 'novo', label: `Novos / Pendentes (${pendingCount})` },
              { value: 'tratado', label: `Tratados (${counters.tratados || 0})` },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`fc-filter-pill ${statusFilter === opt.value ? 'active' : ''}`}
                onClick={() => setStatusFilter(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}

      {loading ? (
        <div className="fc-loading-box">
          <div className="spin-indicator" />
          <span>Carregando alertas clínicos...</span>
        </div>
      ) : (
        <>
          {/* Seção 1: Novos / Pendentes */}
          {statusFilter !== 'tratado' && (
            <div className="card">
              <h3>Novos / Pendentes de Avaliação ({pendingAlerts.length})</h3>
              {pendingAlerts.length === 0 ? (
                <p className="muted">Nenhum alerta pendente para os filtros selecionados.</p>
              ) : (
                <div className="fc-alerts-list">
                  {pendingAlerts.map((al) => {
                    const meta = severityMeta(al.severidade);
                    return (
                      <div key={al.alerta_id} className={meta.rowClass}>
                        <div className="fc-alert-card-main">
                          <div className="fc-alert-card-top">
                            <span className={meta.chipClass}>
                              {meta.symbol} {meta.label}
                            </span>
                            <strong>{al.titulo}</strong>
                            <span className="fc-mono muted">
                              {al.paciente_id} — {al.paciente_nome}
                            </span>
                            {al.dia_tratamento && (
                              <span className="fc-slot-pill">Dia {al.dia_tratamento}</span>
                            )}
                          </div>
                          <p className="fc-alert-msg">{al.motivo || al.mensagem}</p>
                          {al.evidencia_resumo && (
                            <p className="muted" style={{ marginTop: 4, fontSize: 12 }}>
                              Evidência: <strong>{al.evidencia_resumo}</strong>
                            </p>
                          )}
                        </div>

                        <div className="fc-alert-card-actions">
                          {al.session_id && onSelectSession && (
                            <button
                              type="button"
                              className="btn-secondary btn-sm"
                              onClick={() => onSelectSession(al.session_id)}
                            >
                              Abrir Sessão
                            </button>
                          )}
                          {onOpenEvolution && (
                            <button
                              type="button"
                              className="btn-secondary btn-sm"
                              onClick={() => onOpenEvolution(al.paciente_id)}
                            >
                              Ver Evolução
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn-primary btn-sm"
                            disabled={updatingId === al.alerta_id}
                            onClick={() => handleToggleStatus(al, 'tratado')}
                          >
                            {updatingId === al.alerta_id ? 'Salvando...' : 'Marcar como tratado'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Seção 2: Tratados */}
          {statusFilter !== 'novo' && (
            <div className="card">
              <h3>Alertas Tratados / Arquivados ({treatedAlerts.length})</h3>
              {treatedAlerts.length === 0 ? (
                <p className="muted">Nenhum alerta marcado como tratado ainda.</p>
              ) : (
                <div className="fc-alerts-list">
                  {treatedAlerts.map((al) => {
                    const meta = severityMeta(al.severidade);
                    return (
                      <div key={al.alerta_id} className={`${meta.rowClass} fc-alert-treated`}>
                        <div className="fc-alert-card-main">
                          <div className="fc-alert-card-top">
                            <span className={meta.chipClass}>
                              {meta.symbol} {meta.label}
                            </span>
                            <strong>{al.titulo}</strong>
                            <span className="fc-mono muted">
                              {al.paciente_id} — {al.paciente_nome}
                            </span>
                            <span className="fc-status-chip fc-status-verde">● Tratado</span>
                          </div>
                          <p className="fc-alert-msg">{al.motivo || al.mensagem}</p>
                        </div>

                        <div className="fc-alert-card-actions">
                          {onOpenEvolution && (
                            <button
                              type="button"
                              className="btn-secondary btn-sm"
                              onClick={() => onOpenEvolution(al.paciente_id)}
                            >
                              Ver Evolução
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn-link"
                            disabled={updatingId === al.alerta_id}
                            onClick={() => handleToggleStatus(al, 'novo')}
                          >
                            Reabrir
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
