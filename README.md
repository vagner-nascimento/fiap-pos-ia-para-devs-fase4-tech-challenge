# Fisio Coach — FIAP Pós-Tech IA para Devs (Fase 4)

Plataforma multimodal orientada por Inteligência Artificial para auxílio ao fisioterapeuta no monitoramento remoto e avaliação biomecânica de sessões de reabilitação física.

O sistema analisa gravações de vídeo e áudio de pacientes executando exercícios prescritos, realizando o rastreamento de pontos articulares (landmarks), contagem automática de repetições, detecção de desvios posturais em tempo real, renderização de vídeo anotado com HUD responsivo e geração de relatórios clínicos com snapshots comprobatórios.

> Para detalhes aprofundados sobre decisões de engenharia, diagramas C4 e modelos matemáticos, consulte a [Documentação de Arquitetura](docs/arquitetura/arquitetura-do-sistema.md) e os [ADRs](docs/arquitetura/adrs/).

---

## 🚀 Como Executar o Projeto

### Opção 1: Aplicação Completa via Docker Compose (Recomendado)

Inicia o Frontend (Nginx/React), o Backend (FastAPI + Motor de Pose) e o Banco de Dados (MongoDB 7):

```sh
# Usando o script de conveniência:
sh start_app.sh

# Ou diretamente via Docker Compose:
docker compose -f docker-compose.yaml up -d --build
```

**Portas e Acessos:**
* **Frontend Web:** [http://localhost:8080](http://localhost:8080)
* **Backend API (Docs OpenAPI):** [http://localhost:3000/docs](http://localhost:3000/docs)
* **Health Check:** [http://localhost:3000/api/health](http://localhost:3000/api/health)
* **MongoDB:** `mongodb://localhost:27017`

**Comandos Úteis:**
```sh
sh stop_app.sh     # Para os containers preservando dados
sh restart_app.sh  # Reinicia e reconstrói as aplicações
```

---

### Opção 2: Processamento de Vídeos via Linha de Comando (CLI)

O motor de visão computacional pode ser executado diretamente pelo terminal (com suporte nativo a CPU e alta performance) para analisar qualquer vídeo da base de dados:

```sh
# A partir da raiz do repositório (usando uv com Python 3.11):
uv run ./backend/src/cli/analyze_video.py \
  --video /caminho/para/seu/video.mp4 \
  --case FISIO-001 \
  --side auto \
  --target-reps 5 \
  --run-id sessao_teste_01
```

**Exercícios Suportados no MVP (`--case`):**
* `FISIO-001`: Extensão de joelho sentado
* `FISIO-002`: Pêndulo de ombro (Codman)
* `FISIO-003`: Inclinação pélvica deitado
* `FISIO-004`: Rotação de joelhos deitado
* `FISIO-005`: Flexão de ombro com bastão
* `FISIO-006`: Abdução de ombro com elástico
* `FISIO-007`: Flexão de cotovelo com halter

---

## 📁 Onde os Resultados são Gravados?

Todas as saídas geradas ficam centralizadas fora do Git na pasta `data/outputs/{run_id}/pose/`:

* **`annotated.mp4`**: Vídeo final com o esqueleto articular e HUD em tempo real (fase, ângulo, contagem e alertas em português);
* **`analysis.json`**: Relatório executivo estruturado (repetições válidas/inválidas, taxa de conformidade e desvios com timestamps);
* **`telemetry.json`**: Série temporal frame a frame dos ângulos articulares medidos;
* **`evidence/*.jpg`**: Snapshots fotográficos congelados no momento exato em que cada desvio ocorreu.

---

## 🧪 Testes Automatizados

Para executar a suíte completa de testes unitários do motor de pose e caminhos de mídia:

```sh
cd backend
uv run pytest tests -q
```

---

## 📚 Documentação do Projeto

* 🏛️ **[Arquitetura do Sistema](docs/arquitetura/arquitetura-do-sistema.md)** — Diagramas C4 Níveis 1, 2 e 3, diagramas de sequência multimodal e cobertura clínica dos exercícios;
* 📑 **[Architecture Decision Records (ADRs)](docs/arquitetura/adrs/)** — Registros formais de decisões:
  * [ADR 0001: Adoção do MediaPipe Pose](docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md)
  * [ADR 0002: Padrão Strategy para Exercícios](docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md)
  * [ADR 0003: Detecção Automática do Lado Ativo](docs/arquitetura/adrs/0003-deteccao-automatica-de-lado-ativo.md)
  * [ADR 0004: Armazenamento Isolado de Mídias](docs/arquitetura/adrs/0004-armazenamento-desacoplado-de-midias.md)
  * [ADR 0005: HUD Responsivo com Pillow e UTF-8](docs/arquitetura/adrs/0005-renderizacao-de-hud-com-pillow-utf8.md)
  * [ADR 0006: Adoção do MongoDB](docs/arquitetura/adrs/0006-adocao-do-mongodb-para-persistencia.md)
* 📋 **[PRD Oficial do Projeto](docs/prd-fisio-coach-tech-challenge-fase4-v1_2.md)** — Requisitos funcionais (RF-01 a RF-21), regras de negócio e personas;
* 🛠️ **[Walkthrough de Implementação](docs/walkthrough-motor-deteccao-pose.md)** — Guia passo a passo de desenvolvimento e calibração dos analisadores.
