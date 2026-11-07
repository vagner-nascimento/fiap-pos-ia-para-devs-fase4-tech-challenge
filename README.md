# Fisio Coach — FIAP Pós-Tech IA para Devs (Fase 4)

Plataforma multimodal orientada por Inteligência Artificial para auxílio ao fisioterapeuta no monitoramento remoto e avaliação biomecânica de sessões de reabilitação física.

O sistema analisa gravações de vídeo e áudio de pacientes executando exercícios prescritos, realizando o rastreamento de pontos articulares (landmarks), contagem automática de repetições, detecção de desvios posturais, identificação de equipamentos com YOLO, transcrição local da fala relacionada à dor, renderização de vídeo anotado com HUD responsivo e geração de relatórios clínicos com snapshots comprobatórios.

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
* **Dataset:** o botão `Download Dataset` clona o repositório oficial para `data/datasets/fisio`; o catálogo fica disponível após o status `ready`;
* **MongoDB:** `mongodb://localhost:27017`

> A demonstração roda em CPU. O PyTorch usado pelo detector YOLO é resolvido
> pelos wheels CPU-only; não é necessário instalar CUDA ou uma GPU NVIDIA.

**Comandos Úteis:**
```sh
sh stop_app.sh     # Para os containers preservando dados
sh restart_app.sh  # Reinicia e reconstrói as aplicações
```

---

### Opção 2: Processamento de Vídeos via Linha de Comando (CLI)

O motor de visão computacional pode ser executado diretamente pelo terminal (com suporte nativo a CPU e alta performance), gravando em disco e opcionalmente no MongoDB:

```sh
# A partir da raiz do repositório (usando uv com Python 3.11):
uv run ./backend/src/cli/analyze_video.py \
  --video /caminho/para/seu/video.mp4 \
  --case FISIO-001 \
  --side auto \
  --target-reps 5 \
  --paciente-id PAC-001 \
  --mongo \
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

### Opção 3: Execução e Consulta via API REST (`api.http`)

Com a stack ativa, você pode disparar análises e consultar sessões/eventos diretamente pelo VS Code usando o arquivo de conveniência [`api.http`](api.http):

* **Cadastro e consulta de pacientes, laudos e prescrições (Issues #3 e #4):**
  `GET http://localhost:3000/api/pacientes?nome=` · `POST http://localhost:3000/api/pacientes` · `GET http://localhost:3000/api/pacientes/{id}` · `GET http://localhost:3000/api/pacientes/{id}/sessoes`
* **Inserção e consulta de laudo médico com extração automática e plano de exercícios:**
  `POST/GET http://localhost:3000/api/pacientes/{id}/laudo` · `POST/GET http://localhost:3000/api/pacientes/{id}/plano`
* **Download/status do dataset:** `GET /api/datasets/fisio/status` · `POST /api/datasets/fisio/download`
* **Disparo assíncrono por clipe do dataset (retorna 202 com BackgroundTasks):**
  `POST http://localhost:3000/api/sessoes/referencia`
* **Upload multipart de vídeo gravado pelo paciente por slot da prescrição (Issue #5):**
  `POST http://localhost:3000/api/sessoes` (`paciente_id`, `slot_id`, `exercicio`/`exercicio_id`, `lgpd_aceite=true` e `file` até 200 MB)
* **Listagem e detalhes da sessão no MongoDB:**
  `GET http://localhost:3000/api/sessoes` · `GET http://localhost:3000/api/sessoes/{id}`
* **Linha do tempo de repetições e desvios:**
  `GET http://localhost:3000/api/sessoes/{id}/eventos`
* **Streaming de vídeo anotado e snapshots:**
  `GET http://localhost:3000/media/outputs/{id}/pose/annotated.mp4`

---

## 📁 Onde os Resultados são Gravados?

1. **No Sistema de Arquivos (`data/outputs/{run_id}/pose/`):**
   * **`annotated.mp4`**: Vídeo final com landmarks/esqueleto, HUD, alertas biomecânicos e, nos exercícios FISIO-006 e FISIO-007, caixas e status do equipamento;
   * **`analysis.json`**: Relatório executivo estruturado com repetições, desvios, transcrição/classificação de dor e resumo percentual do equipamento;
   * **`telemetry.json`**: Série temporal frame a frame dos ângulos articulares medidos;
   * **`evidence/*.jpg`**: Snapshots fotográficos congelados no momento exato em que cada desvio ocorreu.

2. **No Banco de Dados MongoDB (`fiap-pos-ia-db`):**
   * **Coleção `pacientes`**: Cadastro sintético dos pacientes (`paciente_id`, `nome`, `idade`, `observacoes`), com seed inicial (`PAC-001` a `PAC-004`);
   * **Coleção `laudos`**: Laudo médico estruturado com região anatômica, lesão, movimentos restritos e limite angular máximo extraídos do texto e revisados pelo profissional;
   * **Coleção `planos`**: Plano de prescrição de exercícios do paciente (dor máxima aceitável `0–10`, faixa de amplitude esperada e lista de exercícios prescritos com `slot_id`, séries, repetições, lado e equipamento);
   * **Coleção `sessoes`**: Documento executivo consolidado com vínculo ao slot da prescrição (`slot_id`), aceite LGPD (`lgpd_aceite`), arquivo original (`original_filename`, `file_size_bytes`), status (`enviado`, `processando`, `concluido`, `erro`), classificação clínica de risco (`verde`, `atencao`, `critico`), justificativas explicáveis e caminhos relativos de mídia;
   * **Coleção `eventos`**: Repetições biomecânicas (pico, duração, validade), desvios posturais com referências às evidências fotográficas e falas relacionadas à dor (`fala_dor`).

---

## 🧪 Testes Automatizados

O backend conta com suíte automatizada de **139 testes unitários e de integração** (Pytest + `mongomock`):

```sh
cd backend
uv run pytest tests -v
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
  * [ADR 0007: Padrão Result Sinks e Pipeline Assíncrono](docs/arquitetura/adrs/0007-padrao-result-sinks-e-pipeline-assincrono-mongodb.md)
  * [ADR 0008: Transcodificação H.264 para Streaming Web](docs/arquitetura/adrs/0008-transcodificacao-h264-para-streaming-web.md)
  * [ADR 0009: Detecção de Equipamentos com YOLO](docs/arquitetura/adrs/0009-deteccao-de-equipamentos-com-yolo.md)
  * [ADR 0010: Transcrição Local com Faster-Whisper](docs/arquitetura/adrs/0010-transcricao-local-com-faster-whisper.md)
  * [ADR 0011: Detecção de Dor por Transcrição](docs/arquitetura/adrs/0011-deteccao-de-dor-por-transcricao.md)
  * [ADR 0012: Extração Estruturada de Laudos e Persistência de Prescrições](docs/arquitetura/adrs/0012-extracao-estruturada-laudos-e-prescricoes.md)
  * [ADR 0013: Busca Privada de Prescrição, Upload por Slot e Consentimento LGPD](docs/arquitetura/adrs/0013-upload-de-videos-por-slot-e-consentimento-lgpd.md)
* 📋 **[PRD Oficial do Projeto](docs/prd-fisio-coach-tech-challenge-fase4-v1_2.md)** — Requisitos funcionais (RF-01 a RF-21), regras de negócio e personas;
* 🗂️ **[Plano – Issue #3 (Inserção de Dados de Laudo e Prescrições)](plans/plano-issue-3-insercao-laudo-prescricoes.md)** — Especificação de backend, extração clínica e frontend para planos e laudos;
* 🗂️ **[Plano – Issue #4 (Busca de Dados de Laudo e Prescrições pelo Paciente)](plans/plano-issue-4-busca-laudo-prescricoes.md)** — Especificação da visão do paciente (Tela 2 — *"Minha prescrição"*), busca tolerante a acentos e status por slot;
* 🗂️ **[Plano – Issue #5 (Upload de Vídeo de Seção de Exercícios pelo Paciente)](plans/plano-issue-5-upload-videos-paciente.md)** — Especificação do upload de vídeos por slot prescrito (Tela 3 — *"Enviar sessões"*), progresso via XHR e aceite LGPD;
* 🛠️ **[Walkthrough – Passo 3 (Relatório Individual e Frontend)](docs/walkthrough-passo-3-relatorio-individual.md)** — Guia de execução e testes da interface web do relatório individual (Issue #6);
* 🛠️ **[Walkthrough do Motor de Detecção de Pose](docs/walkthrough-motor-deteccao-pose.md)** — Guia de desenvolvimento e calibração via CLI (Passo 1).
