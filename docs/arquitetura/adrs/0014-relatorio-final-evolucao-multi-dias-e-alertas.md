# ADR 0014 — Relatório Final de Evolução Longitudinal Multi-Dias (Séries × Repetições) e Painel de Alertas Clínicos

- **Status:** Aceito
- **Data:** 07/11/2026
- **Contexto:** Issue #7 (Relatório Final de Evolução do Paciente e Painel de Alertas)

---

## 1. Contexto e Problema

Na jornada real de reabilitação fisioterapêutica, um plano de tratamento (`PlanDocument`) abrange **múltiplos dias de tratamento** (`dias_tratamento`, ex.: 3 dias) nos quais o paciente executa diariamente uma sequência de **exercícios prescritos** (`SLOT-1`, `SLOT-2`, ...), onde cada exercício possui **$N$ séries de $M$ repetições por série** (`series` $\times$ `repeticoes`, totalizando $N \times M$ repetições diárias por exercício).

Até a Issue #6, o sistema apresentava o relatório analítico de uma única sessão de vídeo isolada (`GET /api/sessoes/{id}/relatorio`). Era necessário consolidar a **evolução longitudinal do paciente ao longo dos dias e sessões de exercícios** sob três pilares clínicos:
1. **Amplitude Articular (°):** progressão do ângulo médio e máximo ($\bar{\theta}, \theta_{\max}$) por série, por sessão e entre os dias ($\Delta \theta = \bar{\theta}_{\text{atual}} - \bar{\theta}_{\text{inicial}}$), confrontada com a faixa esperada do Plano (`amplitude_esperada_texto`) e o limite de segurança do Laudo Médico (`limite_amplitude_max`).
2. **Consistência Biomecânica (0–100%):** combinação ponderada entre taxa de repetições válidas sem compensações posturais (50%), regularidade cinemática angular e temporal entre repetições/séries via coeficiente de variação $1 - CV$ (30%) e adesão ao volume diário prescrito $N \times M$ (20%).
3. **Nível de Dor (0–10):** conversão determinística dos segmentos de fala de dor (`sem_dor`, `desconforto`, `dor`, `muita_dor`) ponderados pelo percentual do tempo do vídeo para a escala clínica numérica `0–10`, comparada ao limite `dor_maxima_aceitavel` do plano.

Além disso, o fisioterapeuta precisa de um **Painel de Alertas Clínicos** consolidado (`GET /api/alertas` e `PATCH /api/alertas/{id}`) para triagem rápida de eventos críticos e de atenção.

---

## 2. Decisão Arquitetural

1. **Modelagem Multi-Dias e Decomposição em Séries (`SessionDocument` e `PlanDocument`):**
   - `PlanDocument` passa a armazenar `dias_tratamento` (default `3`), `avaliado_evolucao` e `observacoes_avaliacao_final`.
   - `SessionDocument` passa a armazenar `dia_tratamento` (`1..D`), `series_prescritas` ($N$), `repeticoes_por_serie` ($M$), `serie_index` (opcional), `amplitude_maxima`, `amplitude_media`, `consistencia_score`, `dor_score_0_10`, `dor_percentual_tempo`, `series_breakdown` (lista de métricas por série `Série 1..N`) e `avaliado_fisioterapeuta`.
   - Quando um vídeo contém todas as repetições do exercício no dia, o motor `build_series_breakdown` agrupa automaticamente os `RepetitionEvent` (ou sintetiza a partir do resumo da sessão) em blocos de tamanho $M$ (`repeticoes_por_serie`), calculando a amplitude média, pico e consistência de cada série (`Série 1..N`).

2. **Serviço de Agregação Longitudinal (`evolution_service.py`):**
   - Centraliza os cálculos matemáticos de `dor_score_0_10`, `consistencia_score`, `series_breakdown`, geração automática de alertas clínicos (`generate_alerts_for_session`) e montagem do relatório longitudinal (`build_patient_evolution_report`).
   - Produz o parecer clínico longitudinal (`parecer_clinico`) e recomendações de ajuste de plano (`recomendacoes_plano`) sempre utilizando linguagem de **apoio à decisão clínica** (*"indica"*, *"sugere"*, *"recomenda-se revisão"*), sem emitir diagnóstico médico.

3. **Coleção MongoDB `alertas` e `AlertRepository`:**
   - Alertas são gerados automaticamente ao concluir o processamento de uma sessão (`MongoResultSink.save`) e persistidos na coleção `alertas` com severidade (`critico`, `atencao`, `verde`) e status (`novo`, `lido`, `tratado`).

4. **Endpoints REST Adicionados:**
   - `GET /api/pacientes/{paciente_id}/relatorio-evolucao`: retorna o relatório final longitudinal completo do paciente.
   - `POST /api/pacientes/{paciente_id}/seed-evolucao`: popula/regenera uma jornada multi-dias (`Dia 1`, `Dia 2`, `Dia 3`) para demonstração imediata.
   - `POST /api/pacientes/{paciente_id}/avaliar-evolucao`: registra o parecer e avaliação final do fisioterapeuta/médico.
   - `PATCH /api/sessoes/{session_id}/avaliar`: persiste a marcação individual da sessão como avaliada.
   - `GET /api/alertas` e `PATCH /api/alertas/{alerta_id}`: listagem filtrada com contadores e atualização de status de alertas.

---

## 3. Consequências

- **Positivas:**
  - Atende integralmente à jornada multi-dias do paciente ($D$ dias $\times$ $K$ exercícios/dia $\times$ $N$ séries $\times$ $M$ repetições/série).
  - Resolve também as demandas correlatas de decomposição em múltiplas séries e histórico evolutivo por slot de exercício.
  - Preserva 100% de compatibilidade retroativa com as sessões e testes existentes (146 testes automatizados passando no backend).
- **Trade-offs:**
  - Para sessões legadas que não possuíam `amplitude_media` ou `series_breakdown` persistidos no documento da sessão, `ensure_session_metrics_populated` reconstrói essas métricas sob demanda a partir dos eventos no MongoDB ou dos contadores da sessão.

