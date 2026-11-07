import { useState, useCallback } from 'react';
import { Card } from './ds/Card';
import { Button } from './ds/Button';
import { StatusChip } from './ds/StatusChip';
import { listPatients, getPatientBundle } from '../api/patients';
import {
  Search,
  RefreshCw,
  FileText,
  PlayCircle,
  CircleAlert,
  ShieldCheck,
  ClipboardCheck,
  Dumbbell,
  UserCheck,
} from 'lucide-react';

/**
 * PatientPrescriptionView — Tela 2 ("Minha prescrição" — Visão do Paciente, Issue #4)
 * Implementa o Passo 2 da Jornada Principal (docs/jornada-proposta-001.md e PRD v1.2),
 * alinhada ao Design System (docs/design/DESIGN.md) e ao Mock 02-Paciente-Envio.dc.html.
 * Por privacidade (LGPD), não lista outros pacientes: o paciente deve buscar seu próprio
 * cadastro informando seu nome ou código identificador (ex.: PAC-001).
 */
export function PatientPrescriptionView({ onSelectSession, onSelectProcessing }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchEmpty, setSearchEmpty] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const loadPatientPrescription = useCallback(async (pacienteId) => {
    if (!pacienteId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getPatientBundle(pacienteId);
      setBundle(data);
    } catch (err) {
      setError(err.message || 'Não foi possível carregar os dados de prescrição e laudo.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearchSubmit = async (e) => {
    if (e) e.preventDefault();
    const trimmed = searchQuery.trim();
    setError(null);
    setSearchEmpty(false);

    if (trimmed.length < 2) {
      setError('Por favor, informe pelo menos 2 caracteres do seu nome ou seu código (ex.: PAC-001).');
      return;
    }

    setHasSearched(true);
    setLoading(true);

    try {
      const results = await listPatients(trimmed);

      if (results.length === 0) {
        setSearchEmpty(true);
        setBundle(null);
      } else {
        // Prioriza correspondência exata por ID ou nome, sem expor listagem de outros pacientes
        const normalizedQuery = trimmed.toLowerCase();
        const bestMatch =
          results.find(
            (p) =>
              p.paciente_id.toLowerCase() === normalizedQuery ||
              p.nome.toLowerCase() === normalizedQuery
          ) || results[0];

        await loadPatientPrescription(bestMatch.paciente_id);
      }
    } catch (err) {
      setError(err.message || 'Erro ao buscar prescrição do paciente.');
    } finally {
      setLoading(false);
    }
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    setSearchEmpty(false);
    setHasSearched(false);
    setError(null);
    setBundle(null);
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return '';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  const patient = bundle?.patient;
  const laudo = bundle?.laudo;
  const plano = bundle?.plano;
  const recentSessions = bundle?.sessoes_recentes || [];
  const prescribedExercises = plano?.exercicios || [];

  // Associa cada slot prescrito à sessão mais recente correspondente do paciente
  const getSlotSession = (exerciseItem) => {
    return recentSessions.find(
      (sess) =>
        sess.exercicio_id === exerciseItem.exercicio_id ||
        sess.case_id === exerciseItem.exercicio_id
    );
  };

  const completedSlotsCount = prescribedExercises.filter((ex) => {
    const sess = getSlotSession(ex);
    return sess && (sess.status === 'concluido' || sess.status === 'processando');
  }).length;

  return (
    <div className="patient-prescription-view">
      {/* Cabeçalho Principal conforme Mock 02-Paciente-Envio */}
      <div
        className="f"
        style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}
      >
        <div>
          <h1>Minha prescrição</h1>
          <p className="mu">
            Consulte seu laudo, limites clínicos e a lista de exercícios prescritos · Passo 2 da
            jornada
          </p>
        </div>

        {patient && (
          <Button
            type="button"
            variant="secondary"
            onClick={() => loadPatientPrescription(patient.paciente_id)}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            <span>Atualizar dados</span>
          </Button>
        )}
      </div>

      {/* Card 1: Busca de Prescrição pelo Nome ou Identificador (Mock 2) */}
      <Card style={{ marginTop: '20px' }}>
        <form onSubmit={handleSearchSubmit}>
          <label htmlFor="q">Buscar prescrição pelo nome ou código do paciente</label>
          <div className="f" style={{ flexWrap: 'wrap' }}>
            <input
              id="q"
              type="text"
              className="in"
              style={{ flex: 1, minWidth: '220px' }}
              placeholder="Digite seu nome (ex.: Marina T.) ou código (ex.: PAC-001)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <Button type="submit" disabled={loading}>
              <Search size={16} />
              <span>{loading ? 'Buscando...' : 'Buscar'}</span>
            </Button>
          </div>
        </form>
      </Card>

      {/* Estado de Erro de API ou Validação (DESIGN.md seção 4) */}
      {error && (
        <Card
          style={{
            marginTop: '20px',
            borderColor: 'var(--fc-crit-fg)',
            background: 'var(--fc-crit-bg)',
            color: 'var(--fc-crit-fg)',
          }}
        >
          <div className="f" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div className="f">
              <CircleAlert size={20} />
              <strong>■ {error}</strong>
            </div>
            {searchQuery.trim().length >= 2 && (
              <Button variant="secondary" onClick={handleSearchSubmit}>
                Tentar novamente
              </Button>
            )}
          </div>
        </Card>
      )}

      {/* Estado Inicial antes da busca (Privacidade / LGPD: nenhum paciente listado) */}
      {!hasSearched && !loading && !patient && (
        <Card style={{ marginTop: '20px', textAlign: 'center', padding: '44px 20px' }}>
          <UserCheck size={36} className="mu" style={{ margin: '0 auto 12px' }} />
          <h2>Identifique-se para acessar sua prescrição</h2>
          <p className="mu" style={{ maxWidth: '480px', margin: '0 auto' }}>
            Para proteger a privacidade dos dados clínicos, informe seu nome ou código de paciente
            no campo de busca acima e clique em <strong>Buscar</strong>.
          </p>
        </Card>
      )}

      {/* Estado de Lista Vazia na Busca (DESIGN.md seção 4) */}
      {searchEmpty && !loading && (
        <Card style={{ marginTop: '20px', textAlign: 'center', padding: '40px 20px' }}>
          <Search size={36} className="mu" style={{ margin: '0 auto 12px' }} />
          <h2>Nenhuma prescrição encontrada</h2>
          <p className="mu" style={{ maxWidth: '460px', margin: '0 auto 16px' }}>
            Não localizamos cadastro correspondente a <strong>&ldquo;{searchQuery}&rdquo;</strong>.
            Verifique o nome ou código informado com seu fisioterapeuta.
          </p>
          <Button variant="secondary" onClick={handleClearSearch}>
            Limpar busca
          </Button>
        </Card>
      )}

      {/* Estado de Carregamento (Skeleton / Spinner) */}
      {loading && (
        <Card style={{ marginTop: '20px', textAlign: 'center', padding: '48px 20px' }}>
          <div className="spin-indicator" />
          <p className="mu">Carregando dados de laudo médico e prescrição do paciente...</p>
        </Card>
      )}

      {/* Grid Principal: Laudo e Limites (Esquerda) + Exercícios Prescritos (Direita) */}
      {!loading && !searchEmpty && patient && (
        <div
          className="g prescription-main-grid"
          style={{ gridTemplateColumns: '1fr 1.3fr', marginTop: '20px' }}
        >
          {/* Coluna Esquerda: Laudo e Limites (Mock 2) */}
          <Card className="prescription-laudo-card">
            <div
              className="f"
              style={{
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: '12px',
              }}
            >
              <div>
                <h2 style={{ margin: 0 }}>Laudo e limites</h2>
                <p className="mu" style={{ marginTop: '2px' }}>
                  Paciente: <strong>{patient.nome}</strong> ({patient.paciente_id}
                  {patient.idade ? ` · ${patient.idade} anos` : ''})
                </p>
              </div>
              {laudo?.laudo_id && <span className="ch ne">Laudo {laudo.laudo_id}</span>}
            </div>

            {laudo ? (
              <>
                <p style={{ fontSize: '15px', fontWeight: 500 }}>{laudo.texto_original}</p>

                {/* Chips Estruturados do Laudo */}
                <div className="f" style={{ flexWrap: 'wrap', marginTop: '12px', gap: '8px' }}>
                  {laudo.regiao && <span className="ch ne">Região: {laudo.regiao}</span>}
                  {laudo.lesao && <span className="ch ne">Lesão: {laudo.lesao}</span>}
                  {(laudo.movimentos_restritos || []).length > 0 ? (
                    laudo.movimentos_restritos.map((rest, idx) => (
                      <span key={idx} className="ch wa">
                        ▲ Restrito: {rest}
                      </span>
                    ))
                  ) : (
                    <span className="ch ok">● Sem restrição angular explícita</span>
                  )}
                </div>
              </>
            ) : (
              <p className="mu" style={{ padding: '8px 0' }}>
                Nenhum laudo médico registrado para este paciente até o momento.
              </p>
            )}

            {/* Parâmetros de Limites Clínicos do Plano (Mock 2: Dor máxima e Amplitude) */}
            <div className="prescription-limits-box">
              <div className="f" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
                <div>
                  <span className="mu" style={{ display: 'block', fontSize: '12px' }}>
                    Dor máxima aceitável
                  </span>
                  <strong style={{ fontSize: '18px', color: 'var(--fc-primary-dark)' }}>
                    {plano ? `${plano.dor_maxima_aceitavel}/10` : '--'}
                  </strong>
                </div>
                <div>
                  <span className="mu" style={{ display: 'block', fontSize: '12px' }}>
                    Amplitude esperada
                  </span>
                  <strong style={{ fontSize: '18px', color: 'var(--fc-primary-dark)' }}>
                    {plano?.amplitude_esperada_texto ? `${plano.amplitude_esperada_texto}°` : '--'}
                  </strong>
                </div>
                {laudo?.limite_amplitude_max != null && (
                  <div>
                    <span className="mu" style={{ display: 'block', fontSize: '12px' }}>
                      Limite de segurança (Laudo)
                    </span>
                    <strong style={{ fontSize: '18px', color: 'var(--fc-warn-fg)' }}>
                      máx. {laudo.limite_amplitude_max}°
                    </strong>
                  </div>
                )}
              </div>

              <p className="mu" style={{ marginTop: '10px' }}>
                {plano ? (
                  <>
                    Dor máxima aceitável: <strong>{plano.dor_maxima_aceitavel}/10</strong>
                    {laudo?.movimentos_restritos?.length > 0
                      ? ` · Evite: ${laudo.movimentos_restritos.join(', ')}.`
                      : ` · Faixa angular alvo: ${plano.amplitude_esperada_texto}°.`}
                  </>
                ) : (
                  'Limites de dor e amplitude ainda não configurados pelo fisioterapeuta.'
                )}
              </p>
            </div>

            {patient.observacoes && (
              <p className="mu" style={{ marginTop: '12px' }}>
                <strong>Observações:</strong> {patient.observacoes}
              </p>
            )}

            <div
              className="f"
              style={{
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid var(--fc-border)',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
              }}
            >
              <span
                className="mu"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <ShieldCheck size={15} style={{ color: 'var(--fc-ok-fg)' }} />
                Prescrição válida · dados fictícios (LGPD)
              </span>
              {laudo?.revisado_profissional && (
                <span className="ch ok">● Revisado pelo fisioterapeuta</span>
              )}
            </div>
          </Card>

          {/* Coluna Direita: Exercícios Prescritos / Sessões da Prescrição (Mock 2) */}
          <Card>
            <div
              className="f"
              style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}
            >
              <h2 style={{ margin: 0 }}>Exercícios prescritos (Sessões)</h2>
              {prescribedExercises.length > 0 && (
                <span className="ch ne">
                  <ClipboardCheck size={13} />
                  <span>
                    {completedSlotsCount}/{prescribedExercises.length} enviada(s)
                  </span>
                </span>
              )}
            </div>

            <p className="mu" style={{ marginBottom: '12px' }}>
              Um envio por sessão de fisioterapia. Grave de frente, com boa luz, corpo e rosto
              visíveis, e fale como está a dor.
            </p>

            {prescribedExercises.length === 0 ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '28px 16px',
                  background: 'var(--fc-bg)',
                  borderRadius: 'var(--fc-radius-control)',
                }}
              >
                <Dumbbell size={28} className="mu" style={{ margin: '0 auto 8px' }} />
                <p className="mu">
                  Nenhum exercício foi prescrito no plano deste paciente até o momento.
                </p>
              </div>
            ) : (
              <div>
                {prescribedExercises.map((item, idx) => {
                  const slotSession = getSlotSession(item);
                  const isDone = slotSession?.status === 'concluido';
                  const isProc =
                    slotSession?.status === 'processando' || slotSession?.status === 'enviado';

                  return (
                    <div
                      key={`${item.slot_id || idx}-${item.exercicio_id}`}
                      className="prescription-slot-row"
                    >
                      <div style={{ flex: 1 }}>
                        <b>
                          Sessão {idx + 1} · {item.exercicio_nome}
                        </b>
                        <p className="mu" style={{ marginTop: '2px' }}>
                          <strong>{item.exercicio_id}</strong> · {item.series} séries ×{' '}
                          {item.repeticoes} repetições · Lado: {item.lado || 'auto'} · Equipamento:{' '}
                          {item.equipamento || 'Nenhum'}
                        </p>
                        {item.instrucoes && (
                          <p className="mu" style={{ marginTop: '2px', fontStyle: 'italic' }}>
                            Orientação: &ldquo;{item.instrucoes}&rdquo;
                          </p>
                        )}
                        {slotSession ? (
                          <p className="mu" style={{ marginTop: '4px', fontSize: '12px' }}>
                            Último envio: <strong>{slotSession.session_id}</strong>
                            {slotSession.created_at
                              ? ` (${formatDateTime(slotSession.created_at)})`
                              : ''}
                            {isDone && slotSession.compliance_score != null
                              ? ` · Conformidade: ${slotSession.compliance_score.toFixed(0)}%`
                              : ''}
                          </p>
                        ) : (
                          <p className="mu" style={{ marginTop: '4px', fontSize: '12px' }}>
                            Nenhum arquivo enviado para esta sessão
                          </p>
                        )}
                      </div>

                      <div className="f" style={{ gap: '8px', flexWrap: 'wrap' }}>
                        {isDone ? (
                          <>
                            <StatusChip level="ok" label="Enviada" />
                            {onSelectSession && (
                              <Button
                                type="button"
                                variant="secondary"
                                style={{ height: '36px', padding: '0 12px', fontSize: '13px' }}
                                onClick={() => onSelectSession(slotSession.session_id)}
                              >
                                <FileText size={14} /> Relatório
                              </Button>
                            )}
                          </>
                        ) : isProc ? (
                          <>
                            <StatusChip level="info" label="Em análise" />
                            {onSelectProcessing && (
                              <Button
                                type="button"
                                variant="secondary"
                                style={{ height: '36px', padding: '0 12px', fontSize: '13px' }}
                                onClick={() => onSelectProcessing(slotSession.session_id)}
                              >
                                <PlayCircle size={14} /> Acompanhar
                              </Button>
                            )}
                          </>
                        ) : (
                          <span className="ch ne">Pendente de envio</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      )}

      <p className="mu legal-disclaimer" style={{ marginTop: '12px' }}>
        Todos os dados de pacientes, laudos e prescrições são fictícios (LGPD). Apoio à decisão,
        não diagnóstico.
      </p>
    </div>
  );
}
