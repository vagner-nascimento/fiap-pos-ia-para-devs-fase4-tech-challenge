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

*(Nota: Para iniciar a API localmente, o MongoDB deve estar em execução na porta 27017, ou iniciado via `docker compose up -d mongodb`).*

---

### 2. Executar a CLI de Análise de Vídeo
O motor de pose pode ser executado diretamente em vídeos gravados para produzir relatórios, telemetria e o vídeo anotado com HUD:

```sh
uv run python -m cli.analyze_video \
  --video /caminho/do/video.mp4 \
  --case FISIO-001 \
  --side auto \
  --target-reps 5 \
  --run-id teste_01
```

**Principais Parâmetros:**
* `--video`: Caminho absoluto ou relativo para o arquivo `.mp4`;
* `--case`: Código do exercício (`FISIO-001` a `FISIO-007`);
* `--side`: Lado do corpo avaliado (`auto` [padrão], `direito` ou `esquerdo`);
* `--target-reps`: Quantidade de repetições prescritas (padrão: 5);
* `--run-id`: Identificador da execução (define o nome da subpasta de saída);
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
│   │       └── video_processor.py      # Orquestrador ponta a ponta do pipeline de vídeo
│   ├── infra/database/                 # Conexão MongoDB assíncrona
│   ├── rest/routers/                   # Endpoints da API REST
│   └── main.py                         # Ponto de entrada do Uvicorn
└── tests/
    └── unit/                           # Testes unitários com Pytest
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

Para uma visão detalhada sobre a arquitetura do motor de visão, consulte:
* 🏛️ [Arquitetura do Sistema](../docs/arquitetura/arquitetura-do-sistema.md)
* 📑 [ADR 0001: Escolha do MediaPipe Pose](../docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md)
* 📑 [ADR 0002: Padrão Strategy para Analisadores](../docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md)
* 📑 [ADR 0005: Renderização de HUD com Pillow e UTF-8](../docs/arquitetura/adrs/0005-renderizacao-de-hud-com-pillow-utf8.md)
