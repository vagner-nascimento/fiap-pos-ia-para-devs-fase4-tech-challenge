# Resumo de Progresso e Estado Atual — Pipeline Multimodal

**Data/Hora do Handover:** 29/10/2026 (atualizado)  
**Documento de Arquitetura Principal:** `docs/arquitetura/plano-motor-deteccao-pose-mediapipe.md`

---

## 1. O Que Já Foi Implementado e Testado

### Etapa 1: Fundação & Infraestrutura de Mídia (Concluída)
- **`MediaStorage` (`backend/src/config/media_paths.py`):** Ponto único para caminhos de entrada e saída, impedindo *path traversal* e garantindo caminhos relativos para persistência.
- **Estrutura de Pastas:** `data/inputs/` e `data/outputs/` criados com `.gitkeep`.
- **Gitignore & Ambientes:** `.gitignore` ignora dados sensíveis de `data/`; `.env.example` atualizado com `MEDIA_ROOT=../data` e `DATASET_ROOT`.
- **Docker Compose:** Volume persistente `./data:/app/data`; o dataset é baixado pelo backend para `data/datasets/fisio`.
- **Dockerfile:** `git`, `libgl1` e `libglib2.0-0` adicionados para download do dataset, OpenCV e MediaPipe.
- **Dependências (`backend/pyproject.toml`):** `mediapipe==0.10.21`, `opencv-python-headless>=4.8,<5`, `numpy>=1.24,<2.0`, `scipy>=1.11,<2.0`, `requires-python = ">=3.11,<3.13"`.

### Etapa 2: Núcleo de Visão e Algoritmos Base (Concluída)
- **`geometry.py`:** Funções geométricas puras (ângulos entre 3 pontos, inclinações com sinal em relação à vertical/horizontal, distâncias e ponto médio em pixels).
- **`joint_mapper.py`:** `BodySide` dinâmico (`direito`, `esquerdo`, `auto`, `ambos`) e `JointMapper` que entrega os landmarks MediaPipe sem lados fixos/hardcoded.
- **`models.py`:** `PoseFrame`, `RepetitionEvent`, `DeviationEvent`, `TelemetryPoint`, `SessionSummary`, `ExerciseAnalysisResult` em Pydantic.
- **`repetitions.py`:** `fill_gaps` para interpolação de lacunas curtas, `smooth` (média móvel preservando NaNs) e `RepetitionDetector` com histerese (conta repetições mesmo parciais para reportar desvios).
- **`base_analyzer.py`:** Template method `BaseExerciseAnalyzer` com suporte a `AUTO` (avalia ambos os lados e elege o ativo por amplitude x visibilidade), detecção de fases (`repouso`, `concentrica`, `pico`, `excentrica`) e geração de telemetria amostrada.
- **`landmark_extractor.py`:** Leitor de vídeo com OpenCV + MediaPipe com amostragem inteligente (`max_fps=30.0` e `stride`) para alta performance.

### Etapa 3: Analisadores de Exercícios (Em Andamento)
- **`FISIO-001` (Extensão de Joelho Sentado):**
  - Implementado em `backend/src/services/pose/analyzers/fisio_001_knee_extension.py`.
  - Calibrado e validado contra os 4 clipes reais do dataset:
    * `correto`: 5 reps válidas, 0 desvios, score 100%.
    * `extensao-parcial`: `amplitude_reduzida` em todas as repetições.
    * `inclinacao-tronco`: `compensacao_tronco` detectado.
    * `velocidade-irregular`: `ritmo_acelerado` detectado.
- **`registry.py`:** Factory de instâncias por `case_id` ou `exercise_id`.
- **Testes Unitários:** 76 testes passando com `pytest tests/ -q`.

### Etapa 4: Renderizador, CLI & Gravadores (Concluída)
- **`hud_renderer.py`:** HUD visual superior dinâmico e responsivo com Pillow UTF-8 e alertas em tempo real.
- **`video_processor.py`:** Pipeline ponta a ponta gerando `annotated.mp4` e snapshots em `evidence/`.
- **`analyze_video.py`:** CLI executável para validação local com parâmetros `--case`, `--video`, `--side`, `--target-reps`, `--paciente-id` e `--mongo`.

### Etapa 5: Passo 2 — Integração com MongoDB (Concluída)
- **Modelos de Banco (`backend/src/models/database/`):**
  * `SessionDocument` (coleção `sessoes`): status da sessão, classificação de risco (`VERDE`, `ATENCAO`, `CRITICO`), justificativas explicáveis, caminhos de mídia em `data/` e métricas consolidadas.
  * `EventDocument` (coleção `eventos`): repetições com timestamps e valores biomecânicos; desvios posturais com evidências fotográficas.
- **Repositórios de Dados (`backend/src/infra/database/repositories/`):**
  * `SessionRepository`: upsert de sessões, recuperação, listagem filtrada e atualização de etapas.
  * `EventRepository`: gravação em lote (*batch insert*) e listagem por sessão e tipo.
- **Padrão Strategy de Persistência (`backend/src/services/pose/sinks.py`):**
  * `ResultSink`: interface abstrata desacoplando a visão computacional do banco de dados.
  * `FileResultSink`: persistência em arquivos locais (`analysis.json`, `telemetry.json`).
  * `MongoResultSink`: classificação automática de risco clínico, extração de justificativas e salvamento no MongoDB.
  * `CompositeResultSink`: persistência combinada (arquivo + MongoDB) sem duplicação de esforço.
- **API REST (`backend/src/rest/routers/sessions.py`):**
  * `GET /api/sessoes`: listagem das sessões mais recentes (com filtro opcional por paciente).
  * `GET /api/sessoes/{id}`: detalhes consolidados da sessão.
  * `GET /api/sessoes/{id}/eventos`: eventos de repetições e desvios associados.
- **Testes Automatizados:** 97 testes unitários passando (`pytest tests/ -v`).

### Etapa 6: Passo 3 — Frontend & Relatório Individual do Vídeo (Issue #6 - Concluída)
- **Design System Oficial (`docs/design/`):**
  * `frontend/src/tokens.css` criado e importado com todos os tokens formais (`--fc-*`), tipografia *Plus Jakarta Sans*, espaçamentos e raios.
  * Componentes do Design System (`frontend/src/components/ds/`): `Button`, `Card`, `StatusChip` (●/▲/■), `StepList` (etapas com ✓, … e numerais), `Timeline` (faixas de 28px) e `VideoPlayer` sincronizado.
- **Telas da Jornada Implementadas:**
  * **Tela 4 (Processamento - `ProcessingView.jsx`):** Feedback visual em tempo real com `StepList`, barra de progresso e polling automático.
  * **Tela 5 (Relatório da Sessão - `SessionReportView.jsx`):** Player HTML5 do vídeo anotado com HUD (`/media/outputs/.../annotated.mp4`), timeline multicamadas sincronizada, galeria de snapshots de evidência com modal lightbox, conformidade biomecânica e botão "Baixar PDF / Imprimir" com CSS `@media print`.
  * **Histórico & Nova Análise (`SessionsListView.jsx`):** Tabela de sessões registradas no MongoDB, filtros e modal com tabs para upload de MP4 ou seleção de clipe do dataset sintético.
  * **AppShell (`App.jsx`):** Sidebar fixa de 220px (`--fc-primary-dark`), navegação fluida entre telas e aba de monitoramento API Health mantida.
- **Backend & Infraestrutura:**
  * `frontend/nginx.conf` e `frontend/vite.config.js`: Proxies configurados para servir `/media/` a partir do backend, com `client_max_body_size 250M;` e timeouts estendidos de 600s para uploads grandes.
  * `services/pose/video_processor.py`: Transcodificação automática pós-renderização para **H.264 (`yuv420p` + `+faststart`)** via FFmpeg, garantindo playback nativo em navegadores modernos sem erros de decodificação.
  * Endpoints REST adicionados: status/download/catalogo em `/api/datasets/fisio`, `GET /api/sessoes/clips-referencia` e `GET /api/sessoes/{id}/relatorio`.
  * A tela de nova análise exibe `Download Dataset` quando os clipes ainda não estão disponíveis e lista apenas vídeos reais após o download.
  * Testes automatizados: 121 testes passando no backend e build de produção do frontend validado (`npm run build`).

### Etapa 7: Áudio local, dor por transcrição e detecção de equipamentos (Concluída)
- **Áudio:** extração da trilha do vídeo, conversão para mono/16 kHz, redução de
  ruído, normalização e transcrição local com Faster-Whisper em CPU.
- **Dor:** classificação determinística de segmentos transcritos em níveis de
  dor/desconforto, com timestamps e texto original para a timeline do relatório.
- **Equipamentos:** YOLO CPU-only carregado de `backend/src/yolo/best.pt`,
  ativado somente para FISIO-006 (`faixa_elastica`) e FISIO-007 (`halter`).
  O vídeo mantém pose, landmarks, alertas e HUD, e acrescenta status do objeto;
  o relatório exibe os percentuais de detecção. Exercícios sem equipamento não
  carregam o detector.
- **Infraestrutura:** PyTorch e Torchvision foram fixados nos índices
  CPU-only, evitando a instalação dos runtimes CUDA/NVIDIA.

### Etapa 8: Inserção de Dados de Laudo e Prescrições por Paciente (Issue #3 - Concluída)
- **Modelos e Repositórios MongoDB:**
  * `PatientDocument` (`pacientes`), `MedicalReportDocument` (`laudos`) e `PlanDocument` / `PrescribedExerciseItem` (`planos`), com repositórios dedicados (`PatientRepository`, `MedicalReportRepository`, `PlanRepository`) e seed automático dos 4 cenários sintéticos do PRD (`PAC-001` a `PAC-004` / `LAU-A` a `LAU-D`).
- **Extração Determinística de Laudos (`backend/src/services/clinical_extractor.py`):**
  * Extrai região anatômica, lesão/condição, movimentos restritos e limite angular máximo a partir do texto livre em pt-BR, além de parser de faixa de amplitude esperada (`parse_amplitude_range`).
- **API REST (`backend/src/rest/routers/patients.py`):**
  * `GET /api/pacientes`, `POST /api/pacientes`, `GET /api/pacientes/{id}`;
  * `POST /api/pacientes/laudo/extrair`, `POST /api/pacientes/{id}/laudo`, `GET /api/pacientes/{id}/laudo`;
  * `POST /api/pacientes/{id}/plano`, `GET /api/pacientes/{id}/plano`, `GET /api/pacientes/catalogo-exercicios` (todos os 7 exercícios `FISIO-001` a `FISIO-007`).
  * Integração de `comparacao_clinica` em `GET /api/sessoes/{id}/relatorio` com os dados reais do plano e laudo do paciente.
- **Frontend (`frontend/src/components/PlanAndReportView.jsx` e `Field.jsx`):**
  * Implementação da **Tela 1 ("Plano e laudo")** e modal da **Tela 8 ("Novo paciente")** alinhados ao Mock `01-Plano-Laudo.dc.html` e ao Design System (`tokens.css`), com chips extraídos automaticamente e edição manual pelo fisioterapeuta.
- **Testes Automatizados:** 130 testes passando no backend (`pytest tests/ -v`).

### Etapa 9: Busca de Dados de Laudo e Prescrições pelo Paciente (Issue #4 - Concluída)
- **Backend (`PatientRepository` e `/api/pacientes`):**
  * Busca tolerante a acentos e caixa alta/baixa em `GET /api/pacientes?nome=` (ex.: buscar `"claudia"` retorna `"Cláudia M."` / `PAC-003`).
  * Novo endpoint `GET /api/pacientes/{id}/sessoes` e enriquecimento de `GET /api/pacientes/{id}` com `sessoes_recentes` para cruzar os slots prescritos com as sessões já enviadas pelo paciente.
- **Frontend (`frontend/src/components/PatientPrescriptionView.jsx`):**
  * Implementação da **Tela 2 ("Minha prescrição")** seguindo o Mock `02-Paciente-Envio.dc.html` e o Design System (`tokens.css`), com busca por nome/ID, pílulas de acesso rápido, card **"Laudo e limites"** e listagem dos **slots de exercícios prescritos** com status (`● Enviada`, `Em análise` ou `Pendente de envio`).
- **Testes Automatizados:** 137 testes passando no backend (`pytest tests/ -v`).

---

## 2. Progresso da tela de processamento

O acompanhamento da análise utiliza seis etapas reais publicadas pelo backend:

1. vídeo recebido;
2. extração de pose e landmarks;
3. análise biomecânica do movimento;
4. transcrição de áudio e fala de dor;
5. geração do vídeo anotado e evidências;
6. persistência e relatório.

O backend persiste a etapa, o índice, o percentual, a mensagem e o horário da
última atualização durante o processamento. A tela de processamento consome
esse contrato por polling e não deve criar etapas adicionais no frontend.

Expressão facial, fusão com plano/laudo e outras capacidades ainda não
implementadas não fazem parte dessa lista.

---

## 3. Próximos Passos Imediatos

1. Upload de vídeos pelo paciente diretamente nos slots de exercícios prescritos com termo de aceite LGPD (Issue #5).
2. Relatório final de evolução entre sessões e painel de alertas consolidado (Issue #7).
3. Evolução da análise de dor e expansão dos datasets de validação.
