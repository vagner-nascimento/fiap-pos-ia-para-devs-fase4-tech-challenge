import { useState, useEffect, useCallback } from 'react';
import { Card } from './ds/Card';
import { Button } from './ds/Button';
import { Field } from './ds/Field';
import {
  listPatients,
  createPatient,
  getPatientBundle,
  listClinicalExerciseCatalog,
  extractReportPreview,
  savePatientMedicalReport,
  savePatientPlan,
} from '../api/patients';
import {
  Plus,
  Save,
  Sparkles,
  Trash2,
  UserPlus,
  CheckCircle2,
  CircleAlert,
  Edit3,
  X,
} from 'lucide-react';

/**
 * PlanAndReportView — Tela 1 ("Plano e laudo") e Tela 8 ("Cadastro de paciente")
 * Alinhada ao Design System Oficial (docs/design/DESIGN.md e Mock 01-Plano-Laudo.dc.html).
 */
export function PlanAndReportView() {
  // Lista de pacientes e catálogo de exercícios
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('PAC-001');
  const [exerciseCatalog, setExerciseCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveMessage, setSaveMessage] = useState('');

  // Estado do Laudo Médico
  const [textoLaudo, setTextoLaudo] = useState('');
  const [regiao, setRegiao] = useState('');
  const [lesao, setLesao] = useState('');
  const [restricoesTexto, setRestricoesTexto] = useState('');
  const [isEditingExtracted, setIsEditingExtracted] = useState(false);
  const [revisadoProfissional, setRevisadoProfissional] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);

  // Estado dos Limites do Plano
  const [dorMaxima, setDorMaxima] = useState(4);
  const [amplitudeEsperada, setAmplitudeEsperada] = useState('60 – 90');

  // Estado dos Exercícios Prescritos
  const [prescribedExercises, setPrescribedExercises] = useState([]);
  const [isAddingExercise, setIsAddingExercise] = useState(false);
  const [newExCaseId, setNewExCaseId] = useState('FISIO-006');
  const [newExSeries, setNewExSeries] = useState(3);
  const [newExReps, setNewExReps] = useState(10);
  const [newExLado, setNewExLado] = useState('direito');
  const [newExInstrucoes, setNewExInstrucoes] = useState('');

  // Salvamento geral
  const [isSaving, setIsSaving] = useState(false);

  // Modal de Novo Paciente (Tela 8)
  const [isPatientModalOpen, setIsPatientModalOpen] = useState(false);
  const [newPatientId, setNewPatientId] = useState('');
  const [newPatientName, setNewPatientName] = useState('');
  const [newPatientAge, setNewPatientAge] = useState('');
  const [newPatientNotes, setNewPatientNotes] = useState('');
  const [isCreatingPatient, setIsCreatingPatient] = useState(false);

  const loadPatientBundle = useCallback(async (pacienteId) => {
    if (!pacienteId) return;
    setError(null);
    setSaveMessage('');
    try {
      const bundle = await getPatientBundle(pacienteId);
      const laudo = bundle.laudo;
      const plano = bundle.plano;

      if (laudo) {
        setTextoLaudo(laudo.texto_original || '');
        setRegiao(laudo.regiao || '');
        setLesao(laudo.lesao || '');
        setRestricoesTexto((laudo.movimentos_restritos || []).join(', '));
        setRevisadoProfissional(Boolean(laudo.revisado_profissional));
      } else {
        setTextoLaudo('');
        setRegiao('');
        setLesao('');
        setRestricoesTexto('');
        setRevisadoProfissional(false);
      }

      if (plano) {
        setDorMaxima(plano.dor_maxima_aceitavel ?? 4);
        setAmplitudeEsperada(plano.amplitude_esperada_texto || '60 – 90');
        setPrescribedExercises(plano.exercicios || []);
      } else {
        setDorMaxima(4);
        setAmplitudeEsperada('60 – 90');
        setPrescribedExercises([]);
      }
    } catch (err) {
      setError(err.message || 'Erro ao carregar dados do paciente.');
    }
  }, []);

  const initScreen = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [patientsList, catalogList] = await Promise.all([
        listPatients(),
        listClinicalExerciseCatalog(),
      ]);
      setPatients(patientsList);
      setExerciseCatalog(catalogList);

      if (catalogList.length > 0) {
        setNewExCaseId(catalogList[0].case_id);
        setNewExLado(catalogList[0].lado_padrao || 'auto');
      }

      const initialId =
        patientsList.find((p) => p.paciente_id === selectedPatientId)?.paciente_id ||
        patientsList[0]?.paciente_id ||
        'PAC-001';
      setSelectedPatientId(initialId);
      await loadPatientBundle(initialId);
    } catch (err) {
      setError(err.message || 'Não foi possível carregar os dados iniciais.');
    } finally {
      setLoading(false);
    }
  }, [loadPatientBundle, selectedPatientId]);

  useEffect(() => {
    initScreen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelectPatientChange = async (e) => {
    const nextId = e.target.value;
    setSelectedPatientId(nextId);
    await loadPatientBundle(nextId);
  };

  // Extrai automaticamente entidades a partir do texto do laudo
  const handleExtractFromText = async (customText = null) => {
    const textToAnalyze = customText !== null ? customText : textoLaudo;
    if (!textToAnalyze || !textToAnalyze.trim()) {
      setRegiao('');
      setLesao('');
      setRestricoesTexto('');
      return;
    }
    setIsExtracting(true);
    try {
      const extracted = await extractReportPreview(textToAnalyze);
      setRegiao(extracted.regiao || '');
      setLesao(extracted.lesao || '');
      setRestricoesTexto((extracted.movimentos_restritos || []).join(', '));
      setRevisadoProfissional(false);
    } catch {
      // Silencia erro de preview em digitação
    } finally {
      setIsExtracting(false);
    }
  };

  const handleAddExerciseToPlan = () => {
    const catItem = exerciseCatalog.find((c) => c.case_id === newExCaseId);
    if (!catItem) return;

    const nextSlotNumber = prescribedExercises.length + 1;
    const newItem = {
      slot_id: `SLOT-${nextSlotNumber}`,
      exercicio_id: catItem.case_id,
      exercicio_nome: catItem.nome,
      equipamento: catItem.requisitos?.[0] || 'Nenhum',
      lado: newExLado || catItem.lado_padrao || 'auto',
      series: Number(newExSeries) || 3,
      repeticoes: Number(newExReps) || 10,
      instrucoes: newExInstrucoes.trim() || null,
    };

    setPrescribedExercises((prev) => [...prev, newItem]);
    setIsAddingExercise(false);
    setNewExInstrucoes('');
    setSaveMessage('');
  };

  const handleRemoveExercise = (indexToRemove) => {
    setPrescribedExercises((prev) =>
      prev
        .filter((_, idx) => idx !== indexToRemove)
        .map((item, idx) => ({ ...item, slot_id: `SLOT-${idx + 1}` }))
    );
    setSaveMessage('');
  };

  const handleUpdateExerciseField = (index, field, value) => {
    setPrescribedExercises((prev) =>
      prev.map((item, idx) => (idx === index ? { ...item, [field]: value } : item))
    );
    setSaveMessage('');
  };

  const handleSavePlanAndReport = async () => {
    if (!selectedPatientId) return;
    setIsSaving(true);
    setError(null);
    setSaveMessage('');

    try {
      const restricoesArray = restricoesTexto
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      if (textoLaudo.trim()) {
        const savedLaudo = await savePatientMedicalReport(selectedPatientId, {
          texto_original: textoLaudo.trim(),
          regiao: regiao.trim() || null,
          lesao: lesao.trim() || null,
          movimentos_restritos: restricoesArray.length > 0 ? restricoesArray : null,
          revisado_profissional: revisadoProfissional || isEditingExtracted,
        });
        setRegiao(savedLaudo.regiao || '');
        setLesao(savedLaudo.lesao || '');
        setRestricoesTexto((savedLaudo.movimentos_restritos || []).join(', '));
      }

      const savedPlano = await savePatientPlan(selectedPatientId, {
        dor_maxima_aceitavel: Number(dorMaxima) || 0,
        amplitude_esperada_texto: amplitudeEsperada.trim() || '60 – 90',
        exercicios: prescribedExercises.map((ex, idx) => ({
          slot_id: `SLOT-${idx + 1}`,
          exercicio_id: ex.exercicio_id,
          series: Number(ex.series) || 3,
          repeticoes: Number(ex.repeticoes) || 10,
          lado: ex.lado || 'auto',
          equipamento: ex.equipamento || null,
          instrucoes: ex.instrucoes || null,
        })),
      });

      setPrescribedExercises(savedPlano.exercicios || []);
      const activePatient = patients.find((p) => p.paciente_id === selectedPatientId);
      setSaveMessage(
        `Plano e laudo salvos com sucesso para ${activePatient?.nome || selectedPatientId}.`
      );
    } catch (err) {
      setError(err.message || 'Falha ao salvar plano e laudo.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateNewPatient = async (e) => {
    e.preventDefault();
    if (!newPatientName.trim()) return;
    setIsCreatingPatient(true);
    setError(null);
    try {
      const created = await createPatient({
        paciente_id: newPatientId.trim() || null,
        nome: newPatientName.trim(),
        idade: newPatientAge ? Number(newPatientAge) : null,
        observacoes: newPatientNotes.trim() || null,
      });

      const updatedList = await listPatients();
      setPatients(updatedList);
      setSelectedPatientId(created.paciente_id);
      setIsPatientModalOpen(false);
      setNewPatientId('');
      setNewPatientName('');
      setNewPatientAge('');
      setNewPatientNotes('');
      await loadPatientBundle(created.paciente_id);
    } catch (err) {
      setError(err.message || 'Erro ao cadastrar novo paciente.');
    } finally {
      setIsCreatingPatient(false);
    }
  };

  const activePatient = patients.find((p) => p.paciente_id === selectedPatientId);
  const restricoesList = restricoesTexto
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div className="plan-report-view">
      {/* Cabeçalho Principal conforme Mock 1 */}
      <div
        className="f"
        style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}
      >
        <div>
          <h1>Plano e laudo</h1>
          <p className="mu">
            Paciente fictício: <strong>{activePatient?.nome || selectedPatientId}</strong> (
            {selectedPatientId}) · Passo 1 da jornada
          </p>
        </div>

        <div className="f" style={{ flexWrap: 'wrap' }}>
          <div className="f" style={{ gap: '8px' }}>
            <label htmlFor="patient-select" style={{ margin: 0, whiteSpace: 'nowrap' }}>
              Paciente:
            </label>
            <select
              id="patient-select"
              className="in"
              style={{ width: '230px' }}
              value={selectedPatientId}
              onChange={handleSelectPatientChange}
              disabled={loading || isSaving}
            >
              {patients.map((p) => (
                <option key={p.paciente_id} value={p.paciente_id}>
                  {p.nome} ({p.paciente_id})
                </option>
              ))}
            </select>
          </div>

          <Button
            type="button"
            variant="secondary"
            onClick={() => setIsPatientModalOpen(true)}
            disabled={isSaving}
          >
            <UserPlus size={16} /> Novo paciente
          </Button>

          <Button
            type="button"
            onClick={handleSavePlanAndReport}
            disabled={loading || isSaving}
          >
            <Save size={16} />
            <span>{isSaving ? 'Salvando...' : 'Salvar plano'}</span>
          </Button>
        </div>
      </div>

      {/* Mensagens de Feedback / Erro */}
      {saveMessage && (
        <div
          className="c f"
          style={{
            background: 'var(--fc-ok-bg)',
            color: 'var(--fc-ok-fg)',
            borderColor: 'var(--fc-ok-fg)',
            padding: '12px 16px',
            marginTop: '16px',
          }}
          role="status"
        >
          <CheckCircle2 size={18} />
          <strong>● {saveMessage}</strong>
        </div>
      )}

      {error && (
        <div
          className="c f"
          style={{
            background: 'var(--fc-crit-bg)',
            color: 'var(--fc-crit-fg)',
            borderColor: 'var(--fc-crit-fg)',
            padding: '12px 16px',
            marginTop: '16px',
          }}
          role="alert"
        >
          <CircleAlert size={18} />
          <span>■ {error}</span>
        </div>
      )}

      {/* Grid Superior: Laudo (Esquerda) + Limites do Plano (Direita) */}
      <div
        className="g plan-top-grid"
        style={{ gridTemplateColumns: '1fr 1fr', marginTop: '20px' }}
      >
        {/* Card 1: Laudo Médico */}
        <Card>
          <div className="f" style={{ justifyContent: 'space-between', marginBottom: '12px' }}>
            <h2 style={{ margin: 0 }}>Laudo</h2>
            <Button
              type="button"
              variant="secondary"
              style={{ height: '34px', padding: '0 12px', fontSize: '12px' }}
              onClick={() => handleExtractFromText(textoLaudo)}
              disabled={isExtracting || !textoLaudo.trim()}
            >
              <Sparkles size={14} />
              <span>{isExtracting ? 'Extraindo...' : 'Extrair entidades'}</span>
            </Button>
          </div>

          <Field
            id="l1"
            label="Texto do laudo"
            multiline
            value={textoLaudo}
            placeholder="Ex: Tendinopatia de ombro direito. Evitar elevação acima de 90° sem controle."
            onChange={(e) => {
              setTextoLaudo(e.target.value);
              setSaveMessage('');
            }}
            onBlur={(e) => {
              if (!revisadoProfissional) {
                handleExtractFromText(e.target.value);
              }
            }}
          />

          <div
            className="f"
            style={{ justifyContent: 'space-between', marginTop: '12px' }}
          >
            <p className="mu">Extraído automaticamente (confira):</p>
            <button
              type="button"
              className="btn-link-inline"
              onClick={() => setIsEditingExtracted((prev) => !prev)}
            >
              <Edit3 size={13} />
              <span>{isEditingExtracted ? 'Ocultar edição' : 'Ajustar campos'}</span>
            </button>
          </div>

          {/* Chips Extraídos conforme Mock 1 */}
          <div className="f" style={{ flexWrap: 'wrap', marginTop: '8px', gap: '8px' }}>
            <span className="ch ne">Região: {regiao || 'não especificada'}</span>
            <span className="ch ne">Lesão: {lesao || 'não especificada'}</span>
            {restricoesList.length > 0 ? (
              restricoesList.map((r, idx) => (
                <span key={idx} className="ch wa">
                  ▲ Restrito: {r}
                </span>
              ))
            ) : (
              <span className="ch ok">● Sem restrição angular explícita</span>
            )}
          </div>

          {/* Campos editáveis para revisão quando a extração for incerta (DESIGN.md seção 4) */}
          {isEditingExtracted && (
            <div
              className="g"
              style={{
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                marginTop: '14px',
                paddingTop: '14px',
                borderTop: '1px solid var(--fc-border)',
              }}
            >
              <Field
                id="laudo-regiao"
                label="Região anatômica (confira)"
                value={regiao}
                placeholder="Ex: ombro direito"
                onChange={(e) => {
                  setRegiao(e.target.value);
                  setRevisadoProfissional(true);
                }}
              />
              <Field
                id="laudo-lesao"
                label="Lesão / condição (confira)"
                value={lesao}
                placeholder="Ex: tendinopatia"
                onChange={(e) => {
                  setLesao(e.target.value);
                  setRevisadoProfissional(true);
                }}
              />
              <div style={{ gridColumn: '1 / -1' }}>
                <Field
                  id="laudo-restricoes"
                  label="Movimentos restritos (separados por vírgula)"
                  value={restricoesTexto}
                  placeholder="Ex: elevação > 90°, carga externa"
                  onChange={(e) => {
                    setRestricoesTexto(e.target.value);
                    setRevisadoProfissional(true);
                  }}
                />
              </div>
            </div>
          )}
        </Card>

        {/* Card 2: Limites do Plano */}
        <Card>
          <h2>Limites do plano</h2>
          <Field
            id="p1"
            label="Dor máxima aceitável (0–10)"
            type="number"
            min="0"
            max="10"
            value={dorMaxima}
            onChange={(e) => {
              setDorMaxima(e.target.value);
              setSaveMessage('');
            }}
          />

          <Field
            id="p2"
            label="Amplitude esperada (graus)"
            style={{ marginTop: '12px' }}
            value={amplitudeEsperada}
            placeholder="Ex: 60 – 90"
            onChange={(e) => {
              setAmplitudeEsperada(e.target.value);
              setSaveMessage('');
            }}
            hint="Faixa angular alvo utilizada para comparar a execução do paciente com o plano."
          />

          <div
            style={{
              marginTop: '16px',
              padding: '12px',
              borderRadius: 'var(--fc-radius-control)',
              background: 'var(--fc-bg)',
            }}
          >
            <p className="mu">
              <strong>Resumo de segurança clínica:</strong> Alertas serão gerados caso o relato de
              dor ultrapasse <strong>{dorMaxima}/10</strong> ou a amplitude viole as restrições do
              laudo.
            </p>
          </div>
        </Card>
      </div>

      {/* Card 3: Exercícios Prescritos conforme Mock 1 */}
      <Card style={{ marginTop: '20px' }}>
        <div className="f" style={{ justifyContent: 'space-between', marginBottom: '8px' }}>
          <h2 style={{ margin: 0 }}>Exercícios prescritos</h2>
          <span className="mu">{prescribedExercises.length} exercício(s) no plano</span>
        </div>

        {prescribedExercises.length === 0 ? (
          <p className="mu" style={{ padding: '16px 0' }}>
            Nenhum exercício prescrito para este paciente. Clique em &ldquo;+ Adicionar
            exercício&rdquo; abaixo.
          </p>
        ) : (
          <div>
            {prescribedExercises.map((item, idx) => (
              <div key={`${item.slot_id || idx}-${item.exercicio_id}`} className="plan-exercise-row">
                <div>
                  <b>
                    {item.exercicio_id} · {item.exercicio_nome}
                  </b>
                  <p className="mu">
                    Equipamento: {item.equipamento || 'Nenhum'} · Lado: {item.lado || 'auto'}
                    {item.instrucoes ? ` · ${item.instrucoes}` : ''}
                  </p>
                </div>

                <div className="f" style={{ gap: '10px', flexWrap: 'wrap' }}>
                  <div className="f" style={{ gap: '6px' }}>
                    <input
                      type="number"
                      min="1"
                      max="20"
                      aria-label={`Séries de ${item.exercicio_id}`}
                      className="in"
                      style={{ width: '64px', height: '36px', textAlign: 'center', padding: '0 6px' }}
                      value={item.series}
                      onChange={(e) =>
                        handleUpdateExerciseField(idx, 'series', Number(e.target.value) || 1)
                      }
                    />
                    <span className="mu">séries ×</span>
                    <input
                      type="number"
                      min="1"
                      max="50"
                      aria-label={`Repetições de ${item.exercicio_id}`}
                      className="in"
                      style={{ width: '68px', height: '36px', textAlign: 'center', padding: '0 6px' }}
                      value={item.repeticoes}
                      onChange={(e) =>
                        handleUpdateExerciseField(idx, 'repeticoes', Number(e.target.value) || 1)
                      }
                    />
                    <span className="mu">reps</span>
                  </div>

                  <button
                    type="button"
                    className="btn-icon-danger"
                    onClick={() => handleRemoveExercise(idx)}
                    aria-label={`Remover exercício ${item.exercicio_id}`}
                    title="Remover exercício"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Formulário Inline para Adicionar Exercício */}
        {isAddingExercise ? (
          <div className="add-exercise-box">
            <h3 style={{ fontSize: '15px', margin: '0 0 12px', fontWeight: 700 }}>
              Adicionar exercício à prescrição
            </h3>
            <div
              className="g"
              style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: '12px' }}
            >
              <Field id="add-ex-select" label="Exercício de referência">
                <select
                  id="add-ex-select"
                  className="in"
                  value={newExCaseId}
                  onChange={(e) => {
                    const nextCode = e.target.value;
                    setNewExCaseId(nextCode);
                    const found = exerciseCatalog.find((c) => c.case_id === nextCode);
                    if (found?.lado_padrao) {
                      setNewExLado(found.lado_padrao);
                    }
                  }}
                >
                  {exerciseCatalog.map((ex) => (
                    <option key={ex.case_id} value={ex.case_id}>
                      {ex.case_id} · {ex.nome}
                    </option>
                  ))}
                </select>
              </Field>

              <Field id="add-ex-lado" label="Lado avaliado">
                <select
                  id="add-ex-lado"
                  className="in"
                  value={newExLado}
                  onChange={(e) => setNewExLado(e.target.value)}
                >
                  <option value="direito">Direito</option>
                  <option value="esquerdo">Esquerdo</option>
                  <option value="ambos">Ambos</option>
                  <option value="auto">Automático</option>
                </select>
              </Field>

              <Field
                id="add-ex-series"
                label="Séries"
                type="number"
                min="1"
                max="20"
                value={newExSeries}
                onChange={(e) => setNewExSeries(e.target.value)}
              />

              <Field
                id="add-ex-reps"
                label="Repetições"
                type="number"
                min="1"
                max="50"
                value={newExReps}
                onChange={(e) => setNewExReps(e.target.value)}
              />
            </div>

            <Field
              id="add-ex-notes"
              label="Instruções específicas (opcional)"
              style={{ marginTop: '12px' }}
              placeholder="Ex: Manter tronco apoiado e executar movimento sem pressa"
              value={newExInstrucoes}
              onChange={(e) => setNewExInstrucoes(e.target.value)}
            />

            <div className="f" style={{ justifyContent: 'flex-end', marginTop: '14px' }}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setIsAddingExercise(false)}
              >
                Cancelar
              </Button>
              <Button type="button" onClick={handleAddExerciseToPlan}>
                Confirmar exercício
              </Button>
            </div>
          </div>
        ) : (
          <Button
            type="button"
            variant="secondary"
            style={{ marginTop: '12px' }}
            onClick={() => setIsAddingExercise(true)}
          >
            <Plus size={16} /> + Adicionar exercício
          </Button>
        )}
      </Card>

      <p className="mu legal-disclaimer" style={{ marginTop: '4px' }}>
        Todos os dados de pacientes, laudos e prescrições são fictícios (LGPD). Apoio à decisão,
        não diagnóstico.
      </p>

      {/* Modal: Cadastro de Novo Paciente Sintético (Tela 8) */}
      {isPatientModalOpen && (
        <div
          className="lightbox-backdrop"
          onClick={() => !isCreatingPatient && setIsPatientModalOpen(false)}
        >
          <div
            className="lightbox-modal modal-new-session"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="lightbox-header">
              <div>
                <h2>Novo Paciente (Dados Fictícios)</h2>
                <p className="mu">Cadastre um identificador sintético para vincular plano e laudo</p>
              </div>
              <button
                type="button"
                className="btn-close"
                onClick={() => setIsPatientModalOpen(false)}
                disabled={isCreatingPatient}
                aria-label="Fechar"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateNewPatient} className="modal-form">
              <div className="g" style={{ gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <Field
                  id="new-patient-id"
                  label="Código Sintético (opcional)"
                  placeholder="Ex: PAC-005 (auto se vazio)"
                  value={newPatientId}
                  onChange={(e) => setNewPatientId(e.target.value)}
                />
                <Field
                  id="new-patient-age"
                  label="Idade fictícia (anos)"
                  type="number"
                  min="1"
                  max="120"
                  placeholder="Ex: 42"
                  value={newPatientAge}
                  onChange={(e) => setNewPatientAge(e.target.value)}
                />
              </div>

              <Field
                id="new-patient-name"
                label="Nome fictício do paciente *"
                style={{ marginTop: '12px' }}
                placeholder="Ex: Helena R."
                value={newPatientName}
                onChange={(e) => setNewPatientName(e.target.value)}
                required
              />

              <Field
                id="new-patient-notes"
                label="Observações clínicas gerais"
                style={{ marginTop: '12px' }}
                multiline
                placeholder="Ex: Encaminhamento ortopédico sintético para reabilitação motora."
                value={newPatientNotes}
                onChange={(e) => setNewPatientNotes(e.target.value)}
              />

              <div className="modal-actions" style={{ marginTop: '20px' }}>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setIsPatientModalOpen(false)}
                  disabled={isCreatingPatient}
                >
                  Cancelar
                </Button>
                <Button type="submit" disabled={isCreatingPatient}>
                  {isCreatingPatient ? 'Cadastrando...' : 'Criar Paciente'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

