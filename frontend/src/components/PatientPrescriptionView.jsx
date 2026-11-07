import { useState, useCallback, useEffect } from 'react';
import { Card } from './ds/Card';
import { Button } from './ds/Button';
import { StatusChip } from './ds/StatusChip';
import { listPatients, getPatientBundle } from '../api/patients';
import {
  createSessionUpload,
  createSessionReference,
  listReferenceClips,
} from '../api/sessions';
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
  Upload,
  Film,
  X,
  CheckCircle2,
  RotateCcw,
} from 'lucide-react';

const MAX_UPLOAD_SIZE_BYTES = 200 * 1024 * 1024; // 200 MB (DESIGN.md seção 4)
const ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'];

function formatFileSize(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes))) return '';
  const num = Number(bytes);
  if (num < 1024 * 1024) {
    return `${Math.max(1, Math.round(num / 1024))} KB`;
  }
  return `${(num / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`;
}

function validateVideoFile(file) {
  if (!file) return 'Nenhum arquivo selecionado.';
  const lowerName = (file.name || '').toLowerCase();
  const hasValidExt = ALLOWED_VIDEO_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  const hasVideoMime = file.type && file.type.startsWith('video/');

  if (!hasValidExt && !hasVideoMime) {
    return 'Formato inválido. Selecione um arquivo de vídeo (.mp4, .mov ou .webm).';
  }
  if (file.size <= 0) {
    return 'O arquivo selecionado está vazio.';
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return `O arquivo (${formatFileSize(file.size)}) excede o limite máximo de 200 MB.`;
  }
  return null;
}

/**
 * PatientPrescriptionView — Telas 2 e 3 ("Minha prescrição" e "Enviar sessões" — Visão do Paciente, Issues #4 e #5)
 * Implementa os Passos 2 e 3 da Jornada Principal (docs/jornada-proposta-001.md e PRD v1.2),
 * alinhada ao Design System (docs/design/DESIGN.md) e ao Mock 02-Paciente-Envio.dc.html.
 * Por privacidade (LGPD), não lista outros pacientes: o paciente busca seu próprio cadastro
 * informando seu nome ou código identificador (ex.: PAC-001) e realiza 1 envio de vídeo por sessão prescrita.
 */
export function PatientPrescriptionView({ onSelectSession, onSelectProcessing }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchEmpty, setSearchEmpty] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // Estado de seleção e upload por slot (Issue #5)
  // slotSelections[slotKey] = { mode: 'file' | 'reference', file?: File, datasetClip?: string, validationError?: string }
  const [slotSelections, setSlotSelections] = useState({});
  // slotUploadStates[slotKey] = { status: 'idle' | 'uploading' | 'done' | 'error', progress: number, error?: string, sessionId?: string }
  const [slotUploadStates, setSlotUploadStates] = useState({});
  const [lgpdConsent, setLgpdConsent] = useState(false);
  const [uploadFormError, setUploadFormError] = useState(null);
  const [isBatchUploading, setIsBatchUploading] = useState(false);
  const [batchSuccessSessions, setBatchSuccessSessions] = useState([]);
  const [referenceClips, setReferenceClips] = useState([]);
  const [openDemoPickerSlot, setOpenDemoPickerSlot] = useState(null);

  useEffect(() => {
    let active = true;
    listReferenceClips()
      .then((clips) => {
        if (active && Array.isArray(clips)) {
          setReferenceClips(clips);
        }
      })
      .catch(() => {
        // Clipes de referência são opcionais na tela do paciente
      });
    return () => {
      active = false;
    };
  }, []);

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
    setUploadFormError(null);
    setBatchSuccessSessions([]);

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

        setSlotSelections({});
        setSlotUploadStates({});
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
    setSlotSelections({});
    setSlotUploadStates({});
    setBatchSuccessSessions([]);
    setUploadFormError(null);
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

  const getSlotKey = (exerciseItem, idx) => exerciseItem.slot_id || `SLOT-${idx + 1}`;

  // Associa cada slot prescrito à sessão mais recente correspondente do paciente (priorizando slot_id)
  const getSlotSession = (exerciseItem, slotKey) => {
    const bySlotId = recentSessions.find((sess) => sess.slot_id && sess.slot_id === slotKey);
    if (bySlotId) return bySlotId;

    return recentSessions.find(
      (sess) =>
        !sess.slot_id &&
        (sess.exercicio_id === exerciseItem.exercicio_id ||
          sess.case_id === exerciseItem.exercicio_id)
    );
  };

  const completedSlotsCount = prescribedExercises.filter((ex, idx) => {
    const sess = getSlotSession(ex, getSlotKey(ex, idx));
    return sess && (sess.status === 'concluido' || sess.status === 'processando');
  }).length;

  // Manipulação de arquivo selecionado por slot
  const handleFileChangeForSlot = (slotKey, fileList) => {
    const file = fileList?.[0];
    if (!file) return;

    const validationError = validateVideoFile(file);
    setUploadFormError(null);
    setBatchSuccessSessions([]);
    setOpenDemoPickerSlot(null);

    setSlotSelections((prev) => ({
      ...prev,
      [slotKey]: {
        mode: 'file',
        file,
        validationError,
      },
    }));

    setSlotUploadStates((prev) => ({
      ...prev,
      [slotKey]: { status: 'idle', progress: 0, error: null },
    }));
  };

  const handleSelectDemoClipForSlot = (slotKey, clipFilename) => {
    if (!clipFilename) return;
    setUploadFormError(null);
    setBatchSuccessSessions([]);
    setOpenDemoPickerSlot(null);

    setSlotSelections((prev) => ({
      ...prev,
      [slotKey]: {
        mode: 'reference',
        datasetClip: clipFilename,
        validationError: null,
      },
    }));

    setSlotUploadStates((prev) => ({
      ...prev,
      [slotKey]: { status: 'idle', progress: 0, error: null },
    }));
  };

  const handleClearSlotSelection = (slotKey) => {
    setSlotSelections((prev) => {
      const next = { ...prev };
      delete next[slotKey];
      return next;
    });
    setSlotUploadStates((prev) => {
      const next = { ...prev };
      delete next[slotKey];
      return next;
    });
  };

  // Envia um único slot (via multipart/form-data ou referência)
  const uploadSingleSlot = async (exerciseItem, slotKey) => {
    const selection = slotSelections[slotKey];
    if (!selection || selection.validationError || !patient) {
      return null;
    }

    setSlotUploadStates((prev) => ({
      ...prev,
      [slotKey]: { status: 'uploading', progress: 5, error: null },
    }));

    try {
      let created = null;
      if (selection.mode === 'reference' && selection.datasetClip) {
        setSlotUploadStates((prev) => ({
          ...prev,
          [slotKey]: { status: 'uploading', progress: 45, error: null },
        }));
        created = await createSessionReference({
          exercicio_id: exerciseItem.exercicio_id,
          paciente_id: patient.paciente_id,
          slot_id: slotKey,
          dataset_clip: selection.datasetClip,
          side: exerciseItem.lado || 'auto',
          target_repetitions: Number(exerciseItem.repeticoes) || 5,
          lgpd_aceite: true,
        });
      } else {
        const formData = new FormData();
        formData.append('file', selection.file);
        formData.append('paciente_id', patient.paciente_id);
        formData.append('slot_id', slotKey);
        formData.append('exercicio_id', exerciseItem.exercicio_id);
        formData.append('exercicio', exerciseItem.exercicio_id);
        formData.append('side', exerciseItem.lado || 'auto');
        formData.append('target_repetitions', String(exerciseItem.repeticoes || 5));
        formData.append('lgpd_aceite', 'true');

        created = await createSessionUpload(formData, {
          onProgress: (percent) => {
            setSlotUploadStates((prev) => ({
              ...prev,
              [slotKey]: { status: 'uploading', progress: percent, error: null },
            }));
          },
        });
      }

      setSlotUploadStates((prev) => ({
        ...prev,
        [slotKey]: {
          status: 'done',
          progress: 100,
          error: null,
          sessionId: created?.session_id,
        },
      }));

      // Limpa a seleção pendente do slot concluído
      setSlotSelections((prev) => {
        const next = { ...prev };
        delete next[slotKey];
        return next;
      });

      return created;
    } catch (err) {
      const errMsg = err.message || 'Falha no envio do vídeo desta sessão.';
      setSlotUploadStates((prev) => ({
        ...prev,
        [slotKey]: { status: 'error', progress: 0, error: errMsg },
      }));
      throw err;
    }
  };

  // Dispara o envio de todos os slots selecionados (1 upload por sessão de fisioterapia)
  const handleSendAllSelectedSlots = async () => {
    setUploadFormError(null);
    setBatchSuccessSessions([]);

    const slotsToUpload = prescribedExercises
      .map((item, idx) => ({ item, slotKey: getSlotKey(item, idx), idx }))
      .filter(({ slotKey }) => Boolean(slotSelections[slotKey]));

    if (slotsToUpload.length === 0) {
      setUploadFormError(
        'Escolha um vídeo (.mp4) em pelo menos uma sessão prescrita antes de clicar em "Enviar para análise".'
      );
      return;
    }

    const invalidSlot = slotsToUpload.find(
      ({ slotKey }) => Boolean(slotSelections[slotKey]?.validationError)
    );
    if (invalidSlot) {
      setUploadFormError(
        `Corrija o arquivo inválido na Sessão ${invalidSlot.idx + 1} (${invalidSlot.item.exercicio_nome}) antes de enviar.`
      );
      return;
    }

    if (!lgpdConsent) {
      setUploadFormError(
        'Para enviar seus vídeos, marque o aceite do Termo de Consentimento LGPD (uso de imagem e voz).'
      );
      return;
    }

    setIsBatchUploading(true);
    const createdList = [];
    let hadError = false;

    for (const { item, slotKey, idx } of slotsToUpload) {
      try {
        const created = await uploadSingleSlot(item, slotKey);
        if (created?.session_id) {
          createdList.push({
            session_id: created.session_id,
            slotKey,
            sessionNumber: idx + 1,
            exercicio_nome: item.exercicio_nome,
          });
        }
      } catch {
        hadError = true;
      }
    }

    if (patient?.paciente_id) {
      await loadPatientPrescription(patient.paciente_id);
    }

    setIsBatchUploading(false);

    if (createdList.length === 1 && !hadError && onSelectProcessing) {
      // Conforme DESIGN.md seção 3: ao concluir envio individual, navega para /sessoes/:id/processamento
      onSelectProcessing(createdList[0].session_id);
    } else if (createdList.length > 0) {
      setBatchSuccessSessions(createdList);
    }
  };

  // Reenvio individual quando um slot falhou ("Tentar novamente" — DESIGN.md seção 4)
  const handleRetrySlotUpload = async (exerciseItem, slotKey, idx) => {
    setUploadFormError(null);
    if (!lgpdConsent) {
      setUploadFormError(
        'Marque o aceite do Termo de Consentimento LGPD antes de tentar enviar novamente.'
      );
      return;
    }

    setIsBatchUploading(true);
    try {
      const created = await uploadSingleSlot(exerciseItem, slotKey);
      if (patient?.paciente_id) {
        await loadPatientPrescription(patient.paciente_id);
      }
      if (created?.session_id && onSelectProcessing) {
        onSelectProcessing(created.session_id);
      } else if (created?.session_id) {
        setBatchSuccessSessions([
          {
            session_id: created.session_id,
            slotKey,
            sessionNumber: idx + 1,
            exercicio_nome: exerciseItem.exercicio_nome,
          },
        ]);
      }
    } catch {
      // Erro já registrado em slotUploadStates[slotKey]
    } finally {
      setIsBatchUploading(false);
    }
  };

  const selectedSlotsCount = prescribedExercises.filter((ex, idx) => {
    const key = getSlotKey(ex, idx);
    return Boolean(slotSelections[key] && !slotSelections[key].validationError);
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
            Consulte seu laudo, limites clínicos e envie seus vídeos por sessão de fisioterapia ·
            Passos 2 e 3 da jornada
          </p>
        </div>

        {patient && (
          <Button
            type="button"
            variant="secondary"
            onClick={() => loadPatientPrescription(patient.paciente_id)}
            disabled={loading || isBatchUploading}
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
              disabled={isBatchUploading}
            />
            <Button type="submit" disabled={loading || isBatchUploading}>
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

      {/* Grid Principal: Laudo e Limites (Esquerda) + Enviar Sessões (Direita — Mock 02-Paciente-Envio) */}
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

          {/* Coluna Direita: Enviar Sessões (Mock 02-Paciente-Envio — Issue #5) */}
          <Card>
            <div
              className="f"
              style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}
            >
              <h2 style={{ margin: 0 }}>Enviar sessões</h2>
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

            {/* Banner de Sucesso quando múltiplas sessões foram enviadas em lote */}
            {batchSuccessSessions.length > 0 && (
              <div className="batch-upload-success-banner">
                <div className="f" style={{ gap: '8px', marginBottom: '8px' }}>
                  <CheckCircle2 size={18} />
                  <strong>
                    ● {batchSuccessSessions.length} sessão(ões) enviada(s) para análise!
                  </strong>
                </div>
                <p className="mu" style={{ marginBottom: '10px', color: 'inherit' }}>
                  O processamento biomecânico e de áudio iniciou em segundo plano. Escolha uma
                  sessão abaixo para acompanhar:
                </p>
                <div className="f" style={{ flexWrap: 'wrap', gap: '8px' }}>
                  {batchSuccessSessions.map((item) => (
                    <Button
                      key={item.session_id}
                      type="button"
                      variant="secondary"
                      style={{ height: '36px', padding: '0 12px', fontSize: '13px' }}
                      onClick={() => onSelectProcessing && onSelectProcessing(item.session_id)}
                    >
                      <PlayCircle size={14} />
                      <span>
                        Acompanhar Sessão {item.sessionNumber} ({item.exercicio_nome})
                      </span>
                    </Button>
                  ))}
                </div>
              </div>
            )}

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
                  const slotKey = getSlotKey(item, idx);
                  const slotSession = getSlotSession(item, slotKey);
                  const isDone = slotSession?.status === 'concluido';
                  const isProc =
                    slotSession?.status === 'processando' || slotSession?.status === 'enviado';

                  const selection = slotSelections[slotKey];
                  const uploadState = slotUploadStates[slotKey];
                  const isUploadingThisSlot = uploadState?.status === 'uploading';
                  const fileInputId = `slot-video-input-${slotKey}`;
                  const compatibleClips = referenceClips.filter(
                    (c) => c.case_id === item.exercicio_id
                  );

                  return (
                    <div key={`${slotKey}-${item.exercicio_id}`} className="prescription-slot-row">
                      <div style={{ flex: 1, minWidth: '220px' }}>
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

                        {/* Linha de status do arquivo selecionado ou sessão enviada (Mock 02-Paciente-Envio) */}
                        {selection ? (
                          <div className="slot-selected-file-pill">
                            {selection.mode === 'reference' ? (
                              <span>
                                <Film size={13} style={{ verticalAlign: 'text-bottom' }} /> Clipe
                                demo: <strong>{selection.datasetClip}</strong>
                              </span>
                            ) : (
                              <span>
                                <Upload size={13} style={{ verticalAlign: 'text-bottom' }} />{' '}
                                <strong>{selection.file.name}</strong> ·{' '}
                                {formatFileSize(selection.file.size)}
                              </span>
                            )}
                            <button
                              type="button"
                              className="slot-remove-file-btn"
                              onClick={() => handleClearSlotSelection(slotKey)}
                              disabled={isBatchUploading}
                              aria-label={`Remover vídeo selecionado da Sessão ${idx + 1}`}
                              title="Remover arquivo selecionado"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ) : slotSession ? (
                          <p className="mu" style={{ marginTop: '4px', fontSize: '12px' }}>
                            {slotSession.original_filename ? (
                              <>
                                <strong>{slotSession.original_filename}</strong>
                                {slotSession.file_size_bytes
                                  ? ` · ${formatFileSize(slotSession.file_size_bytes)}`
                                  : ''}{' '}
                                ·{' '}
                              </>
                            ) : null}
                            Sessão <strong>{slotSession.session_id}</strong>
                            {slotSession.created_at
                              ? ` (${formatDateTime(slotSession.created_at)})`
                              : ''}
                            {isDone && slotSession.compliance_score != null
                              ? ` · Conformidade: ${slotSession.compliance_score.toFixed(0)}%`
                              : ''}
                            {slotSession.lgpd_aceite !== false && (
                              <span
                                className="ch ok"
                                style={{
                                  fontSize: '11px',
                                  padding: '2px 8px',
                                  marginLeft: '8px',
                                  verticalAlign: 'middle',
                                }}
                                title="Consentimento LGPD (imagem e voz) registrado nesta sessão"
                              >
                                <ShieldCheck size={12} /> ● Termo LGPD aceito
                              </span>
                            )}
                          </p>
                        ) : (
                          <p className="mu" style={{ marginTop: '4px', fontSize: '12px' }}>
                            Nenhum arquivo
                          </p>
                        )}

                        {/* Erro de validação do arquivo selecionado (ex: > 200 MB ou formato inválido) */}
                        {selection?.validationError && (
                          <p className="slot-validation-error">■ {selection.validationError}</p>
                        )}

                        {/* Barra de progresso durante o upload (DESIGN.md seção 4) */}
                        {isUploadingThisSlot && (
                          <div className="slot-upload-progress-wrap">
                            <div className="slot-upload-progress-bar">
                              <div
                                className="slot-upload-progress-fill"
                                style={{ width: `${uploadState.progress || 10}%` }}
                              />
                            </div>
                            <span className="mu" style={{ fontSize: '12px' }}>
                              Enviando vídeo... {uploadState.progress || 10}%
                            </span>
                          </div>
                        )}

                        {/* Erro de upload neste slot com botão "Tentar novamente" (DESIGN.md seção 4) */}
                        {uploadState?.status === 'error' && (
                          <div className="slot-upload-error-box">
                            <span>■ {uploadState.error}</span>
                            {selection && !selection.validationError && (
                              <button
                                type="button"
                                className="btn-link-inline"
                                onClick={() => handleRetrySlotUpload(item, slotKey, idx)}
                                disabled={isBatchUploading}
                              >
                                <RotateCcw size={13} /> Tentar novamente
                              </button>
                            )}
                          </div>
                        )}

                        {/* Seletor rápido opcional de clipe de demonstração do dataset */}
                        {openDemoPickerSlot === slotKey && compatibleClips.length > 0 && (
                          <div className="slot-demo-picker">
                            <label htmlFor={`demo-select-${slotKey}`} style={{ fontSize: '12px' }}>
                              Selecionar clipe de demonstração ({item.exercicio_id}):
                            </label>
                            <div className="f" style={{ gap: '8px', flexWrap: 'wrap' }}>
                              <select
                                id={`demo-select-${slotKey}`}
                                className="in"
                                style={{ height: '36px', fontSize: '13px', flex: 1 }}
                                defaultValue=""
                                onChange={(e) =>
                                  handleSelectDemoClipForSlot(slotKey, e.target.value)
                                }
                              >
                                <option value="" disabled>
                                  Escolha um clipe do dataset...
                                </option>
                                {compatibleClips.map((clip) => (
                                  <option key={clip.filename} value={clip.filename}>
                                    {clip.filename} — {clip.descricao}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                className="btn-link-inline"
                                onClick={() => setOpenDemoPickerSlot(null)}
                              >
                                Fechar
                              </button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Ações à direita da linha do slot */}
                      <div className="f" style={{ gap: '8px', flexWrap: 'wrap' }}>
                        {/* Input file oculto acessível via label/botão */}
                        <input
                          id={fileInputId}
                          type="file"
                          accept="video/mp4,video/quicktime,video/webm,video/*"
                          style={{ display: 'none' }}
                          onChange={(e) => {
                            handleFileChangeForSlot(slotKey, e.target.files);
                            e.target.value = '';
                          }}
                          disabled={isBatchUploading}
                        />

                        {isDone && !selection ? (
                          <>
                            <StatusChip level="ok" label="Enviada" />
                            {onSelectSession && (
                              <Button
                                type="button"
                                variant="secondary"
                                style={{ height: '38px', padding: '0 12px', fontSize: '13px' }}
                                onClick={() => onSelectSession(slotSession.session_id)}
                              >
                                <FileText size={14} /> Relatório
                              </Button>
                            )}
                            <label
                              htmlFor={fileInputId}
                              className="btn s slot-choose-video-label"
                              style={{ height: '38px', padding: '0 12px', fontSize: '13px' }}
                              title="Enviar uma nova gravação para esta sessão"
                            >
                              <Upload size={14} /> Novo vídeo
                            </label>
                          </>
                        ) : isProc && !selection ? (
                          <>
                            <StatusChip level="info" label="Em análise" />
                            {onSelectProcessing && (
                              <Button
                                type="button"
                                variant="secondary"
                                style={{ height: '38px', padding: '0 12px', fontSize: '13px' }}
                                onClick={() => onSelectProcessing(slotSession.session_id)}
                              >
                                <PlayCircle size={14} /> Acompanhar
                              </Button>
                            )}
                          </>
                        ) : (
                          <>
                            <label
                              htmlFor={fileInputId}
                              className="btn s slot-choose-video-label"
                              aria-label={`Escolher vídeo para Sessão ${idx + 1} (${item.exercicio_nome})`}
                            >
                              <Upload size={15} />
                              <span>{selection ? 'Trocar vídeo' : 'Escolher vídeo'}</span>
                            </label>

                            {compatibleClips.length > 0 && !selection && (
                              <button
                                type="button"
                                className="btn-link-inline"
                                onClick={() =>
                                  setOpenDemoPickerSlot(
                                    openDemoPickerSlot === slotKey ? null : slotKey
                                  )
                                }
                                disabled={isBatchUploading}
                                title="Usar um vídeo de demonstração do dataset sintético"
                              >
                                <Film size={13} /> Clipe demo
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Termo de Consentimento LGPD (Imagem e Voz) */}
                <div className="lgpd-consent-box">
                  <label htmlFor="lgpd-consent-checkbox" className="lgpd-consent-label">
                    <input
                      id="lgpd-consent-checkbox"
                      type="checkbox"
                      checked={lgpdConsent}
                      onChange={(e) => {
                        setLgpdConsent(e.target.checked);
                        if (e.target.checked) setUploadFormError(null);
                      }}
                      disabled={isBatchUploading}
                    />
                    <span>
                      <strong>Termo de Consentimento (LGPD):</strong> Autorizo a gravação e o
                      processamento automatizado da minha imagem (postura e equipamento) e voz
                      (transcrição local de relato de dor) exclusivamente para análise biomecânica
                      de apoio à decisão do fisioterapeuta. Dados fictícios de demonstração.
                    </span>
                  </label>
                </div>

                {/* Alerta de erro geral do formulário de envio */}
                {uploadFormError && (
                  <div className="upload-form-error-banner" role="alert">
                    <CircleAlert size={18} />
                    <span>■ {uploadFormError}</span>
                  </div>
                )}

                {/* Botão Principal de Envio (Mock 02-Paciente-Envio: width 100%, margin-top 12px) */}
                <Button
                  type="button"
                  style={{ marginTop: '12px', width: '100%' }}
                  onClick={handleSendAllSelectedSlots}
                  disabled={isBatchUploading}
                >
                  <Upload size={16} />
                  <span>
                    {isBatchUploading
                      ? 'Enviando sessões para análise...'
                      : selectedSlotsCount > 0
                      ? `Enviar para análise (${selectedSlotsCount} ${
                          selectedSlotsCount === 1 ? 'sessão selecionada' : 'sessões selecionadas'
                        })`
                      : 'Enviar para análise'}
                  </span>
                </Button>
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
