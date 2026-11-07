# Gaps e Melhorias — Fisio Coach (Tech Challenge Fase 4)

> Análise comparativa entre os **requisitos do [edital-tech-challenge-fase4.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/edital-tech-challenge-fase4.md)** e o **estado atual do repositório**.
> Data de análise: 07/11/2026

---

## Resumo Executivo

O projeto **Fisio Coach** apresenta um nível de maturidade técnica e arquitetural excelente para a entrega do Tech Challenge da Fase 4. Toda a cadeia multimodal (vídeo + áudio + texto clínico) encontra-se implementada, integrada de ponta a ponta e coberta por **147 testes automatizados** no backend (`pytest` + `mongomock`). O sistema realiza a extração de pose com **Google MediaPipe Pose** para 7 exercícios clínicos (`FISIO-001` a `FISIO-007`), detecção de equipamentos ortopédicos (`faixa_elastica` e `halter`) com **YOLO** customizado (`best.pt`), transcrição de áudio local com **Faster-Whisper** e classificação determinística de relatos verbais de dor/desconforto, extração de entidades de laudos médicos em português, comparação com prescrições diárias (`dias_prescritos`), avaliação longitudinal multi-dias ($D$ dias $\times$ $N$ séries $\times$ $M$ repetições) e geração automática de alertas clínicos para o fisioterapeuta.

As decisões de escopo e arquitetura estão solidamente fundamentadas em **13 Architecture Decision Records (ADRs)** ([`docs/arquitetura/adrs/`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs)): a substituição do OpenPose pelo MediaPipe Pose ([ADR 0001](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md)) e a adoção de `faster-whisper` + regras determinísticas locais em vez de serviços pagos da Azure ([ADR 0010](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0010-transcricao-local-com-faster-whisper.md) e [ADR 0011](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0011-deteccao-de-dor-por-transcricao.md)) garantem custo zero e execução 100% reproduzível em CPU via `docker compose up`. Da mesma forma, o recorte clínico voltado à reabilitação fisioterapêutica (monitorando anomalias em padrões de movimentação biomecânica, dor relatada e evolução longitudinal de prescrições, sem escopo de sinais vitais hospitalares) já foi validado em alinhamento com o professor.

Dessa forma, **todos os requisitos funcionais e técnicos de código (`R01` a `R08`) estão 100% atendidos**. Foram identificados apenas **2 Gaps Críticos (`G01` e `G02`)**, ambos restritos aos entregáveis finais de submissão documental e audiovisual (`R09` — consolidação dos resultados obtidos e exemplos de anomalias no Relatório Técnico; e `R10` — gravação e link do vídeo demonstrativo de até 15 minutos), além de **4 Melhorias Importantes (`M01` a `M04`)** voltadas ao polimento documental do repositório para a banca avaliadora.

---

## 🔴 Gaps Críticos (Requisitos Obrigatórios Não Atendidos ou Parcialmente Atendidos)

### G01 — Consolidação de "Resultados Obtidos e Exemplos de Anomalias Detectadas" no Relatório Técnico (`R09`)

**Requisito do documento:**
> "### Repositório Git
> - Código-fonte completo da solução;
> - Relatório técnico com:
>   - Descrição do fluxo multimodal.
>   - Modelos aplicados em cada tipo de dado.
>   - Resultados obtidos e exemplos de anomalias detectadas."

**Situação atual:**
- Os dois primeiros subitens do relatório técnico (**descrição do fluxo multimodal** e **modelos aplicados em cada tipo de dado**) estão amplamente documentados em [arquitetura-do-sistema.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/arquitetura-do-sistema.md), com diagramas C4 (Níveis 1, 2 e 3), diagrama de sequência multimodal e tabela de cobertura clínica dos 7 exercícios.
- Existem guias parciais de validação em [walkthrough-motor-deteccao-pose.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/walkthrough-motor-deteccao-pose.md) e [walkthrough-passo-3-relatorio-individual.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/walkthrough-passo-3-relatorio-individual.md), bem como a listagem do dataset sintético em [docs/dataset_fisioterapia_sintetico/README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/dataset_fisioterapia_sintetico/README.md).
- **Falta:** Uma seção consolidada (em [arquitetura-do-sistema.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/arquitetura-do-sistema.md) ou em um documento dedicado `docs/relatorio-tecnico-fase4.md` referenciado no [README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/README.md)) apresentando formalmente os **resultados obtidos** na execução dos clipes do dataset (`FISIO-001` a `FISIO-007`) e um **catálogo de exemplos concretos de anomalias detectadas** pelo sistema (ex.: compensação postural com ângulo medido vs. limite do laudo, ausência de equipamento obrigatório detectada pelo YOLO, relato verbal de dor intensa transcrito com timestamp e regressão longitudinal entre dias gerando alerta `critico` no painel).

**Ação recomendada:**
- Criar o documento consolidado `docs/relatorio-tecnico-fase4.md` (ou adicionar a Seção 7 em [arquitetura-do-sistema.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/arquitetura-do-sistema.md)) contendo:
  1. Tabela de resultados obtidos por caso (`FISIO-001` a `FISIO-007`) comparando execuções corretas vs. execuções com desvio/dor;
  2. Exemplos reais de payloads/saídas de anomalias detectadas nas 4 dimensões do Fisio Coach: (a) anomalia biomecânica/postural, (b) anomalia de equipamento (`faixa_elastica`/`halter`), (c) anomalia vocal de dor (`dor`/`muita_dor` acima de `dor_maxima_aceitavel`) e (d) anomalia longitudinal na evolução da prescrição multi-dias;
  3. Link em destaque no [README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/README.md) sob o título **Relatório Técnico Oficial (Entregável Fase 4)**.

---

### G02 — Produção e Link do Vídeo Demonstrativo de até 15 Minutos (`R10`)

**Requisito do documento:**
> "### Vídeo com até 15 minutos demonstrando
> - Upload no YouTube ou Vimeo (público ou não listado);
> - Demonstração do processamento multimodal:
>   - Exemplo prático da análise de áudio e vídeo;
>   - Detecção e resposta a anomalias;
>   - Integração dos serviços Azure;
>   - Fluxo final do alerta à equipe médica."

**Situação atual:**
- Toda a interface web React ([`frontend/src/components/`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/frontend/src/components)) e os fluxos de demonstração rápida (incluindo seletor de clipes do dataset oficial e botão `"Simular jornada (3 dias)"` em [`PatientEvolutionReportView.jsx`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/frontend/src/components/PatientEvolutionReportView.jsx)) já estão prontos para gravação.
- **Falta:** Gravar o vídeo de até 15 minutos, realizar o upload no YouTube ou Vimeo (público ou não listado) e adicionar a seção com o link oficial do vídeo no [README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/README.md).

**Ação recomendada:**
- Estruturar o roteiro de gravação cobrindo os pontos exigidos pelo edital:
  1. Contextualização da arquitetura multimodal e justificativa técnica/financeira do uso de modelos locais em CPU (`MediaPipe Pose`, `YOLO`, `Faster-Whisper` + NLP determinístico) em substituição aos serviços pagos de nuvem;
  2. Cadastro/revisão de Laudo Médico e Prescrição de Exercícios por dia (`Tela 1`);
  3. Visão do Paciente (`Telas 2 e 3`): consulta da prescrição por dia, aceite do Termo LGPD e envio de vídeo com áudio;
  4. Acompanhamento do processamento multimodal (`Tela 4`) e análise detalhada do Relatório da Sessão (`Tela 5`: vídeo anotado H.264, HUD, séries, desvios com snapshots, equipamento via YOLO e timeline de fala de dor);
  5. Detecção de anomalias longitudinais no Relatório Final de Evolução Multi-Dias (`Tela 7`) e tratativa no Painel de Alertas Clínicos pela equipe de fisioterapia (`Tela 6`).
- Inserir o link do vídeo publicado em uma seção de destaque no topo do [README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/README.md).

---

## 🟡 Melhorias Importantes (Qualidade, Robustez e Apresentação)

### ~~M01~~ ✅ Resolvido — Sincronização do `PRD v1.2` com as Decisões Arquiteturais Finais

**Situação atual:**
- O documento [prd-fisio-coach-tech-challenge-fase4-v1_2.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/prd-fisio-coach-tech-challenge-fase4-v1_2.md) foi atualizado na Seção 5.2 para explicitar `RF-05` a `RF-07` (Dor por expressão facial) como **Opcional / Evolução Futura**, e a Seção 11 (`Mapeamento com o edital`) foi ajustada para refletir a substituição dos serviços Azure por componentes locais em CPU por redução de custos e sem pendências de validação.

---

### ~~M02~~ ✅ Resolvido — Tabela Executiva de Aderência ao Edital no `README.md` Raiz

**Situação atual:**
- Adicionada a seção `## 🎯 Aderência ao Edital (Tech Challenge – Fase 4)` no topo do [README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/README.md) mapeando cada eixo do Edital (`1. Análise de Vídeo`, `2. Análise de Áudio`, `3. Detecção de Anomalias e Alertas` e `4. Fusão Multimodal e Privacidade`) para os módulos e ADRs correspondentes.

---

### ~~M03~~ ✅ Resolvido — Documentação das Métricas do Treinamento YOLO (`best.pt`) no ADR 0009

**Situação atual:**
- O [ADR 0009](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0009-deteccao-de-equipamentos-com-yolo.md) foi enriquecido com as tabelas de hiperparâmetros (`args.yaml`, 23 imagens rotuladas, 100 épocas com `yolo11n.pt`) e de evolução das métricas de validação (`results.csv`, atingindo **76,36% de precisão**, **75,00% de recall**, **67,60% de mAP50** e **44,97% de mAP50-95** no melhor checkpoint).

---

### M04 — Criação de Arquivo `backend/.env.example`

**Situação atual:**
- O diretório `frontend/` possui [`frontend/.env.example`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/frontend/.env.example), enquanto o diretório `backend/` documenta suas variáveis de ambiente (`MEDIA_ROOT`, `DATASET_ROOT`, `DATASET_REF`, `MONGO_DB_SERVER`, `MONGO_DB_NAME`, `WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`) apenas na tabela do [backend/README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/README.md#L163-L177).
- **Impacto:** Ter um arquivo `backend/.env.example` padroniza a configuração local fora do Docker para desenvolvedores e avaliadores.

**Ação recomendada:**
- Criar `backend/.env.example` com os valores padrão documentados em [backend/README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/README.md).

---

## 🟢 Pontos Positivos (Requisitos bem atendidos)

| Requisito | Status | Evidência |
|---|---|---|
| **R01 — Processar vídeos clínicos (sessões de fisioterapia)** | ✅ Atendido | Pipeline completo em [`video_processor.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/pose/video_processor.py), cobrindo 7 exercícios clínicos (`FISIO-001` a `FISIO-007`) com upload até 200 MB, validação de consentimento LGPD ([ADR 0013](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0013-upload-de-videos-por-slot-e-consentimento-lgpd.md)) e transcodificação H.264 para web ([ADR 0008](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0008-transcodificacao-h264-para-streaming-web.md)). |
| **R02 — Detectar movimentos fora do padrão (Pose) e objetos críticos (YOLO)** | ✅ Atendido | Rastreamento de 33 landmarks com **MediaPipe Pose** ([`landmark_extractor.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/pose/landmark_extractor.py), [ADR 0001](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md)), 7 analisadores biomecânicos ([`analyzers/`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/pose/analyzers), [ADR 0002](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md)) e detecção de equipamentos (`faixa_elastica` e `halter`) com **YOLO** ([`object_detector.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/pose/object_detector.py), [ADR 0009](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0009-deteccao-de-equipamentos-com-yolo.md)). |
| **R03 — Gerar relatórios automáticos indicando desvios ou falhas** | ✅ Atendido | Relatório individual da sessão ([`SessionReportView.jsx`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/frontend/src/components/SessionReportView.jsx)) com vídeo anotado, snapshots fotográficos comprobatórios (`evidence/*.jpg`), decomposição por série (`Série 1..N`) e Relatório Final de Evolução Multi-Dias ([`PatientEvolutionReportView.jsx`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/frontend/src/components/PatientEvolutionReportView.jsx)). |
| **R04 — Processar áudios clínicos e detectar sintomas relacionados à fala** | ✅ Atendido | No recorte clínico do projeto, monitora relatos verbais espontâneos de **dor e desconforto** durante os exercícios (`pouca_ou_nenhuma_dor`, `desconforto`, `dor`, `muita_dor`), com tratamento de negação e alinhamento temporal na timeline ([`audio_transcription.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/audio_transcription.py)). |
| **R05 — Transcrição de áudio e identificação de termos críticos/sentimentos (alternativa local por custo)** | ✅ Atendido | Implementado com **Faster-Whisper** local em CPU (mono/16 kHz, redução de ruído, VAD e prompt clínico pt-BR) + classificador determinístico de domínio e extrator clínico de laudos ([`clinical_extractor.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/clinical_extractor.py)), devidamente justificados por custo zero nos [ADR 0010](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0010-transcricao-local-com-faster-whisper.md), [ADR 0011](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0011-deteccao-de-dor-por-transcricao.md) e [ADR 0012](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0012-extracao-estruturada-laudos-e-prescricoes.md). |
| **R06 — Detecção de anomalias em padrões de movimentação e na evolução de prescrições** | ✅ Atendido | Detecta compensações posturais, violação de limites de amplitude do laudo médico, dor acima do tolerável no plano e regressões ao longo dos dias e séries do tratamento ([`evolution_service.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/evolution_service.py), [ADR 0014](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0014-relatorio-final-evolucao-multi-dias-e-alertas.md)). Escopo focado em fisioterapia (sem sinais vitais) alinhado com o professor. |
| **R07 — Gerar alertas automáticos para a equipe médica com base nas anomalias** | ✅ Atendido | Persistência automática na coleção `alertas` ([`alert.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/models/database/alert.py), [`alert_repository.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/infra/database/repositories/alert_repository.py)), endpoints `GET/PATCH /api/alertas` ([`alerts.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/rest/routers/alerts.py)) e Painel de Alertas Clínicos na interface do fisioterapeuta ([`AlertsPanelView.jsx`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/frontend/src/components/AlertsPanelView.jsx)). |
| **R08 — Entregável: Código-fonte completo, reproduzível e testado no Git** | ✅ Atendido | Stack completa orquestrada via [`docker-compose.yaml`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docker-compose.yaml) e [`start_app.sh`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/start_app.sh), coleção de chamadas [`api.http`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/api.http) com 27 requisições e suíte de **147 testes unitários e de integração** passando. |
| **R09 — Entregável: Relatório técnico (fluxo, modelos, resultados e exemplos de anomalias)** | ⚠️ Parcial | Fluxo multimodal e modelos estão detalhados em [arquitetura-do-sistema.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/arquitetura-do-sistema.md); falta consolidar a seção de **resultados obtidos e exemplos de anomalias detectadas** (`G01`). |
| **R10 — Entregável: Vídeo demonstrativo de até 15 minutos (YouTube/Vimeo)** | ❌ Ausente | Falta gravar/publicar o vídeo demonstrativo e inserir o link no [README.md](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/README.md) (`G02`). |

---

## 📋 Backlog Priorizado de Ações

| Prioridade | ID | Título | Esforço Estimado |
|---|---|---|---|
| 🔴 Alta | G01 | Consolidar seção/documento de Relatório Técnico com resultados obtidos no dataset e exemplos de anomalias detectadas | 2h |
| 🔴 Alta | G02 | Elaborar roteiro, gravar vídeo demonstrativo de até 15 min (YouTube/Vimeo) e incluir link no `README.md` | 4h |
| ✅ Concluído | ~~M02~~ | Adicionar tabela executiva de rastreabilidade "Edital Fase 4 × Solução Fisio Coach" no `README.md` raiz | 0.5h |
| ✅ Concluído | ~~M01~~ | Atualizar `PRD v1.2` alinhando escopo opcional da Seção 5.2 e ajustes na Seção 11 | 0.5h |
| ✅ Concluído | ~~M03~~ | Documentar métricas do treinamento YOLO (`best.pt`) no `ADR 0009` | 1h |
| 🟢 Baixa | M04 | Criar arquivo `backend/.env.example` padronizado com `backend/README.md` | 0.5h |

