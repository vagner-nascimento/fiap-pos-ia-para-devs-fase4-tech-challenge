# Arquitetura do Sistema – Fisio Coach

**Tech Challenge · Fase 4 · Pós-Tech IA para Devs (FIAP)**  
**Versão:** 1.0 · **Data:** Outubro de 2026  
**Status:** Aprovado e em implementação

---

## 1. Visão Geral e Contexto de Negócio

O **Fisio Coach** é uma plataforma multimodal orientada por Inteligência Artificial projetada para auxiliar fisioterapeutas no monitoramento remoto e acompanhamento de sessões de exercícios de reabilitação motora.

O sistema analisa sessões gravadas em vídeo (contendo trilhas visuais e de áudio) para:
1. **Rastrear postura e biomecânica:** Extrair landmarks corporais, calcular ângulos articulares em tempo real, segmentar repetições válidas/inválidas e identificar desvios posturais específicos do exercício prescrito;
2. **Estimar dor e fadiga:** Capturar queixas verbais de dor (transcrição de áudio em pt-BR e PLN clínico) e analisar microexpressões faciais de desconforto;
3. **Fusão Multimodal e Alinhamento Clínico:** Correlacionar repetições, desvios e picos de dor em uma linha do tempo unificada, confrontando o desempenho do paciente com o laudo da lesão e a prescrição do fisioterapeuta;
4. **Geração de Evidências e Laudos:** Renderizar vídeos anotados com Head-Up Display (HUD) responsivo e gerar relatórios executivos com snapshots comprobatórios dos desvios.

---

## 2. Diagramas de Arquitetura C4

### 2.1 C4 Nível 1 – Diagrama de Contexto

O diagrama abaixo ilustra o contexto do sistema, os usuários (fisioterapeuta e paciente) e as fronteiras do sistema Fisio Coach.

```mermaid
C4Context
    title Diagrama de Contexto (C4 Nível 1) - Fisio Coach

    Person(paciente, "Paciente", "Grava o vídeo da sessão de exercícios de fisioterapia e relata queixas de dor durante os movimentos.")
    Person(fisio, "Fisioterapeuta", "Prescreve exercícios, define limites de amplitude e dor, e avalia o relatório detalhado e alertas gerados.")

    System(fisio_coach, "Fisio Coach System", "Plataforma multimodal de IA para análise postural, estimativa de dor, conformidade terapêutica e apoio à decisão clínica.")

    System_Ext(dataset_repo, "Repositório de Datasets", "Dataset sintético com 7 exercícios de referência e dezenas de variações de execução motora correta e incorreta.")
    System_Ext(azure_language, "Azure Text Analytics (Opcional)", "Serviço em nuvem de análise de sentimento e extração de entidades clínicas a partir de transcrições.")

    Rel(paciente, fisio_coach, "Envia vídeo da sessão (vídeo + áudio)", "HTTPS / Web")
    Rel(fisio, fisio_coach, "Cadastra prescrição/laudo e visualiza alertas e relatórios analíticos", "HTTPS / Web")
    Rel(fisio_coach, dataset_repo, "Lê clipes sintéticos de referência para validação e testes", "Filesystem / Docker Volume (:ro)")
    Rel(fisio_coach, azure_language, "Envia transcrições para extração avançada de menções de dor", "REST / HTTPS")
```

---

### 2.2 C4 Nível 2 – Diagrama de Containers

O sistema é modular e conteinerizado via Docker Compose, permitindo execução integral em ambiente local com suporte a aceleração em CPU:

```mermaid
C4Container
    title Diagrama de Containers (C4 Nível 2) - Fisio Coach

    Person(usuario, "Fisioterapeuta / Paciente", "Acessa a plataforma pelo navegador web.")

    Container(frontend, "Frontend SPA", "React 19, Vite, TailwindCSS / Vanilla CSS, Nginx", "Fornece interface para upload de vídeos, visualização de telemetria, player com timeline sincronizada e painel de alertas.")
    
    Container(backend, "Backend API & AI Engine", "Python 3.11, FastAPI, Uvicorn, MediaPipe Pose, OpenCV, Pillow, SciPy", "Expõe API RESTful (/api), orquestra o pipeline multimodal, processa pose, segmenta repetições, detecta desvios e renderiza vídeo anotado.")
    
    ContainerDb(mongodb, "Banco de Dados", "MongoDB 7.0", "Armazena cadastros de pacientes, planos de tratamento, laudos estruturados, resumos de sessão, eventos e telemetria temporal.")

    ContainerDb(storage, "Armazenamento de Mídias (Volume)", "Sistema de Arquivos Local (./data)", "Armazena vídeos brutos de entrada, vídeos anotados MP4, snapshots JPG de evidências e relatórios JSON.")

    Rel(usuario, frontend, "Interage com a interface", "HTTP/8080")
    Rel(frontend, backend, "Chama endpoints REST (upload, status, dados da sessão)", "HTTP/3000 (proxy reverso via Nginx)")
    Rel(backend, mongodb, "Persiste e consulta planos, laudos, sessões e telemetria", "MongoDB Wire Protocol / 27017")
    Rel(backend, storage, "Lê entradas e salva saídas (vídeos, evidências, telemetria)", "Filesystem I/O (POSIX / MediaStorage)")
    Rel(frontend, storage, "Carrega stream de vídeos anotados e imagens de evidência", "HTTP GET estático via Nginx/Backend")
```

---

### 2.3 C4 Nível 3 – Diagrama de Componentes do Backend

Detalhamento da arquitetura interna do container Backend (`backend/src/`):

```mermaid
graph TD
    subgraph "API Layer (FastAPI Controllers)"
        RouterSessions["Sessions Router<br/>/api/sessions"]
        RouterPlans["Plans Router<br/>/api/plans"]
        RouterReports["Reports Router<br/>/api/reports"]
    end

    subgraph "Config & Infrastructure"
        MediaStorage["MediaStorage<br/>(Resolução segura e isolamento de caminhos)"]
        DBConnection["MongoDB Client<br/>(Motor / PyMongo)"]
    end

    subgraph "Pose Engine (Vision & Biomechanics)"
        Processor["VideoPoseProcessor<br/>(Orquestrador do Pipeline de Vídeo)"]
        LandmarkExtractor["LandmarkExtractor<br/>(MediaPipe Pose, Sampler, Normalizer)"]
        Registry["ExerciseRegistry<br/>(Catálogo de Analisadores)"]
        BaseAnalyzer["BaseExerciseAnalyzer<br/>(Template Method: Fases, Ângulos, Repetições)"]
        Analyzers["7 Analisadores Especializados<br/>(FISIO-001 a FISIO-007)"]
        Geometry["Geometry Utilities<br/>(Ângulos 2D, Distâncias, Inclinações)"]
        RepetitionDetector["RepetitionDetector<br/>(Histerese, Interpolação, Suavização)"]
        HudRenderer["HudRenderer<br/>(Pillow + TrueType, Responsivo, UTF-8)"]
    end

    subgraph "Multimodal Fusion & Clinical Engine (Passo 2 / Planejado)"
        SpeechEngine["SpeechEngine<br/>(Faster-Whisper local pt-BR)"]
        PainTextExtractor["PainTextExtractor<br/>(Dicionário clínico + Azure Language)"]
        FacePainEngine["FacePainEngine<br/>(Action Units Faciais / PSPI)"]
        MultimodalFusion["MultimodalFusionService<br/>(Alinhamento temporal, Matriz de Risco)"]
    end

    RouterSessions --> MediaStorage
    RouterSessions --> Processor
    Processor --> LandmarkExtractor
    Processor --> Registry
    Registry --> Analyzers
    Analyzers -- herda de --> BaseAnalyzer
    BaseAnalyzer --> Geometry
    BaseAnalyzer --> RepetitionDetector
    Processor --> HudRenderer
    Processor --> MediaStorage
    Processor --> DBConnection
```

---

## 3. Pipeline de Processamento Multimodal

O diagrama de sequência a seguir descreve o fluxo ponta a ponta desde o envio do vídeo até a disponibilização do laudo consolidado:

```mermaid
sequenceDiagram
    autonumber
    actor P as Paciente / Fisioterapeuta
    participant FE as Frontend (Nginx/React)
    participant API as FastAPI Backend
    participant FS as MediaStorage (Disco)
    participant PE as Motor de Pose (MediaPipe)
    participant SE as Motor de Áudio (Whisper)
    participant MF as Fusor Multimodal & Clínico
    participant DB as MongoDB

    P->>FE: Realiza upload do vídeo da sessão (.mp4)
    FE->>API: POST /api/sessions (arquivo + metadados do plano)
    API->>FS: Salva vídeo original em data/inputs/sessions/{id}/original.mp4
    API->>DB: Registra sessão com status="enviado"
    API-->>FE: Retorna 202 Accepted {session_id, status: "enviado"}

    par Processamento de Pose e Biomecânica
        API->>PE: Executa análise visual do vídeo
        PE->>PE: Extrai landmarks corporais (30 FPS normalizados)
        PE->>PE: Determina lado ativo (auto-detecção de amplitude)
        PE->>PE: Rastreia ângulos articulares e detecta fases e repetições
        PE->>PE: Identifica desvios posturais específicos do exercício
        PE->>FS: Grava frames de evidência (.jpg) em outputs/{run_id}/pose/evidence/
        PE->>PE: Renderiza HUD responsivo (Pillow UTF-8) e gera annotated.mp4
        PE->>FS: Grava annotated.mp4, analysis.json e telemetry.json
    and Processamento de Áudio e Voz
        API->>SE: Extrai trilha sonora e transcreve fala (Whisper pt-BR)
        SE->>SE: Detecta marcadores de dor e região anatômica ("dor no joelho", "fisgada")
    end

    API->>MF: Realiza fusão temporal de Pose + Fala + Prescrição + Laudo
    MF->>MF: Classifica sessão na Matriz de Risco (Verde / Atenção / Crítico)
    MF->>DB: Atualiza sessão com resultados, scores, telemetria e status="concluido"
    
    FE->>API: Consulta status/resultado da sessão (Polling/SSE)
    API-->>FE: Retorna resumo da sessão, telemetria e links dos vídeos e evidências
    FE->>P: Exibe Player sincronizado com HUD, gráfico de ângulos e laudo clínico
```

---

## 4. Arquitetura do Motor de Visão (Pose Engine)

O motor de visão foi desenvolvido com foco em alta precisão biomecânica, desacoplamento e suporte a execução nativa em CPU.

### 4.1 Padrão Strategy para os Analisadores de Exercício

A classe base `BaseExerciseAnalyzer` fornece os algoritmos comuns de processamento de séries temporais:
- **Interpolação de gaps:** Preenchimento linear de frames onde landmarks sofreram oclusão momentânea;
- **Suavização por média móvel:** Janela temporal configurável para atenuar tremores e ruídos de detecção de alta frequência;
- **Detecção por histerese:** Transição estável entre fases do movimento (`repouso` $\rightarrow$ `concentrica` $\rightarrow$ `pico` $\rightarrow$ `excentrica` $\rightarrow$ `repouso`), evitando contagens falsas geradas por oscilações no ápice do movimento;
- **Auto-seleção de lado (`AUTO`):** Para exercícios unilaterais, o sistema avalia simultaneamente o hemicorpo direito e esquerdo, selecionando o lado ativo pela visibilidade combinada e amplitude de movimento detectada.

```mermaid
classDiagram
    class BaseExerciseAnalyzer {
        <<abstract>>
        +exercise_id: str
        +name: str
        +side: BodySide
        +target_reps: int
        +primary_joint_name: str
        +analyze(frames: list[PoseFrame]) ExerciseAnalysisResult
        #extract_primary_angle(frame, side) float*
        #check_deviations_frame(frame, side, current_angle, phase) list[DeviationEvent]*
        #check_cycle_deviations(cycle_frames, rep_number, side) list[DeviationEvent]*
        #get_reference_side(frames) BodySide
    }

    class KneeExtensionAnalyzer {
        +primary_joint_name = "angulo_joelho"
        +check_deviations_frame()
        +check_cycle_deviations()
    }
    class ShoulderPendulumAnalyzer {
        +primary_joint_name = "inclinacao_tronco"
        +check_deviations_frame()
    }
    class PelvicTiltAnalyzer {
        +primary_joint_name = "angulo_quadril"
        +check_deviations_frame()
    }
    class KneeRollsAnalyzer {
        +primary_joint_name = "inclinacao_pernas"
        +check_deviations_frame()
    }
    class ShoulderFlexionStickAnalyzer {
        +primary_joint_name = "elevacao_braco"
        +check_deviations_frame()
    }
    class ShoulderAbductionBandAnalyzer {
        +primary_joint_name = "abducao_ombro"
        +check_deviations_frame()
    }
    class ElbowFlexionAnalyzer {
        +primary_joint_name = "angulo_cotovelo"
        +check_deviations_frame()
    }

    BaseExerciseAnalyzer <|-- KneeExtensionAnalyzer : FISIO-001
    BaseExerciseAnalyzer <|-- ShoulderPendulumAnalyzer : FISIO-002
    BaseExerciseAnalyzer <|-- PelvicTiltAnalyzer : FISIO-003
    BaseExerciseAnalyzer <|-- KneeRollsAnalyzer : FISIO-004
    BaseExerciseAnalyzer <|-- ShoulderFlexionStickAnalyzer : FISIO-005
    BaseExerciseAnalyzer <|-- ShoulderAbductionBandAnalyzer : FISIO-006
    BaseExerciseAnalyzer <|-- ElbowFlexionAnalyzer : FISIO-007
```

### 4.2 Tabela de Cobertura dos 7 Exercícios do Dataset Sintético

| Código | Exercício | Lado Avaliado | Articulação Primária | Desvios Monitorados |
|---|---|---|---|---|
| **FISIO-001** | Extensão de joelho sentado | Ativo (`AUTO`/dir/esq) | Ângulo do Joelho ($180^\circ \rightarrow 90^\circ$) | `amplitude_reduzida`, `inclinacao_tronco`, `movimento_muito_rapido` |
| **FISIO-002** | Pêndulo de ombro de Codman | Ativo (`AUTO`/dir/esq) | Inclinação do Tronco e Ângulo do Cotovelo | `postura_ereta_inadequada`, `cotovelo_flexionado`, `braco_estatico` |
| **FISIO-003** | Inclinação pélvica deitado | Bilateral (`BOTH`) | Ângulo do Quadril e Joelhos | `pernas_estendidas_inadequadas`, `amplitude_insuficiente` |
| **FISIO-004** | Rotação de joelhos deitado | Bilateral (`BOTH`) | Ângulo do Fêmur vs Vertical | `espirro_lombar_compensatorio`, `amplitude_assimetrica` |
| **FISIO-005** | Flexão de ombro com bastão | Bilateral (`BOTH`) | Elevação do Braço vs Tronco | `assimetria_bracos`, `compensacao_lombar_hiperlordose` |
| **FISIO-006** | Abdução de ombro com elástico | Ativo (`AUTO`/dir/esq) | Abdução do Braço vs Tronco | `inclinacao_tronco`, `faixa_fora_de_quadro`, `amplitude_reduzida` |
| **FISIO-007** | Flexão de cotovelo com halter | Ativo (`AUTO`/dir/esq) | Ângulo do Cotovelo ($160^\circ \rightarrow 50^\circ$) | `balanco_tronco`, `amplitude_incompleta`, `cotovelo_afastado_corpo` |

---

## 5. Arquitetura de Dados e Armazenamento

A arquitetura estabelece uma separação estrita entre **arquivos binários de mídia pesada** (armazenados em disco com controle rígido de path traversal) e **estruturas de metadados relacionais/documentais** (persistidas no MongoDB):

```
RAIZ_DO_REPOSITORIO/
├── data/                                 # [MEDIA_ROOT] Isolado fora do Git
│   ├── inputs/
│   │   └── sessions/
│   │       └── {session_id}/
│   │           └── original.mp4         # Vídeo bruto enviado pelo paciente
│   └── outputs/
│       └── {run_id}/
│           └── pose/
│               ├── annotated.mp4        # Vídeo renderizado com esqueleto e HUD
│               ├── analysis.json        # Resumo analítico, repetições e desvios
│               ├── telemetry.json       # Série temporal frame a frame dos ângulos
│               └── evidence/
│                   ├── rep01_pico.jpg   # Snapshot da repetição
│                   └── rep01_desvio.jpg # Snapshot comprobatório do desvio
```

### Coleções do MongoDB (`fiap-pos-ia-db`)

1. **`pacientes`:** Cadastro do paciente, histórico clínico e lesões diagnosticadas.
2. **`planos`:** Prescrição do fisioterapeuta (exercício, repetições alvo, faixa de ângulo esperada, limite de dor tolerável).
3. **`laudos`:** Diagnóstico médico ortopédico estruturado com restrições de movimento e amplitudes máximas permitidas.
4. **`sessoes`:** Registro da execução com timestamps, status do processamento, classificação de risco (`verde`, `atencao`, `critico`), caminhos relativos das mídias em `data/` e métricas consolidadas.
5. **`telemetria`:** Registro das séries temporais de ângulos articulares para geração dos gráficos de evolução temporal.
6. **`alertas`:** Notificações direcionadas ao painel do fisioterapeuta sobre desvios críticos ou relatos de dor acima do limiar.

---

## 6. Requisitos Não Funcionais e Decisões de Engenharia

| Requisito | Solução Arquitetural | Impacto / Benefício |
|---|---|---|
| **Execução em CPU (sem GPU)** | Adoção do MediaPipe Pose com modelo BlazePose leve | Permite rodar o pipeline completo em qualquer computador convencional ou container Docker sem custos de instâncias com GPU na nuvem. |
| **Integridade de Caracteres no Vídeo** | Renderização do HUD via Pillow (`ImageDraw` com fonte TrueType UTF-8) | Exibe acentuação correta em português (`ã`, `á`, `ç`) e notações científicas (`°`, `≥`), eliminando interrogações (`?`) típicas do OpenCV Hershey. |
| **HUD Responsivo e Dinâmico** | Cálculo proporcional baseado na largura e altura do frame | Garante que vídeos verticais (típicos de gravações de smartphone) e horizontais exibam caixas de alerta perfeitamente enquadradas sem cortes de texto. |
| **Segurança e Privacidade (LGPD)** | Dados em `data/` isolados no `.gitignore` e caminhos validados por regex | Mídias sensíveis de pacientes não sobem ao Git; sanitização impede ataques de *Path Traversal* (`../`). |
| **Portabilidade Host/Container** | `MediaStorage` com fallback dinâmico absoluto | O sistema resolve o caminho correto tanto executado localmente via CLI quanto encapsulado no container Docker com volume mapeado. |
