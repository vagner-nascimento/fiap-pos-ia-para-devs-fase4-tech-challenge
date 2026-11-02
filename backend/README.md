# Backend — Fisio Coach (FastAPI & Pose Engine)

Serviço de backend responsável pela orquestração do pipeline multimodal de Inteligência Artificial, API RESTful e motor de visão computacional para análise biomecânica com **MediaPipe Pose**.

---

## ⚙️ Pré-requisitos e Instalação

* **Python:** 3.11 (versão estável compatível com MediaPipe e OpenCV)
* **Gerenciador de Pacotes:** [`uv`](https://docs.astral.sh/uv/) (Astral)
* **Dependências de Sistema (Linux):** `libgl1` e `libglib2.0-0` (já embutidas no Dockerfile)

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
* **Rotas de Sessões e Biomecânica:**
  * `POST /api/sessoes`: Recebe upload multipart de vídeo (`.mp4`), registra sessão e processa em background (`202 Accepted`);
  * `POST /api/sessoes/referencia`: Dispara a análise a partir de clipe do dataset via payload JSON;
  * `GET /api/sessoes/clips-referencia`: Lista o catálogo de clipes sintéticos de referência para teste;
  * `GET /api/sessoes`: Lista sessões persistidas no MongoDB (com filtro opcional `?paciente_id=`);
  * `GET /api/sessoes/{id}`: Detalhes da sessão com resumo, score e classificação de risco;
  * `GET /api/sessoes/{id}/eventos`: Linha do tempo de repetições e desvios;
  * `GET /api/sessoes/{id}/relatorio`: Relatório analítico individual estruturado para o frontend e laudo médico;
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
* `--dataset-clip`: Nome do clipe dentro de `DATASET_ROOT` (alternativa a `--video`);
* `--case`: Código do exercício (`FISIO-001` a `FISIO-007`);
* `--side`: Lado do corpo avaliado (`auto` [padrão], `direito` ou `esquerdo`);
* `--target-reps`: Quantidade de repetições prescritas (padrão: 5);
* `--paciente-id`: Identificador sintético do paciente (ex: `PAC-001`);
* `--mongo`: Ativa a persistência documental das repetições e desvios no MongoDB;
* `--run-id`: Identificador da execução (define o nome da subpasta de saída e `session_id`);
* `--no-render`: Executa apenas a análise matemática e relatórios JSON sem gerar o vídeo `.mp4` anotado (processamento ultrarrápido).

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
│   │   └── repositories/               # SessionRepository e EventRepository
│   ├── models/                         # Modelos de Domínio e Transporte
│   │   ├── database/                   # SessionDocument e EventDocument (BSON)
│   │   └── rest/                       # Payloads e Responses da API (JSON)
│   ├── services/
│   │   └── pose/                       # Motor de Visão Computacional
│   │       ├── analyzers/              # 7 Analisadores especializados (FISIO-001 a 007)
│   │       ├── base_analyzer.py        # Base com Template Method, histerese e auto-lado
│   │       ├── geometry.py             # Fórmulas trigonométricas e ângulos 2D
│   │       ├── hud_renderer.py         # HUD responsivo com Pillow e UTF-8
│   │       ├── joint_mapper.py         # Mapeamento de landmarks e lados corporais
│   │       ├── landmark_extractor.py   # Extração via MediaPipe Pose com sampling a 30 FPS
│   │       ├── models.py               # Modelos Pydantic de eventos e telemetria
│   │       ├── registry.py             # Catálogo de exercícios suportados
│   │       ├── repetitions.py          # Suavização temporal e detecção de repetições
│   │       ├── sinks.py                # Strategy de persistência (File, Mongo, Composite)
│   │       └── video_processor.py      # Orquestrador ponta a ponta do pipeline de vídeo
│   ├── rest/routers/                   # Endpoints da API REST (/api/health, /api/sessoes)
│   ├── server.py                       # Fábrica FastAPI, middlewares de CORS e /media
│   └── main.py                         # Ponto de entrada do Uvicorn (porta 3000)
└── tests/
    └── unit/                           # Testes unitários com Pytest (100 testes)
```

---

## 🔐 Variáveis de Ambiente

Configuradas no arquivo `.env` (ou no `docker-compose.yaml`):

| Variável | Descrição | Padrão Local | Padrão Docker |
|---|---|---|---|
| `MEDIA_ROOT` | Raiz onde entradas e saídas de mídia são gravadas | `../data` | `/app/data` |
| `DATASET_ROOT` | Caminho do repositório de clipes sintéticos | `../../fiap-pos-ia-...-datasets` | `/app/datasets` |
| `MONGO_DB_SERVER` | URI de conexão do MongoDB | `mongodb://localhost:27017` | `mongodb://mongodb:27017` |
| `MONGO_DB_NAME` | Nome do banco no MongoDB | `fiap-pos-ia-db` | `fiap-pos-ia-db` |

---

## 📖 Arquitetura e Decisões de Projeto

Para uma visão detalhada sobre a arquitetura do motor de visão e persistência, consulte:
* 🏛️ [Arquitetura do Sistema](../docs/arquitetura/arquitetura-do-sistema.md)
* 📑 [ADR 0001: Escolha do MediaPipe Pose](../docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md)
* 📑 [ADR 0002: Padrão Strategy para Analisadores](../docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md)
* 📑 [ADR 0005: Renderização de HUD com Pillow e UTF-8](../docs/arquitetura/adrs/0005-renderizacao-de-hud-com-pillow-utf8.md)
* 📑 [ADR 0006: Adoção do MongoDB 7](../docs/arquitetura/adrs/0006-adocao-do-mongodb-para-persistencia.md)
* 📑 [ADR 0007: Padrão Result Sinks e Pipeline Assíncrono](../docs/arquitetura/adrs/0007-padrao-result-sinks-e-pipeline-assincrono-mongodb.md)
