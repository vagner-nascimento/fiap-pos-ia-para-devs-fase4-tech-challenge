# PRD – Fisio Coach (MVP 2 refinado)

**Tech Challenge – Fase 4 · IADT**
**Versão:** 1.2 (rascunho para validação do grupo) · **Data:** 21/10/2026 · **Entrega:** 17/11/2026

> Este PRD é uma proposta do grupo, não consta no edital. O prazo de entrega oficial e o canal de submissão devem ser confirmados.

**Histórico de versões**

| Versão | Mudanças |
|---|---|
| 1.0 | Versão inicial: escopo funcional, métricas, cronograma e riscos |
| 1.1 | Incorpora o boilerplate do projeto (React + FastAPI + MongoDB + Docker Compose): arquitetura concreta, processamento assíncrono, contrato de API, coleções do MongoDB, requisitos não funcionais, riscos e cronograma revisados. O escopo funcional (RF-01 a RF-19) não mudou. |
| 1.2 | Cronograma com períodos encerrando aos sábados (primeiro período em 10/10). Sinais vitais removidos do escopo (não obrigatórios neste momento). Exercícios de referência definidos pelo `dataset_index.json`. Azure Speech to Text removido por redução de custos (transcrição substituída por componente local). Ajustes em RF-02, RF-04, RF-08, arquitetura, dados, métricas, mapeamento com o edital, riscos e perguntas em aberto. |

---

## 1. Resumo

O **Fisio Coach** analisa vídeos de sessões de fisioterapia e verifica se o paciente executa o exercício prescrito com a postura correta e **sem dor acima do tolerável**. A dor é estimada de forma multimodal: **expressão facial** (vídeo) e **fala** (áudio: o que o paciente diz e como diz). O resultado final é **comparado com a prescrição de exercícios e o laudo médico** da lesão, gerando um relatório automático e alertas ao fisioterapeuta.

**Modalidades:** vídeo + áudio + texto (prescrição e laudo). Atende à premissa de pelo menos 2 formatos.

## 2. Problema e objetivo

**Problema.** Em sessões (presenciais ou gravadas), o fisioterapeuta não consegue observar toda repetição, nem correlacionar postura, dor relatada e dor expressa com o plano de tratamento. Dor subnotificada ou exercícios contraindicados para a lesão aumentam o risco de agravamento.

**Objetivo do MVP.** Entregar, até 17/11/2026, um pipeline funcional, executável com `docker compose up`, que:
1. detecta desvios posturais por exercício;
2. estima dor por face e por voz;
3. cruza tudo com prescrição e laudo;
4. gera relatório e alerta demonstráveis em vídeo de até 15 min.

**Não objetivos.** Diagnóstico clínico, substituir o fisioterapeuta, app mobile em produção, integração com prontuário real, uso de dados identificáveis reais, autenticação multiusuário completa, monitoramento de sinais vitais.

## 3. Usuários

| Persona | Necessidade |
|---|---|
| **Fisioterapeuta** (principal) | Receber relatório objetivo da sessão e ser alertado de dor/risco |
| **Paciente** | Enviar/gravar sessão e relatar dor naturalmente, falando |
| **Médico/ortopedista** (secundário) | Ver se o plano respeita o laudo |

## 4. Jornada principal

1. O fisioterapeuta cadastra o **plano**: exercícios (a partir da lista de referência da seção 8.1), séries/repetições, limite de dor aceitável e faixa de movimento esperada.
2. O **laudo** é estruturado (lesão, região, movimentos restritos, limite de amplitude). No MVP, é texto sintético processado por extração de entidades.
3. O paciente grava a sessão (vídeo com áudio) e envia pela interface web.
4. O sistema processa em segundo plano, em paralelo: **postura**, **equipamento**, **expressão facial** e **áudio**. A interface mostra o progresso.
5. A **fusão** gera uma linha do tempo da sessão com eventos de postura, picos de dor facial e falas de dor.
6. O resultado é **comparado com plano e laudo**, e classificado em verde, atenção ou crítico.
7. Geram-se o **relatório da sessão** e o **alerta**, exibidos no painel do fisioterapeuta.

## 5. Escopo funcional

### 5.1 Análise de postura e equipamento (vídeo)
- **RF-01** Extrair keypoints do corpo com OpenPose e calcular ângulos articulares por frame.
- **RF-02** Identificar o exercício executado (ou receber como parâmetro do plano, usando os 7 exercícios de referência da seção 8.1) e segmentar **repetições**.
- **RF-03** Comparar com a postura de referência do exercício e marcar desvios (amplitude insuficiente, compensações, assimetria).
- **RF-04** Detectar com YOLOv8 o equipamento prescrito (faixa elástica, bastão de PVC ou cabo de espuma, halter leve, colchonete, mesa ou apoio estável) e sinalizar se ausente ou incorreto.

### 5.2 Dor por expressão facial (vídeo)
- **RF-05** Detectar o rosto e extrair landmarks/Action Units faciais relacionadas à dor (sobrancelha abaixada, olhos contraídos, nariz franzido, lábio superior elevado, olhos fechados).
- **RF-06** Calcular um **índice facial de dor** por janela de tempo (0–10), baseado na escala PSPI (*Prkachin and Solomon Pain Intensity*) ou equivalente simplificado.
- **RF-07** Tratar rosto fora de quadro ou ocluído como "sem dado" e nunca como "sem dor".

### 5.3 Dor por áudio (transcrição local + Azure Text Analytics + acústica)
- **RF-08** Transcrever o áudio em pt-BR com **modelo de reconhecimento de fala executado localmente** (sugestão: faster-whisper, modelo `small`, dentro do container), com timestamps por segmento. Substitui o Azure Speech to Text por redução de custos (ver seção 6.5 e riscos).
- **RF-09** Com **Azure Text Analytics (AI Language)** e um dicionário pt-BR de dor, extrair: menção de dor, **região** ("joelho", "ombro"), **grau** ("7 de 10", "muita dor", "fisgada") e **sentimento**.
- **RF-10** Extrair features acústicas (pitch, energia, pausas, respiração audível, gemidos) para um **índice vocal de dor**.
- **RF-11** Converter o relato verbal em escala numérica 0–10 (NRS); termos qualitativos mapeiam para faixas definidas e documentadas.

### 5.4 Fusão multimodal e comparação clínica
- **RF-12** Alinhar, em uma linha do tempo única, repetições, desvios, picos de dor facial e falas de dor.
- **RF-13** Calcular o **score de dor consolidado** por repetição e por sessão, ponderando relato verbal (maior peso, por ser autorrelato), face e voz. Discordâncias entre fontes (ex.: diz "estou bem" com face de dor) são sinalizadas como **inconsistência**.
- **RF-14** Comparar com a **prescrição**: dor acima do limite do plano, exercício com dor persistente, queda de amplitude ou de repetições frente às sessões anteriores (também é a forma de tratar a "evolução de prescrição" do edital).
- **RF-15** Comparar com o **laudo**: movimento ou região contraindicada executada, amplitude além do limite, dor localizada na região da lesão.
- **RF-16** Classificar a sessão em **Verde / Atenção / Crítico** com regras explícitas e justificativa textual.

### 5.5 Relatório e alertas
- **RF-17** Gerar relatório automático (HTML/PDF): resumo, repetições, desvios com frames de evidência, gráfico de dor ao longo do tempo, trechos transcritos, comparação com plano e laudo, evolução vs. sessões anteriores.
- **RF-18** Disparar **alerta** ao fisioterapeuta com severidade, motivo e evidência anexada: exibido no **painel de alertas** (único canal na versão inicial).
- **RF-19** Manter histórico por paciente para comparar sessões.

### 5.6 Interface web
- **RF-20** Telas para: cadastro de paciente, plano e laudo; upload de sessão; acompanhamento do processamento; linha do tempo da sessão (player de vídeo sincronizado com os eventos); relatório; painel de alertas; histórico por paciente.
- **RF-21** Exibir o status do processamento em tempo quase real (polling ou SSE) com etapas: enviado, extraindo trilhas, vídeo, áudio, fusão, concluído ou erro.

## 6. Arquitetura

### 6.1 Componentes (boilerplate)

| Componente | Tecnologia | Papel no Fisio Coach |
|---|---|---|
| Frontend | React 19, Vite, Nginx (porta 8080) | Cadastros, upload, linha do tempo, relatório e painel de alertas |
| Backend | Python 3.11, FastAPI, Uvicorn (porta 3000, rotas sob `/api`) | API e orquestração do pipeline de IA |
| Banco | MongoDB 7 (volume `mongodb_data`) | Planos, laudos, sessões, eventos, scores, alertas e histórico |

O Nginx do frontend encaminha `/api` ao serviço `backend` pela rede interna do Compose. A execução padrão do projeto é `docker compose -f docker-compose.yaml up -d --build` (ou `sh start_app.sh`).

### 6.2 Fluxo de processamento

```
Frontend (upload) ─► POST /api/sessoes ─► salva vídeo + cria sessão (status: enviado) ─► responde 202
                                              │
                                  processamento em segundo plano (backend)
                                              ▼
 separação de trilhas
  ├─► frames ─► OpenPose (ângulos, repetições, desvios)
  │          ├─► YOLOv8 (equipamento)
  │          └─► face landmarks/AUs ─► índice facial de dor
  └─► áudio ─► transcrição local (faster-whisper, pt-BR, timestamps)
             ├─► Azure Text Analytics (dor, região, grau, sentimento)
             └─► features acústicas ─► índice vocal de dor
                                              ▼
 Linha do tempo unificada ─► Fusão (score de dor + inconsistências)
 Plano + Laudo (MongoDB) ─► Motor de regras de comparação
                                              ▼
 Classificação Verde/Atenção/Crítico ─► Relatório + Alerta (MongoDB) ─► painel de alertas

Frontend ◄── GET /api/sessoes/{id} (polling ou SSE) até status = concluído
```

**Decisão de execução:** o processamento roda em segundo plano dentro do próprio backend (tarefa assíncrona com pool de threads/processos), atualizando o `status` da sessão no MongoDB a cada etapa. Se o desempenho exigir, evolui-se para um serviço `worker` separado no Compose, sem mudar o contrato da API.

### 6.3 Contrato de API (proposta)

Todas as rotas sob `/api` (já existente: `GET /api/health`).

| Método e rota | Descrição |
|---|---|
| `POST /api/pacientes` · `GET /api/pacientes` · `GET /api/pacientes/{id}` | Cadastro e consulta (dados sintéticos) |
| `POST /api/pacientes/{id}/plano` · `GET /api/pacientes/{id}/plano` | Plano de exercícios (exercícios, séries, repetições, limite de dor, amplitude esperada) |
| `POST /api/pacientes/{id}/laudo` · `GET /api/pacientes/{id}/laudo` | Laudo em texto; o backend extrai a versão estruturada |
| `POST /api/sessoes` | Upload de vídeo (multipart) com `paciente_id` e `exercicio`; retorna `202` e o `id` da sessão |
| `GET /api/sessoes/{id}` | Status e etapa atual; resultado resumido quando concluído |
| `GET /api/sessoes/{id}/eventos` | Linha do tempo: repetições, desvios, picos de dor, falas |
| `GET /api/sessoes/{id}/relatorio` | Relatório da sessão (HTML/PDF) |
| `GET /api/pacientes/{id}/sessoes` | Histórico para comparação entre sessões |
| `GET /api/alertas` · `PATCH /api/alertas/{id}` | Painel de alertas; marcar como lido/tratado |

### 6.4 Coleções do MongoDB (proposta)

| Coleção | Conteúdo principal |
|---|---|
| `pacientes` | Identificador sintético, nome fictício, observações |
| `planos` | `paciente_id`, lista de exercícios (`exercicio_id` do dataset, séries, repetições, limite de dor 0–10, amplitude mínima/máxima, equipamento) |
| `laudos` | `paciente_id`, texto original, lesões (região, tipo), movimentos restritos, limites de amplitude |
| `sessoes` | `paciente_id`, exercício, caminho do vídeo, `status`, etapa, datas, score de dor da sessão, classificação, justificativas |
| `eventos` | `sessao_id`, tipo (repeticao, desvio, dor_facial, fala_dor, inconsistencia), instante inicial e final, valores, evidência (frame, trecho de áudio/transcrição) |
| `alertas` | `sessao_id`, severidade, motivo, evidências, canais enviados, estado (novo, lido, tratado) |

Vídeos, frames de evidência e relatórios ficam em volume Docker (ou GridFS), referenciados pelas coleções.

### 6.5 Serviços Azure e componentes de IA

- **Azure AI Language (Text Analytics):** obrigatório para o vídeo, chamado pelo backend via SDK, para termos críticos e sentimento.
- **Azure Speech to Text:** **removido** por redução de custos. A transcrição passa a ser feita localmente (sugestão: faster-whisper). O edital pede o uso de Azure Speech to Text; essa mudança precisa ser validada com o professor (ver seções 11, 12 e 13).
- **Azure Functions e Blob Storage:** fora do escopo, por não serem necessários ao núcleo do MVP.
- **Chaves e endpoints** entram por variáveis de ambiente no Compose (`.env` fora do Git, `.env.example` versionado).

**Nota técnica a validar:** o Azure Face API restringiu recursos de reconhecimento de emoção; por isso a expressão de dor é tratada com bibliotecas abertas (ex.: MediaPipe Face Mesh/OpenFace), a confirmar na documentação vigente.

## 7. Requisitos não funcionais

| Tema | Requisito |
|---|---|
| **Execução** | Ambiente completo sobe com `docker compose up`; modelos de visão, de transcrição e dependências incluídos nas imagens ou em volume de modelos; sem passos manuais além do `.env` |
| **Tempo real** | Definição do projeto: processamento em **modo streaming simulado** (janelas de 5 s) sobre o vídeo gravado; latência de alerta alvo < 30 s após o fim do processamento de cada janela. Documentar no relatório |
| **Upload e timeouts** | Nginx e FastAPI configurados para vídeos de até ~200 MB (`client_max_body_size` e timeouts ampliados); vídeos de demo curtos (1–3 min) |
| **Desempenho** | Meta: processar 1 min de vídeo em até ~5 min em máquina sem GPU; amostragem de frames (5–10 fps); transcrição com modelo `small` ou `base` |
| **Privacidade/LGPD** | Dados de saúde são sensíveis: voluntários do grupo com **termo de consentimento** (imagem e voz), dataset de referência com casos fictícios e dados **sintéticos** para plano/laudo. Sem dados identificáveis no repositório; `data/` fora do Git |
| **Segredos** | Chaves Azure apenas em `.env`; versionar só `.env.example` |
| **Explicabilidade** | Toda classificação exibe as evidências que a causaram |
| **Ética** | Indicador de apoio à decisão, nunca diagnóstico. Limitações de viés facial (iluminação, tom de pele, barba, óculos) descritas no relatório |
| **Reprodutibilidade** | `requirements.txt` com versões fixas, seeds fixos, script de carga de dados de demonstração (seed do MongoDB) |

## 8. Dados

### 8.1 Exercícios de referência (`dataset_index.json`)

O grupo adota como lista de exercícios de exemplo os 7 casos do dataset sintético multimodal de fisioterapia. Todos os casos, pacientes, laudos, prescrições e falas são fictícios.

| ID | Exercício | Região | Equipamento (YOLOv8) | Clipes |
|---|---|---|---|:---:|
| FISIO-001 | Extensão de joelho sentado | Joelho direito | Nenhum | 4 |
| FISIO-002 | Exercício pendular do ombro | Ombro esquerdo | Mesa ou apoio estável | 4 |
| FISIO-003 | Inclinação pélvica em decúbito dorsal | Coluna lombar e pelve | Colchonete | 4 |
| FISIO-004 | Rotação controlada dos joelhos | Tronco e coluna lombar | Colchonete | 4 |
| FISIO-005 | Flexão de ombro com bastão leve | Ombros | Bastão de PVC ou cabo de espuma | 3 |
| FISIO-006 | Abdução de ombro com faixa elástica leve | Ombro direito | Faixa elástica de baixa resistência | 3 |
| FISIO-007 | Flexão de cotovelo com halter leve | Cotovelo direito | Halter leve de espuma ou peso mínimo | 3 |

Total: **25 clipes** em 7 exercícios. Os laudos de demonstração (seção 8.3) cobrem as regiões desses exercícios.

### 8.2 Fontes de dados

| Dado | Fonte proposta |
|---|---|
| Vídeo de exercícios | Gravações feitas pelos integrantes do grupo seguindo o guia de gravação do dataset (plano geral com articulações visíveis, áudio sincronizado, objetos leves e seguros). Os 25 clipes e a rotulagem por `case_id`, `clip_id`, `label` e instrução executada seguem o `dataset_index.json` |
| Expressão de dor | Expressão encenada pelos integrantes do grupo, sem provocar dor real e sem simular limitação com risco físico. Não se usam datasets externos |
| Áudio de relato | Falas de dor (graus e regiões variados) do dataset, gravadas pelos integrantes do grupo |
| Plano e laudo | **Sintéticos**, carregados por script de seed (seção 8.3) |

**Regras de separação:** treino, validação e teste são separados **por participante**, não por clipe. Identificadores fictícios apenas. Objetos leves e seguros; halteres de espuma ou carga mínima.

### 8.3 Laudos sintéticos de demonstração

| Laudo | Lesão fictícia | Exercícios associados | Movimento restrito (exemplo) |
|---|---|---|---|
| LAU-A | Tendinopatia de ombro | FISIO-002, FISIO-005, FISIO-006 | Elevação acima de 90° sem controle |
| LAU-B | Pós-LCA de joelho | FISIO-001 | Extensão forçada com dor na região do joelho |
| LAU-C | Lombalgia | FISIO-003, FISIO-004 | Rotação lombar ampla sob carga |
| LAU-D | Epicondilite lateral | FISIO-007 | Flexão de cotovelo com carga acima do limite |

Os laudos são ficcionais e não constituem orientação médica ou fisioterapêutica.

## 9. Métricas de sucesso

| Métrica | Meta MVP |
|---|---|
| Contagem de repetições vs. contagem manual | erro ≤ 10% |
| Detecção de desvio postural vs. rotulagem manual do grupo | F1 ≥ 0,70 |
| Transcrição da fala (WER) vs. texto de referência do dataset | WER ≤ 20% |
| Extração de grau de dor da fala (NRS) | acerto ±1 ponto em ≥ 80% das falas de teste |
| Detecção de picos de dor facial vs. rotulagem manual | F1 ≥ 0,65 |
| Classificação final (Verde/Atenção/Crítico) vs. julgamento do grupo | concordância ≥ 80% em 10+ sessões |
| Latência de alerta | < 30 s |

As metas são hipóteses iniciais e devem ser ajustadas após o primeiro teste com dados reais.

## 10. Cronograma até 17/11/2026

Os períodos encerram aos sábados. A exceção está na última janela: como a entrega é fixa em 17/11/2026 (terça-feira), a janela final termina nessa data.

| Período | Marco | Entregas |
|---|---|---|
| **01/10 – 10/10** | Fundação | Boilerplate rodando em todas as máquinas; **OpenPose e YOLOv8 validados dentro do container** (ou decisão pelo plano B); contrato de API e esquema do MongoDB fechados; contas Azure (Text Analytics); termo de consentimento; roteiro de gravação; escopo fechado com os 7 exercícios do dataset |
| **11/10 – 17/10** | Dados | Gravação dos 25 clipes e áudios; laudos sintéticos e script de seed; rotulagem manual básica; separação treino/validação/teste por participante; esqueleto do upload e do status assíncrono (API + front) |
| **18/10 – 24/10** | Módulos A | OpenPose + repetições/desvios; YOLOv8 (equipamento); transcrição local (faster-whisper) e Azure Text Analytics com dicionário de dor; telas de cadastro e upload |
| **25/10 – 31/10** | Módulos B | Dor facial (índice PSPI); dor vocal (features acústicas e NRS); telas de plano e laudo; progresso do processamento |
| **01/11 – 07/11** | Fusão e saída | Linha do tempo, score de dor, comparação com plano e laudo, classificação; relatório automático e painel de alertas ponta a ponta; **congelamento de funcionalidades em 07/11** |
| **08/11 – 14/11** | Avaliação e documentação | Métricas, exemplos de anomalias, relatório técnico, README final; roteiro, gravação e edição do vídeo |
| **15/11 – 17/11** | Vídeo e entrega | Upload do vídeo (YouTube/Vimeo, não listado), revisão final e correções; **entrega em 17/11** (repositório, relatório técnico e link do vídeo) |

**Corte de escopo (se atrasar):** primeiro sai a segmentação de repetições sofisticada e o YOLOv8 de equipamento; depois o histórico entre sessões e o SSE (fica só o polling). O núcleo inegociável é postura + dor (face e fala) + comparação com plano/laudo + alerta no painel.

## 11. Mapeamento com o edital

| Exigência do edital | Onde é atendida | Situação |
|---|---|---|
| OpenPose (postura) | RF-01 a RF-03 | Atendido |
| YOLOv8 (objetos/áreas críticas) | RF-04 | Atendido |
| Relatório automático de desvios | RF-17 | Atendido |
| Azure Speech to Text | RF-08 | **Substituído** por transcrição local por redução de custos. Requer validação com o professor |
| Azure Text Analytics (termos críticos e sentimento) | RF-09 | Atendido |
| Alterações vocais | RF-10 | Atendido |
| Anomalias em padrões de movimentação | RF-03, RF-14 | Atendido |
| Anomalias na evolução de prescrições | RF-14, RF-19 (comparação sessão a sessão com o plano) | Atendido na forma proposta. Validar com o professor |
| Alertas automáticos | RF-18 | Atendido |
| Fusão multimodal | RF-12, RF-13, RF-15 | Atendido |
| Código-fonte e relatório técnico | Repositório (boilerplate) + `docs/` | Atendido |

**Fora do escopo por decisão do grupo:** anomalias em **sinais vitais** (batimentos, pressão, oxigenação). O grupo entende que não são obrigatórias neste momento; a decisão está registrada na seção 13.

## 12. Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|:---:|:---:|---|
| Remoção do Azure Speech to Text deixa de atender a um requisito explícito do edital | Média | Alta | Validar com o professor antes da fase de módulos; manter a camada de transcrição isolada para trocar o provedor se necessário |
| Transcrição local lenta sem GPU | Média | Média | Modelo `small` ou `base`; processamento em segundo plano; cache das transcrições no MongoDB |
| OpenPose pesado em Docker e lento sem GPU | **Alta** | Alta | Validar na semana 1 dentro do container; amostragem de frames; vídeos curtos; plano B documentado (MediaPipe Pose) |
| YOLOv8 pré-treinado não reconhece faixa, bastão e halter | Alta | Média | Fine-tuning leve com os clipes do dataset; ou reduzir a detecção aos objetos reconhecíveis (colchonete, mesa); declarar a limitação |
| Build das imagens demorado e com muito disco nas máquinas do grupo | Média | Média | Modelos em volume, cache de camadas, imagem base única para o módulo de visão; definir quem hospeda a demo |
| Upload de vídeo falhando no Nginx/FastAPI (tamanho, timeout) | Média | Média | Ajustar `client_max_body_size` e timeouts desde a semana 1; limitar tamanho e duração do vídeo |
| Processamento em segundo plano perdendo estado ao reiniciar o backend | Média | Média | Persistir `status` no MongoDB e permitir reprocessar sessão; evoluir para `worker` se necessário |
| Dor facial pouco confiável (luz, ângulo, óculos) | Alta | Média | Protocolo de gravação (frontal, boa luz); tratar "sem dado"; peso menor da face na fusão |
| Falta de dados reais de dor | Alta | Alta | Encenação controlada sem risco físico + rotulagem do grupo; declarar limitação |
| Janela de gravação curta (11/10 – 17/10) para 25 clipes e áudios | Média | Alta | Começar as gravações assim que o roteiro estiver pronto; agendar voluntários com antecedência |
| Dicionário pt-BR de dor limitado | Média | Média | Lista curada pelo grupo + frases de teste variadas |
| Azure (quota, custo, chaves) | Baixa | Média | Usar apenas Text Analytics, na camada gratuita; cache das respostas no MongoDB |
| Escopo excessivo em 7 semanas (front completo + IA multimodal) | Alta | Alta | Congelamento em 07/11, lista de corte e telas mínimas primeiro |

## 13. Decisões e pendências

**Decisões tomadas**

1. Sinais vitais estão fora do escopo do MVP, confirmado.
2. O alerta terá como único canal o painel de alertas na versão inicial, sem e-mail nem Teams.
3. Todos os vídeos e áudios serão gravados pelos integrantes do grupo. Não se usam datasets externos de dor facial.
4. A demonstração será gravada em vídeo, conforme exigido pelo edital.

**Pendências**

1. Validar com o professor a substituição do Azure Speech to Text pela transcrição local (faster-whisper). O edital exige o Azure Speech to Text de forma explícita, e esse ponto ainda não foi confirmado.
2. Definir a divisão de trabalho por frente (front, API/dados, visão, áudio/Azure, fusão/regras). Será definida posteriormente.
