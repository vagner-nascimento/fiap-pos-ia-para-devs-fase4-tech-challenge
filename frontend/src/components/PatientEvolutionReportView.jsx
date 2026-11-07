import React, { useState, useEffect, useCallback } from 'react';
import {
  listPatients,
  getPatientEvolutionReport,
  seedPatientEvolutionDemo,
  evaluatePatientEvolution,
} from '../api/patients';

function statusBadgeMeta(status) {
  switch (status) {
    case 'critico':
    case 'crit':
      return {
        symbol: '■',
        label: 'Crítico',
        className: 'fc-status-chip fc-status-critico',
      };
    case 'atencao':
    case 'warn':
      return {
        symbol: '▲',
        label: 'Atenção',
        className: 'fc-status-chip fc-status-atencao',
      };
    case 'verde':
    case 'ok':
    default:
      return {
        symbol: '●',
        label: 'Adequado',
        className: 'fc-status-chip fc-status-verde',
      };
  }
}

function formatDelta(val, unit = '', invertGood = false) {
  const num = Number(val || 0);
  const sign = num > 0 ? '+' : '';
  const isGood = invertGood ? num <= 0 : num >= 0;
  return {
    text: `${sign}${num.toFixed(1)}${unit}`,
    toneClass: num === 0 ? 'fc-delta-neutral' : isGood ? 'fc-delta-positive' : 'fc-delta-negative',
  };
}

/**
 * Gráfico SVG Longitudinal para evolução por dia (Amplitude, Consistência e Dor).
 */
function EvolutionLineChart({
  days = [],
  metricKey,
  label,
  unit,
  minDomain = 0,
  maxDomain = 100,
  targetLine = null,
  targetLabel = '',
}) {
  if (!days || days.length === 0) {
    return <p className="muted">Sem dados por dia para exibir o gráfico.</p>;
  }

  const width = 460;
  const height = 180;
  const padLeft = 42;
  const padRight = 24;
  const padTop = 22;
  const padBottom = 34;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const values = days.map((d) => Number(d[metricKey] || 0));
  const rawMax = Math.max(maxDomain, ...values, targetLine || 0);
  const rawMin = Math.min(minDomain, ...values);
  const domainSpan = Math.max(1, rawMax - rawMin);

  const toX = (idx) => {
    if (days.length === 1) return padLeft + plotW / 2;
    return padLeft + (idx / (days.length - 1)) * plotW;
  };

  const toY = (val) => {
    const ratio = (val - rawMin) / domainSpan;
    return padTop + plotH - Math.max(0, Math.min(1, ratio)) * plotH;
  };

  const points = days.map((d, idx) => ({
    x: toX(idx),
    y: toY(Number(d[metricKey] || 0)),
    val: Number(d[metricKey] || 0),
    day: d.dia_tratamento,
  }));

  const polylinePoints = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const areaPoints = `${points[0].x.toFixed(1)},${(padTop + plotH).toFixed(1)} ${polylinePoints} ${points[points.length - 1].x.toFixed(1)},${(padTop + plotH).toFixed(1)}`;

  return (
    <div className="fc-chart-box">
      <div className="fc-chart-header">
        <strong>{label}</strong>
        {targetLine !== null && targetLine !== undefined && (
          <span className="fc-chart-target-caption">
            Ref.: {targetLabel || `${targetLine}${unit}`}
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="fc-evolution-svg"
        role="img"
        aria-label={`Gráfico de evolução de ${label}`}
      >
        {[0, 0.5, 1].map((step) => {
          const val = rawMin + step * domainSpan;
          const y = toY(val);
          return (
            <g key={step}>
              <line
                x1={padLeft}
                y1={y}
                x2={width - padRight}
                y2={y}
                stroke="var(--fc-border)"
                strokeDasharray="3 3"
              />
              <text
                x={padLeft - 6}
                y={y + 4}
                textAnchor="end"
                fontSize="10"
                fill="var(--fc-text-muted)"
                fontFamily="var(--fc-font)"
              >
                {val.toFixed(0)}{unit}
              </text>
            </g>
          );
        })}

        {targetLine !== null && targetLine !== undefined && targetLine >= rawMin && targetLine <= rawMax && (
          <line
            x1={padLeft}
            y1={toY(targetLine)}
            x2={width - padRight}
            y2={toY(targetLine)}
            stroke="var(--fc-warn-fg)"
            strokeWidth="1.5"
            strokeDasharray="5 4"
          />
        )}

        <polygon points={areaPoints} fill="var(--fc-primary-soft)" opacity="0.55" />
        <polyline
          fill="none"
          stroke="var(--fc-primary)"
          strokeWidth="2.5"
          points={polylinePoints}
        />

        {points.map((pt) => (
          <g key={pt.day}>
            <circle
              cx={pt.x}
              cy={pt.y}
              r="5"
              fill="var(--fc-surface)"
              stroke="var(--fc-primary)"
              strokeWidth="2.5"
            />
            <text
              x={pt.x}
              y={pt.y - 9}
              textAnchor="middle"
              fontSize="11"
              fontWeight="600"
              fill="var(--fc-text)"
              fontFamily="var(--fc-font)"
            >
              {pt.val.toFixed(1)}{unit}
            </text>
            <text
              x={pt.x}
              y={height - 10}
              textAnchor="middle"
              fontSize="11"
              fill="var(--fc-text-muted)"
            >
              Dia {pt.day}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default function PatientEvolutionReportView({
  initialPatientId = 'PAC-001',
  onSelectSession,
  onOpenAlerts,
}) {
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(initialPatientId || 'PAC-001');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [evalNotes, setEvalNotes] = useState('');
  const [expandedSessionId, setExpandedSessionId] = useState(null);

  useEffect(() => {
    if (initialPatientId) {
      setSelectedPatientId(initialPatientId);
    }
  }, [initialPatientId]);

  const loadData = useCallback(async (patientId) => {
    setLoading(true);
    setError(null);
    try {
      const [patientsRes, reportRes] = await Promise.all([
        listPatients(),
        getPatientEvolutionReport(patientId),
      ]);
      setPatients(Array.isArray(patientsRes) ? patientsRes : patientsRes.items || []);
      setReport(reportRes);
      setEvalNotes(reportRes.observacoes_avaliacao_final || '');
    } catch (err) {
      setError(err.message || 'Erro ao carregar o relatório de evolução do paciente.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(selectedPatientId);
  }, [selectedPatientId, loadData]);

  const handleSeedMultiDay = async () => {
    setSeeding(true);
    setFeedback(null);
    setError(null);
    try {
      const updated = await seedPatientEvolutionDemo(selectedPatientId);
      setReport(updated);
      setEvalNotes(updated.observacoes_avaliacao_final || '');
      setFeedback('Jornada multi-dias (com exercícios por dia, séries e repetições) gerada com sucesso!');
    } catch (err) {
      setError(err.message || 'Falha ao simular jornada multi-dias.');
    } finally {
      setSeeding(false);
    }
  };

  const handleEvaluateEvolution = async (e) => {
    e.preventDefault();
    setEvaluating(true);
    setFeedback(null);
    setError(null);
    try {
      const updated = await evaluatePatientEvolution(selectedPatientId, {
        avaliado: true,
        observacoes: evalNotes,
      });
      setReport(updated);
      setFeedback('Avaliação final longitudinal registrada pelo fisioterapeuta/médico.');
    } catch (err) {
      setError(err.message || 'Falha ao registrar avaliação final.');
    } finally {
      setEvaluating(false);
    }
  };

  if (loading && !report) {
    return (
      <div className="fc-loading-box">
        <div className="spin-indicator" />
        <span>Calculando relatório longitudinal de evolução do paciente...</span>
      </div>
    );
  }

  const patientObj = report?.patient || {};
  const laudoObj = report?.laudo || {};
  const planoObj = report?.plano || {};
  const metrics = report?.metricas_globais || {};
  const globalBadge = statusBadgeMeta(metrics.classificacao_geral || 'verde');
  const ampDelta = formatDelta(metrics.amplitude_delta, '°', false);
  const consDelta = formatDelta(metrics.consistencia_delta, '%', false);
  const painDelta = formatDelta(metrics.dor_delta_0_10, '', true);

  const totalRepsValidas = (report?.evolucao_por_dia || []).reduce(
    (acc, d) => acc + (d.total_repeticoes_validas || 0),
    0
  );
  const totalRepsPrescritas = (report?.evolucao_por_dia || []).reduce(
    (acc, d) => acc + (d.total_repeticoes_prescritas || 0),
    0
  );

  return (
    <div className="fc-evolution-page">
      {/* Header da página */}
      <div className="fc-page-header no-print">
        <div>
          <div className="fc-breadcrumb">
            Pacientes &rsaquo; {patientObj.paciente_id || selectedPatientId} &rsaquo; Relatório Final de Evolução Longitudinal
          </div>
          <h2>Relatório Final de Evolução — {patientObj.nome || selectedPatientId}</h2>
          <p className="muted">
            Análise longitudinal de <strong>Amplitude</strong>, <strong>Consistência Biomecânica</strong> e{' '}
            <strong>Nível de Dor</strong> ao longo de{' '}
            <strong>{metrics.dias_previstos || planoObj.dias_tratamento || 3} dias de tratamento</strong> (exercícios por dia com n séries &times; m repetições).
          </p>
        </div>

        <div className="fc-header-actions">
          <label className="fc-inline-select-label">
            <span>Paciente:</span>
            <select
              className="fc-select"
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
            >
              {patients.map((p) => (
                <option key={p.paciente_id} value={p.paciente_id}>
                  {p.paciente_id} — {p.nome}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="btn-secondary"
            onClick={handleSeedMultiDay}
            disabled={seeding}
          >
            {seeding ? 'Simulando...' : 'Simular Jornada Multi-Dias'}
          </button>

          {onOpenAlerts && (
            <button type="button" className="btn-secondary" onClick={onOpenAlerts}>
              Painel de Alertas ({report?.alertas_paciente?.length || 0})
            </button>
          )}

          <button
            type="button"
            className="btn-secondary"
            onClick={() => window.print()}
          >
            Imprimir / Exportar PDF
          </button>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {feedback && <div className="fc-feedback-banner">{feedback}</div>}

      {report && (
        <>
          {/* Contexto Clínico do Plano e Laudo */}
          <div className="card fc-context-bar">
            <div className="fc-context-bar-grid">
              <div>
                <span className="fc-meta-label">Paciente &amp; Plano</span>
                <strong>
                  {patientObj.nome} ({patientObj.paciente_id})
                </strong>
                <span className="muted"> · Plano {planoObj.plano_id || 'Ativo'}</span>
              </div>
              <div>
                <span className="fc-meta-label">Laudo / Região &amp; Lesão</span>
                <strong>{laudoObj.lesao || 'Reabilitação motora'}</strong> — {laudoObj.regiao || 'Articulação'}
              </div>
              <div>
                <span className="fc-meta-label">Jornada Concluída</span>
                <strong className="fc-mono">
                  {metrics.dias_concluidos}/{metrics.dias_previstos} dias
                </strong>{' '}
                <span className="muted">
                  ({metrics.total_sessoes_concluidas}/{metrics.total_sessoes_previstas} sessões realizadas)
                </span>
              </div>
              <div>
                <span className="fc-meta-label">Status Longitudinal</span>
                <div style={{ marginTop: 4, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span className={globalBadge.className}>
                    {globalBadge.symbol} {metrics.label_geral || globalBadge.label}
                  </span>
                  {report.avaliado_evolucao && (
                    <span className="fc-status-chip fc-status-verde">● Avaliado pelo Fisioterapeuta</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* 3 Pilares do Issue #7: Amplitude, Consistência e Nível de Dor */}
          <div className="fc-pillars-grid">
            {/* PILAR 1: AMPLITUDE */}
            <div className="card fc-pillar-card">
              <div className="fc-pillar-header">
                <span className="fc-pillar-tag">1. Amplitude Articular</span>
                <span className={`fc-delta-pill ${ampDelta.toneClass}`}>
                  {ampDelta.text} no tratamento
                </span>
              </div>
              <div className="fc-pillar-main-values">
                <div>
                  <span className="fc-meta-label">Dia Inicial</span>
                  <div className="fc-kpi-number">{Number(metrics.amplitude_inicial || 0).toFixed(1)}°</div>
                </div>
                <span className="fc-arrow-sep">&rarr;</span>
                <div>
                  <span className="fc-meta-label">Dia Atual</span>
                  <div className="fc-kpi-number fc-kpi-highlight">{Number(metrics.amplitude_atual || 0).toFixed(1)}°</div>
                </div>
                <div>
                  <span className="fc-meta-label">Pico Máximo</span>
                  <div className="fc-kpi-number">{Number(metrics.amplitude_maxima_atingida || 0).toFixed(1)}°</div>
                </div>
              </div>
              <div className="fc-comparison-footer">
                <div>
                  <span className="fc-meta-label">Faixa esperada (Plano):</span>{' '}
                  <strong className="fc-mono">{planoObj.amplitude_esperada_texto || '60 – 90'}°</strong>
                </div>
                <div>
                  <span className="fc-meta-label">Teto seguro (Laudo):</span>{' '}
                  <strong className="fc-mono">
                    {laudoObj.limite_amplitude_max ? `${laudoObj.limite_amplitude_max}°` : 'Sem restrição'}
                  </strong>
                </div>
              </div>
            </div>

            {/* PILAR 2: CONSISTÊNCIA */}
            <div className="card fc-pillar-card">
              <div className="fc-pillar-header">
                <span className="fc-pillar-tag">2. Consistência Biomecânica</span>
                <span className={`fc-delta-pill ${consDelta.toneClass}`}>
                  {consDelta.text} no tratamento
                </span>
              </div>
              <div className="fc-pillar-main-values">
                <div>
                  <span className="fc-meta-label">Dia Inicial</span>
                  <div className="fc-kpi-number">{Number(metrics.consistencia_inicial || 0).toFixed(1)}%</div>
                </div>
                <span className="fc-arrow-sep">&rarr;</span>
                <div>
                  <span className="fc-meta-label">Dia Atual</span>
                  <div className="fc-kpi-number fc-kpi-highlight">{Number(metrics.consistencia_atual || 0).toFixed(1)}%</div>
                </div>
                <div>
                  <span className="fc-meta-label">Média Geral</span>
                  <div className="fc-kpi-number">{Number(metrics.consistencia_media_global || 0).toFixed(1)}%</div>
                </div>
              </div>
              <div className="fc-comparison-footer">
                <div>
                  <span className="fc-meta-label">Volume Total (Séries &times; Reps):</span>{' '}
                  <strong className="fc-mono">
                    {totalRepsValidas}/{totalRepsPrescritas} válidas
                  </strong>
                </div>
                <div>
                  <span className="fc-meta-label">Taxa de Adesão:</span>{' '}
                  <strong className="fc-mono">{Number(metrics.percentual_adesao_plano || 0).toFixed(1)}%</strong>
                </div>
              </div>
            </div>

            {/* PILAR 3: NÍVEL DE DOR */}
            <div className="card fc-pillar-card">
              <div className="fc-pillar-header">
                <span className="fc-pillar-tag">3. Nível de Dor (0–10)</span>
                <span className={`fc-delta-pill ${painDelta.toneClass}`}>
                  {painDelta.text} pts no tratamento
                </span>
              </div>
              <div className="fc-pillar-main-values">
                <div>
                  <span className="fc-meta-label">Dia Inicial</span>
                  <div className="fc-kpi-number">{Number(metrics.dor_inicial_0_10 || 0).toFixed(1)}</div>
                </div>
                <span className="fc-arrow-sep">&rarr;</span>
                <div>
                  <span className="fc-meta-label">Dia Atual</span>
                  <div className="fc-kpi-number fc-kpi-highlight">{Number(metrics.dor_atual_0_10 || 0).toFixed(1)}</div>
                </div>
                <div>
                  <span className="fc-meta-label">Pico de Dor</span>
                  <div className="fc-kpi-number">{Number(metrics.dor_maxima_registrada_0_10 || 0).toFixed(1)}</div>
                </div>
              </div>
              <div className="fc-comparison-footer">
                <div>
                  <span className="fc-meta-label">Dor máxima aceitável (Plano):</span>{' '}
                  <strong className="fc-mono">&le; {planoObj.dor_maxima_aceitavel ?? 4}/10</strong>
                </div>
                <div>
                  <span className="fc-meta-label">Status de Tolerância:</span>{' '}
                  <strong className="fc-mono">
                    {Number(metrics.dor_atual_0_10 || 0) <= (planoObj.dor_maxima_aceitavel ?? 4)
                      ? '● Dentro do limite'
                      : '■ Acima do limite'}
                  </strong>
                </div>
              </div>
            </div>
          </div>

          {/* Gráficos Longitudinais por Dia de Tratamento */}
          <div className="card">
            <h3>Curvas de Evolução por Dia de Tratamento</h3>
            <p className="muted" style={{ marginBottom: 14 }}>
              Acompanhamento diário consolidando todos os exercícios prescritos e executados em cada dia (incluindo todas as séries e repetições).
            </p>
            <div className="fc-charts-grid-3">
              <EvolutionLineChart
                days={report.evolucao_por_dia}
                metricKey="amplitude_media_dia"
                label="Amplitude Média Diária (°)"
                unit="°"
                minDomain={30}
                maxDomain={165}
                targetLine={laudoObj.limite_amplitude_max || 90}
                targetLabel={`Teto Laudo ${laudoObj.limite_amplitude_max || 90}°`}
              />
              <EvolutionLineChart
                days={report.evolucao_por_dia}
                metricKey="consistencia_media_dia"
                label="Consistência Biomecânica (%)"
                unit="%"
                minDomain={40}
                maxDomain={100}
                targetLine={80}
                targetLabel="Meta ≥ 80%"
              />
              <EvolutionLineChart
                days={report.evolucao_por_dia}
                metricKey="dor_maxima_dia_0_10"
                label="Nível de Dor Máximo no Dia (0–10)"
                unit=""
                minDomain={0}
                maxDomain={10}
                targetLine={planoObj.dor_maxima_aceitavel ?? 4}
                targetLabel={`Limite Plano ≤ ${planoObj.dor_maxima_aceitavel ?? 4}`}
              />
            </div>
          </div>

          {/* Tabela Resumo por Dia de Tratamento */}
          <div className="card">
            <h3>Jornada por Dia de Tratamento</h3>
            <div className="table-responsive">
              <table className="sessions-table">
                <thead>
                  <tr>
                    <th>Dia</th>
                    <th>Exercícios Concluídos / Prescritos no Dia</th>
                    <th>Volume (Reps Válidas / Prescritas)</th>
                    <th>Amplitude Média / Máx</th>
                    <th>Consistência Média</th>
                    <th>Dor Média / Máx (0–10)</th>
                    <th>Desvios</th>
                    <th>Status do Dia</th>
                  </tr>
                </thead>
                <tbody>
                  {(report.evolucao_por_dia || []).map((dia) => {
                    const badge = statusBadgeMeta(dia.risk_classification);
                    return (
                      <tr key={dia.dia_tratamento}>
                        <td>
                          <strong>{dia.label || `Dia ${dia.dia_tratamento}`}</strong>
                        </td>
                        <td className="fc-mono">
                          <strong>{dia.exercicios_concluidos}</strong> / {dia.exercicios_prescritos} exercício(s)
                        </td>
                        <td className="fc-mono">
                          <strong>{dia.total_repeticoes_validas}</strong> / {dia.total_repeticoes_prescritas} reps ({dia.total_repeticoes_realizadas} exec.)
                        </td>
                        <td className="fc-mono">
                          {Number(dia.amplitude_media_dia).toFixed(1)}° / máx {Number(dia.amplitude_maxima_dia).toFixed(1)}°
                        </td>
                        <td className="fc-mono">{Number(dia.consistencia_media_dia).toFixed(1)}%</td>
                        <td className="fc-mono">
                          {Number(dia.dor_media_dia_0_10).toFixed(1)} / máx {Number(dia.dor_maxima_dia_0_10).toFixed(1)}
                        </td>
                        <td className="fc-mono">{dia.total_desvios_dia || 0}</td>
                        <td>
                          <span className={badge.className}>
                            {badge.symbol} {badge.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Evolução Detalhada por Exercício Prescrito (n séries × m repetições) */}
          <div className="card">
            <h3>Evolução por Exercício Prescrito (Séries &times; Repetições ao longo dos Dias)</h3>
            <p className="muted" style={{ marginBottom: 16 }}>
              Detalhamento longitudinal de cada exercício do plano (com seus respectivos dias prescritos e decomposição por Série 1..N).
            </p>

            <div className="fc-exercises-evolution-list">
              {(report.evolucao_por_exercicio || []).map((ex) => {
                const exBadge = statusBadgeMeta(ex.status_evolucao);
                const exAmpDelta = formatDelta(ex.amplitude_delta, '°', false);
                const exConsDelta = formatDelta(ex.consistencia_delta, '%', false);
                const exPainDelta = formatDelta(ex.dor_delta, '', true);
                const diasLabel =
                  Array.isArray(ex.dias_prescritos) && ex.dias_prescritos.length > 0
                    ? ex.dias_prescritos.map((d) => `Dia ${d}`).join(', ')
                    : `Dias 1..${ex.dias_previstos}`;

                return (
                  <div key={`${ex.slot_id}-${ex.exercicio_id}`} className="fc-exercise-evo-block">
                    <div className="fc-exercise-evo-header">
                      <div>
                        <span className="fc-slot-pill">{ex.slot_id}</span>
                        <strong style={{ fontSize: '1.05rem', marginLeft: 8 }}>
                          {ex.exercicio_id} · {ex.exercicio_nome}
                        </strong>
                        <span className="muted" style={{ marginLeft: 10 }}>
                          Prescrição: <strong>{ex.series_prescritas} séries &times; {ex.repeticoes_por_serie} reps</strong> ({ex.total_repeticoes_dia} reps/dia) &bull; Dias prescritos: <strong>{diasLabel}</strong>
                        </span>
                      </div>

                      <div className="fc-exercise-evo-deltas">
                        <span className={`fc-delta-pill ${exAmpDelta.toneClass}`}>
                          Amplitude: {exAmpDelta.text}
                        </span>
                        <span className={`fc-delta-pill ${exConsDelta.toneClass}`}>
                          Consistência: {exConsDelta.text}
                        </span>
                        <span className={`fc-delta-pill ${exPainDelta.toneClass}`}>
                          Dor: {exPainDelta.text}
                        </span>
                        <span className={exBadge.className}>
                          {exBadge.symbol} {exBadge.label}
                        </span>
                      </div>
                    </div>

                    {(!ex.sessoes || ex.sessoes.length === 0) ? (
                      <p className="muted">Nenhuma sessão executada para este exercício ainda.</p>
                    ) : (
                      <div className="table-responsive">
                        <table className="sessions-table">
                          <thead>
                            <tr>
                              <th>Dia</th>
                              <th>Séries &times; Reps</th>
                              <th>Reps (Válidas / Exec / Meta)</th>
                              <th>Amplitude Média / Máx</th>
                              <th>Consistência</th>
                              <th>Dor (0–10)</th>
                              <th>Desvios</th>
                              <th>Séries (1..N)</th>
                              <th>Ações</th>
                            </tr>
                          </thead>
                          <tbody>
                            {ex.sessoes.map((sess) => {
                              const isExpanded = expandedSessionId === sess.session_id;
                              return (
                                <React.Fragment key={sess.session_id}>
                                  <tr>
                                    <td>
                                      <strong>Dia {sess.dia_tratamento}</strong>
                                    </td>
                                    <td className="fc-mono">
                                      {sess.series_prescritas} &times; {sess.repeticoes_por_serie}
                                    </td>
                                    <td className="fc-mono">
                                      <strong>{sess.valid_repetitions}</strong> / {sess.completed_repetitions} / {sess.target_repetitions}
                                    </td>
                                    <td className="fc-mono">
                                      <strong>{Number(sess.amplitude_media).toFixed(1)}°</strong> (máx {Number(sess.amplitude_maxima).toFixed(1)}°)
                                    </td>
                                    <td className="fc-mono">
                                      <strong>{Number(sess.consistencia_score).toFixed(1)}%</strong>
                                    </td>
                                    <td className="fc-mono">
                                      <strong>{Number(sess.dor_score_0_10).toFixed(1)}</strong>/10 ({Number(sess.dor_percentual_tempo).toFixed(0)}% t)
                                    </td>
                                    <td>
                                      {(sess.total_deviations || 0) > 0 ? (
                                        <span className="fc-status-chip fc-status-atencao">
                                          ▲ {sess.total_deviations} desvio(s)
                                        </span>
                                      ) : (
                                        <span className="fc-status-chip fc-status-verde">● Sem desvio</span>
                                      )}
                                    </td>
                                    <td>
                                      <button
                                        type="button"
                                        className="btn-link"
                                        onClick={() =>
                                          setExpandedSessionId(isExpanded ? null : sess.session_id)
                                        }
                                      >
                                        {isExpanded
                                          ? 'Ocultar séries'
                                          : `Ver ${sess.series_breakdown?.length || sess.series_prescritas} séries`}
                                      </button>
                                    </td>
                                    <td>
                                      {onSelectSession && (
                                        <button
                                          type="button"
                                          className="btn-secondary btn-sm"
                                          onClick={() => onSelectSession(sess.session_id)}
                                        >
                                          Relatório da Sessão
                                        </button>
                                      )}
                                    </td>
                                  </tr>

                                  {isExpanded && sess.series_breakdown && sess.series_breakdown.length > 0 && (
                                    <tr className="fc-series-breakdown-row">
                                      <td colSpan={9}>
                                        <div className="fc-series-chips-container">
                                          {sess.series_breakdown.map((sb) => (
                                            <div key={sb.serie_index || sb.serie_numero} className="fc-series-mini-card">
                                              <div className="fc-series-mini-title">
                                                {sb.label || `Série ${sb.serie_index || sb.serie_numero}`}
                                              </div>
                                              <div className="fc-mono">
                                                Reps válidas: <strong>{sb.repeticoes_validas}/{sb.repeticoes_alvo}</strong> ({sb.repeticoes_completadas ?? sb.repeticoes_executadas} exec.)
                                              </div>
                                              <div className="fc-mono">
                                                Amplitude: <strong>{Number(sb.amplitude_media).toFixed(1)}°</strong> (máx {Number(sb.amplitude_maxima).toFixed(1)}°)
                                              </div>
                                              <div className="fc-mono">
                                                Consistência da série: <strong>{Number(sb.consistencia_serie).toFixed(1)}%</strong>
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </td>
                                    </tr>
                                  )}
                                </React.Fragment>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Parecer de Apoio à Decisão Clínica & Registro de Avaliação Final */}
          <div className="fc-two-col-grid">
            <div className="card">
              <h3>Parecer Longitudinal de Apoio à Decisão Clínica</h3>
              <p className="fc-clinical-disclaimer">
                {report.aviso_legal || 'Apoio à decisão clínica (não substitui diagnóstico médico/fisioterapêutico).'}
              </p>
              <ul className="fc-recommendations-list" style={{ marginTop: 12 }}>
                {(Array.isArray(report.parecer_clinico)
                  ? report.parecer_clinico
                  : [report.parecer_clinico]
                )
                  .filter(Boolean)
                  .map((pItem, idx) => (
                    <li key={idx}>{pItem}</li>
                  ))}
              </ul>

              <h4 style={{ marginTop: 16, marginBottom: 8 }}>Recomendações para o Plano Fisioterapêutico</h4>
              <ul className="fc-recommendations-list">
                {(report.recomendacoes_plano || []).map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>

            <div className="card">
              <h3>Avaliação Final do Fisioterapeuta / Médico</h3>
              <p className="muted" style={{ marginBottom: 12 }}>
                Registre a conclusão clínica sobre a evolução multi-dias do paciente e eventuais ajustes na conduta.
              </p>
              <form onSubmit={handleEvaluateEvolution}>
                <div className="form-group">
                  <label htmlFor="eval-notes">Observações Clínicas Finais</label>
                  <textarea
                    id="eval-notes"
                    rows={4}
                    className="fc-textarea"
                    placeholder="Ex.: Paciente apresentou ganho consistente de amplitude articular (+21°) e redução da dor de 5,8/10 para 1,5/10 ao longo dos 3 dias. Apta para progressão..."
                    value={evalNotes}
                    onChange={(e) => setEvalNotes(e.target.value)}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
                  <span className="muted">
                    Status:{' '}
                    <strong>
                      {report.avaliado_evolucao ? '● Evolução avaliada' : '▲ Pendente de avaliação'}
                    </strong>
                  </span>
                  <button type="submit" className="btn-primary" disabled={evaluating}>
                    {evaluating ? 'Salvando...' : 'Marcar Evolução como Avaliada'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
