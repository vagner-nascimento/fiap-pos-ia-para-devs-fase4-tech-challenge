# Plano: Motor de Detecção de Pose e Movimento (MediaPipe) — Passo 1

**Escopo:** RF-01, RF-02 e RF-03 do PRD v1.2, para os 7 casos `FISIO-001` a `FISIO-007`.
**Fora deste passo:** gravação no MongoDB (Passo 2). O Passo 1 já deixa o contrato pronto para ela (ver seção 6).

---

## 1. Decisões de arquitetura

| Tema | Decisão |
|---|---|
| Biblioteca de detecção | MediaPipe Pose (33 landmarks), plano B do PRD para o OpenPose |
| Lado do exercício | Nunca fixo. `BodySide`: `RIGHT`, `LEFT` ou `AUTO` (ver seção 2) |
| Padrão de código | Strategy: um analisador por exercício sobre uma base comum |
| Mídias | Fora do Git, em `data/`, montado como volume no container do backend |
| Caminhos | Sempre **relativos a `MEDIA_ROOT`**, para funcionar igual no host e no Docker |
| Execução | Biblioteca em `services/pose/` usada por um CLI agora e pela API/worker depois |

## 2. Lado dinâmico (`BodySide`)

1. **Informado:** `side` vindo da prescrição (`direito`/`esquerdo`) ou do parâmetro da chamada.
2. **`AUTO`** (padrão se omitido): o analisador acumula os primeiros ciclos de ambos os lados e escolhe o lado ativo por **visibilidade dos landmarks** e **amplitude angular**. O lado escolhido fica em `side_evaluated` no resultado.
3. **Bilaterais** (FISIO-003, 004 e 005): avaliam os dois lados juntos.

`JointMapper` resolve os índices do MediaPipe a partir do lado:

| Articulação | Direito | Esquerdo |
|---|:---:|:---:|
| Ombro | 12 | 11 |
| Cotovelo | 14 | 13 |
| Punho | 16 | 15 |
| Quadril | 24 | 23 |
| Joelho | 26 | 25 |
| Tornozelo | 28 | 27 |

## 3. Estrutura de diretórios

### 3.1 Código (`backend/`)

```
backend/
├── pyproject.toml                  # [MOD] + mediapipe, opencv-python-headless, numpy, scipy
├── Dockerfile                      # [MOD] libs de sistema para OpenCV/MediaPipe
├── .env.example                    # [MOD] + MEDIA_ROOT, DATASET_ROOT
├── src/
│   ├── config/media_paths.py       # [NEW] MediaStorage: resolve todos os caminhos de mídia
│   ├── services/pose/
│   │   ├── geometry.py             # ângulos 2D, inclinação do tronco, distâncias
│   │   ├── joint_mapper.py         # BodySide + índices por lado
│   │   ├── models.py               # Pydantic: Repetition, Deviation, AnalysisResult
│   │   ├── base_analyzer.py        # FSM de repetições + suavização
│   │   ├── registry.py             # case_id/exercise_id -> analisador
│   │   ├── video_processor.py      # leitura, MediaPipe, HUD, evidências
│   │   ├── result_writer.py        # grava analysis.json, telemetry.json, mídias
│   │   └── analyzers/fisio_00{1..7}_*.py
│   └── cli/analyze_video.py        # [NEW] execução local sobre os vídeos do dataset
└── tests/unit/pose/                # geometry, FSM, analisadores, MediaStorage
```

### 3.2 Mídias (raiz do repositório, fora do Git)

```
data/                                       # MEDIA_ROOT (host) -> /app/data (container)
├── inputs/
│   ├── sessions/
│   │   └── {session_id}/
│   │       └── original.mp4                # upload do paciente (POST /api/sessoes, futuro)
│   └── dataset/                            # opcional: cópia/symlink dos clipes de referência
│       └── FISIO-001/FISIO-001-correto.mp4
└── outputs/
    └── {run_id}/                           # run_id = session_id (API) ou {case}-{clip}-{AAAAMMDD-HHMMSS} (CLI)
        └── pose/
            ├── annotated.mp4               # vídeo com esqueleto e HUD
            ├── analysis.json               # resumo, repetições e desvios
            ├── telemetry.json              # série temporal de ângulos
            └── evidence/
                ├── rep02_amplitude_reduzida.jpg
                └── rep03_compensacao_tronco.jpg
```

- `outputs/{run_id}/` é pensado para receber depois `face/`, `audio/` e `report/` (demais módulos do PRD), sem reorganizar nada.
- O repositório de datasets (`fiap-pos-ia-para-devs-fase4-tech-challenge-datasets`) continua separado. `DATASET_ROOT` aponta para ele e é montado **somente leitura**, evitando copiar ~15 MB por clipe.
- Manter `.gitkeep` em `data/inputs/` e `data/outputs/` e ignorar o conteúdo no `.gitignore` (PRD: `data/` fora do Git, dados sensíveis).

### 3.3 Configuração

```diff
# backend/.env.example
+MEDIA_ROOT=./data
+DATASET_ROOT=../../fiap-pos-ia-para-devs-fase4-tech-challenge-datasets
```

```diff
# docker-compose.yaml (serviço backend)
+    environment:
+      MEDIA_ROOT: /app/data
+      DATASET_ROOT: /app/datasets
+    volumes:
+      - ./data:/app/data
+      - ../fiap-pos-ia-para-devs-fase4-tech-challenge-datasets:/app/datasets:ro
```

```diff
# .gitignore (raiz)
+data/inputs/*
+data/outputs/*
+!data/**/.gitkeep
```

> [!NOTE]
> O mount do dataset usa caminho relativo ao repositório irmão. Se o grupo mantiver a pasta em outro lugar, basta ajustar essa linha ou usar variável no `.env`. A decisão está em **Perguntas em aberto**.

### 3.4 `MediaStorage` (contrato dos caminhos)

```python
class MediaStorage:
    def __init__(self, media_root: Path, dataset_root: Path | None): ...
    def session_input(self, session_id: str) -> Path        # inputs/sessions/{id}/original.mp4
    def dataset_clip(self, case_id: str, filename: str) -> Path
    def pose_output_dir(self, run_id: str) -> Path           # outputs/{run_id}/pose (cria se não existir)
    def annotated_video(self, run_id) -> Path
    def analysis_json(self, run_id) -> Path
    def telemetry_json(self, run_id) -> Path
    def evidence_frame(self, run_id, name: str) -> Path
    def relative(self, path: Path) -> str                    # valor que será guardado no banco
```

Nenhum outro módulo monta caminhos manualmente.

## 4. Mapeamento dos 7 exercícios

| Caso | Exercício | Lado | Desvios detectados (labels do dataset) |
|---|---|---|---|
| FISIO-001 | Extensão de joelho sentado | ativo | `amplitude_reduzida`, `compensacao_tronco`, `ritmo_acelerado` |
| FISIO-002 | Pendular do ombro | ativo (pendente) | `elevacao_ativa`, `amplitude_excessiva`, `braco_rigido` |
| FISIO-003 | Inclinação pélvica | bilateral | `elevacao_pelve`, `movimento_abrupto`, contagem divergente da meta |
| FISIO-004 | Rotação dos joelhos | bilateral | `joelhos_separados`, `ombros_elevados`, `retorno_incompleto` |
| FISIO-005 | Flexão de ombro com bastão | bilateral | assimetria de braços, `pegada_alterada` |
| FISIO-006 | Abdução com faixa | ativo | `inclinacao_tronco`, `faixa_fora_de_quadro` (baixa visibilidade) |
| FISIO-007 | Flexão de cotovelo com halter | ativo | `balanco_tronco`, `retorno_incompleto`, cotovelo deslocado |

Limiares ficam em configuração por exercício (não espalhados no código) e são calibrados com os clipes reais. A prescrição (`prescricao.json`) fornece repetições alvo, duração e lado.

## 5. Saídas do processamento

1. **Vídeo anotado** (`annotated.mp4`): esqueleto colorido por status, HUD com repetições, fase, ângulos e alerta.
2. **`analysis.json`**: `session_summary`, `repetitions[]`, `deviations[]` (com `evidence_frame_path` relativo).
3. **`telemetry.json`**: série temporal de ângulos (5 a 10 amostras/s).
4. **`evidence/*.jpg`**: um frame por desvio, no instante do pico.

Regras: rosto ou membro fora de quadro vira "sem dado" (nunca "correto"), e a limitação é declarada em `analysis.json`.

## 6. Preparação para o Passo 2 (MongoDB)

Para a persistência entrar sem retrabalho:

- `AnalysisResult` (Pydantic) já espelha os campos de `sessoes` e `eventos` do PRD (seção 6.4).
- Todos os caminhos no resultado são relativos a `MEDIA_ROOT`.
- O pipeline recebe um `ResultSink` (interface). No Passo 1 a implementação é `FileResultSink` (grava JSON/mídias). No Passo 2 entra `MongoResultSink` sem alterar o processador.

## 7. Etapas de implementação

1. **Fundação:** dependências, `MediaStorage`, `.gitignore`, `.env.example`, volumes no Compose, ajuste do Dockerfile.
2. **Núcleo:** `geometry`, `joint_mapper` (`BodySide` + `AUTO`), `models`, `base_analyzer` (FSM + suavização).
3. **Analisadores:** FISIO-001 primeiro (já há 4 clipes), depois 007, 006, 002, 005, 003 e 004.
4. **Processador de vídeo:** MediaPipe, HUD, evidências, `FileResultSink`.
5. **CLI e validação:** `python -m cli.analyze_video --case FISIO-001 --clip FISIO-001-correto.mp4 --side auto`.
6. **Testes e relatório de validação** contra `roteiros_e_rotulos.json`.

## 8. Verificação

**Automatizada**
```bash
cd backend && uv run pytest tests/unit/pose -v
```
- Ângulos e inclinações com valores conhecidos.
- FSM com sinais sintéticos (contagem, retorno incompleto).
- `AUTO` escolhe o lado correto em landmarks sintéticos espelhados.
- `MediaStorage` não permite sair de `MEDIA_ROOT`.

**Com vídeos reais (dataset)**
- `FISIO-001-correto.mp4`: 5 repetições, sem desvios.
- `...-extensao-parcial.mp4`: `amplitude_reduzida`.
- `...-inclinacao-tronco.mp4`: `compensacao_tronco`.
- `...-velocidade-irregular.mp4`: `ritmo_acelerado`.
- Meta do PRD: erro na contagem de repetições ≤ 10%.

**Manual:** abrir `annotated.mp4` e conferir esqueleto, HUD e evidências em `data/outputs/{run_id}/pose/`.

## 9. Decisões

- **Dataset:** lido direto do repositório irmão via `DATASET_ROOT`, montado somente leitura (opção A). Os clipes servem apenas para desenvolvimento, calibração, validação e demonstração. Pode ser revisto depois.
- **Localização de `data/`:** raiz do repositório.
- **Armazenamento de mídias:** em disco, por enquanto. GridFS pode ser reavaliado no Passo 2.

Sem perguntas em aberto.
