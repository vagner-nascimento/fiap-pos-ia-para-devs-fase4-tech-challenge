# Backend — Fisio Coach (FastAPI & Pose Engine)

Serviço de backend responsável pela orquestração do pipeline multimodal de Inteligência Artificial, API RESTful e motor de visão computacional para análise biomecânica com **MediaPipe Pose** e detecção de equipamentos com **YOLO**.

---

## ⚙️ Pré-requisitos e Instalação

* **Python:** 3.11 (versão estável compatível com MediaPipe e OpenCV)
* **Gerenciador de Pacotes:** [`uv`](https://docs.astral.sh/uv/) (Astral)
* **Dependências de Sistema (Linux):** `libgl1` e `libglib2.0-0` (já embutidas no Dockerfile)
* **Execução de IA:** CPU-only por padrão; PyTorch e Torchvision são instalados pelos índices CPU do PyTorch, sem CUDA/NVIDIA.

A partir do diretório `backend`:

```sh
# Copia variáveis de ambiente de desenvolvimento
cp .env.example .env

# Sincroniza dependências do ambiente virtual isolado com Python 3.11
uv sync
```

---

## 🏃 Como Executar

### 1. Iniciar o Servidor FastAPI
Inicia a API REST na porta `3000`:

```sh
uv run python -m src.main
```

* **Swagger / OpenAPI:** [http://localhost:3000/docs](http://localhost:3000/docs)
* **Health Check:** [http://localhost:3000/api/health](http://localhost:3000/api/health)
* **Rotas de Pacientes, Planos e Laudos (Issues #3 e #4):**
  * `GET /api/pacientes`: Lista pacientes sintéticos cadastrados (com seed inicial `PAC-001` a `PAC-004` e filtro opcional `?nome=` insensível a acentos);
  * `POST /api/pacientes`: Cadastra ou atualiza um paciente sintético;
  * `GET /api/pacientes/{id}`: Retorna os dados consolidados do paciente (`patient` + `laudo` + `plano` + `sessoes_recentes`);
  * `GET /api/pacientes/{id}/sessoes`: Retorna o histórico de sessões do paciente ordenadas da mais recente para a mais antiga;
  * `POST /api/pacientes/laudo/extrair`: Extrai automaticamente região, lesão e restrições a partir do texto livre do laudo (preview);
  * `POST /api/pacientes/{id}/laudo` · `GET /api/pacientes/{id}/laudo`: Salva e consulta o laudo médico estruturado do paciente;
  * `POST /api/pacientes/{id}/plano` · `GET /api/pacientes/{id}/plano`: Salva e consulta o plano de prescrição de exercícios e limites clínicos do paciente;
  * `GET /api/pacientes/catalogo-exercicios`: Catálogo completo dos 7 exercícios clínicos (`FISIO-001` a `FISIO-007`) para prescrição.
* **Rotas de Sessões e Biomecânica:**
  * `POST /api/sessoes`: Recebe upload multipart de vídeo (`.mp4`), registra sessão e processa em background (`202 Accepted`);
  * `GET /api/datasets/fisio/status`: Consulta se o dataset oficial está disponível;
  * `POST /api/datasets/fisio/download`: Clona o dataset oficial para a área persistente do backend;
  * `GET /api/datasets/fisio/clips`: Lista os vídeos reais disponíveis;
  * `POST /api/sessoes/referencia`: Dispara a análise a partir de clipe catalogado do dataset;
  * `GET /api/sessoes/clips-referencia`: Alias do catálogo de clipes reais;
  * `GET /api/sessoes`: Lista sessões persistidas no MongoDB (com filtro opcional `?paciente_id=`);
  * `GET /api/sessoes/{id}`: Detalhes da sessão com resumo, score, classificação de risco e progresso (`processing_steps`, `current_step`, `current_step_index`, `total_steps`, `progress_percent` e `progress_message`);
  * `GET /api/sessoes/{id}/eventos`: Linha do tempo de repetições, desvios e falas de dor;
  * `GET /api/sessoes/{id}/relatorio`: Relatório analítico individual estruturado para o frontend e laudo médico;
  * `GET /api/sessoes/exercicios`: Catálogo de exercícios com os equipamentos obrigatórios;
  * `GET /media/...`: Serve os vídeos anotados transcodificados em H.264 e snapshots de evidência em JPG.

> 💡 **Dica de Testes:** O repositório inclui o arquivo [`api.http`](../api.http) na raiz com todas as requisições prontas para execução imediata no VS Code / IDE.

---

### 2. Executar a CLI de Análise de Vídeo
O motor de pose pode ser executado diretamente pelo terminal, inclusive gravando nas coleções do MongoDB:

```sh
uv run python -m cli.analyze_video \
  --video /caminho/do/video.mp4 \
  --case FISIO-001 \
  --side auto \
  --target-reps 5 \
  --paciente-id PAC-001 \
  --mongo \
  --run-id teste_01
```

**Principais Parâmetros:**
* `--video`: Caminho absoluto ou relativo para o arquivo `.mp4`;
* `--dataset-clip`: Nome do clipe dentro do dataset local (alternativa a `--video`);
* `--case`: Código do exercício (`FISIO-001` a `FISIO-007`);
* `--side`: Lado do corpo avaliado (`auto` [padrão], `direito` ou `esquerdo`);
* `--target-reps`: Quantidade de repetições prescritas (padrão: 5);
* `--paciente-id`: Identificador sintético do paciente (ex: `PAC-001`);
* `--mongo`: Ativa a persistência documental das repetições e desvios no MongoDB;
* `--run-id`: Identificador da execução (define o nome da subpasta de saída e `session_id`);
* `--no-render`: Executa apenas a análise matemática e relatórios JSON sem gerar o vídeo `.mp4` anotado (processamento ultrarrápido).

Nos exercícios FISIO-006 e FISIO-007, o pipeline também executa o modelo
pré-treinado em `src/yolo/best.pt`. O modelo não é treinado durante a execução:
o resultado inclui percentuais de frames sem detecção, parcialmente detectados
e totalmente detectados. Os demais exercícios não carregam o detector.

### Progresso da sessão

O processamento em background publica atualizações incrementais no documento
da sessão por meio de `SessionRepository.update_progress`. O estado é
monotônico para impedir que callbacks atrasados façam a sessão retroceder.
As seis etapas públicas são definidas em
[`src/models/database/processing.py`](src/models/database/processing.py) e
correspondem à recepção do vídeo, extração de pose, análise biomecânica,
transcrição de áudio, geração de artefatos e persistência do relatório.

---

### 3. Executar os Testes Automatizados
O backend conta com suíte de testes unitários abrangendo geometria biomecânica, histerese de repetições, analisadores de exercícios e isolamento de caminhos de mídia:

```sh
uv run pytest tests -q
```

---

## 📁 Estrutura de Diretórios

```text
backend/
├── src/
│   ├── cli/
│   │   └── analyze_video.py            # Interface CLI de processamento de vídeos
│   ├── config/
│   │   └── media_paths.py              # MediaStorage: isolamento e resolução de caminhos
│   ├── infra/database/                 # Conexão MongoDB e repositórios
│   │   ├── mongodb_client.py           # Conector e gerenciador de sessões PyMongo
│   │   └── repositories/               # Session, Event, Patient, Plan e MedicalReport Repositories
│   ├── models/                         # Modelos de Domínio e Transporte
│   │   ├── database/                   # Documentos MongoDB (sessoes, eventos, pacientes, laudos, planos)
│   │   └── rest/                       # Payloads e Responses da API (JSON)
│   ├── services/
│   │   ├── audio_transcription.py      # Áudio, Faster-Whisper local e classificação de fala de dor
│   │   ├── clinical_extractor.py       # Extrator determinístico de entidades de laudos médicos (pt-BR)
│   │   └── pose/                       # Motor de Visão Computacional
│   │       ├── analyzers/              # 7 Analisadores especializados (FISIO-001 a 007)
│   │       ├── base_analyzer.py        # Base com Template Method, histerese e auto-lado
│   │       ├── geometry.py             # Fórmulas trigonométricas e ângulos 2D
│   │       ├── hud_renderer.py         # HUD responsivo com Pillow e UTF-8
│   │       ├── object_detector.py      # YOLO CPU-only para faixa elástica e halter
│   │       ├── joint_mapper.py         # Mapeamento de landmarks e lados corporais
│   │       ├── landmark_extractor.py   # Extração via MediaPipe Pose com sampling a 30 FPS
│   │       ├── models.py               # Modelos Pydantic de eventos e telemetria
│   │       ├── registry.py             # Catálogo de exercícios suportados
│   │       ├── repetitions.py          # Suavização temporal e detecção de repetições
│   │       ├── sinks.py                # Strategy de persistência (File, Mongo, Composite)
│   │       └── video_processor.py      # Orquestrador ponta a ponta do pipeline de vídeo
│   ├── yolo/
│   │   └── best.pt                 # Melhor checkpoint pré-treinado; não há treino na API
│   ├── rest/routers/                   # Endpoints da API REST (/api/health, /api/pacientes, /api/sessoes)
│   ├── server.py                       # Fábrica FastAPI, middlewares de CORS e /media
│   └── main.py                         # Ponto de entrada do Uvicorn (porta 3000)
└── tests/
    └── unit/                           # Testes unitários com Pytest (137 testes)
```

---

## 🔐 Variáveis de Ambiente

Configuradas no arquivo `.env` (ou no `docker-compose.yaml`):

| Variável | Descrição | Padrão Local | Padrão Docker |
|---|---|---|---|
| `MEDIA_ROOT` | Raiz onde entradas e saídas de mídia são gravadas | `../data` | `/app/data` |
| `DATASET_ROOT` | Caminho persistente do clone de clipes sintéticos | `../data/datasets/fisio` | `/app/data/datasets/fisio` |
| `DATASET_REF` | Branch/ref clonada pelo backend | `main` | `main` |
| `MONGO_DB_SERVER` | URI de conexão do MongoDB | `mongodb://localhost:27017` | `mongodb://mongodb:27017` |
| `MONGO_DB_NAME` | Nome do banco no MongoDB | `fiap-pos-ia-db` | `fiap-pos-ia-db` |
| `WHISPER_MODEL_SIZE` | Tamanho do modelo `faster-whisper` | `medium` | `medium` |
| `WHISPER_DEVICE` | Dispositivo de inferência do Whisper | `cpu` | `cpu` |
| `WHISPER_COMPUTE_TYPE` | Tipo de computação do Whisper | `int8` | `int8` |

O Whisper é executado localmente com `faster-whisper`, em CPU, usando áudio
convertido para mono/16 kHz, redução de ruído, normalização e parâmetros
orientados a português brasileiro e fisioterapia. Não há dependência de
serviços de cloud para transcrição ou classificação de dor.

---

## 📖 Arquitetura e Decisões de Projeto

Para uma visão detalhada sobre a arquitetura do motor de visão e persistência, consulte:
* 🏛️ [Arquitetura do Sistema](../docs/arquitetura/arquitetura-do-sistema.md)
* 📑 [ADR 0001: Escolha do MediaPipe Pose](../docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md)
* 📑 [ADR 0002: Padrão Strategy para Analisadores](../docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md)
* 📑 [ADR 0005: Renderização de HUD com Pillow e UTF-8](../docs/arquitetura/adrs/0005-renderizacao-de-hud-com-pillow-utf8.md)
* 📑 [ADR 0006: Adoção do MongoDB 7](../docs/arquitetura/adrs/0006-adocao-do-mongodb-para-persistencia.md)
* 📑 [ADR 0007: Padrão Result Sinks e Pipeline Assíncrono](../docs/arquitetura/adrs/0007-padrao-result-sinks-e-pipeline-assincrono-mongodb.md)
* 📑 [ADR 0009: Detecção de Equipamentos com YOLO](../docs/arquitetura/adrs/0009-deteccao-de-equipamentos-com-yolo.md)
* 📑 [ADR 0010: Transcrição Local com Faster-Whisper](../docs/arquitetura/adrs/0010-transcricao-local-com-faster-whisper.md)
* 📑 [ADR 0011: Detecção de Dor por Transcrição](../docs/arquitetura/adrs/0011-deteccao-de-dor-por-transcricao.md)
* 📑 [ADR 0012: Extração Estruturada de Laudos e Persistência de Prescrições](../docs/arquitetura/adrs/0012-extracao-estruturada-laudos-e-prescricoes.md)
