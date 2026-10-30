# Resumo de Progresso e Estado Atual — Motor de Detecção de Pose (MediaPipe)

**Data/Hora do Handover:** 29/10/2026 (atualizado)  
**Documento de Arquitetura Principal:** `docs/arquitetura/plano-motor-deteccao-pose-mediapipe.md`

---

## 1. O Que Já Foi Implementado e Testado

### Etapa 1: Fundação & Infraestrutura de Mídia (Concluída)
- **`MediaStorage` (`backend/src/config/media_paths.py`):** Ponto único para caminhos de entrada e saída, impedindo *path traversal* e garantindo caminhos relativos para persistência.
- **Estrutura de Pastas:** `data/inputs/` e `data/outputs/` criados com `.gitkeep`.
- **Gitignore & Ambientes:** `.gitignore` ignora dados sensíveis de `data/`; `.env.example` atualizado com `MEDIA_ROOT=../data` e `DATASET_ROOT`.
- **Docker Compose:** Volumes `./data:/app/data` e `../fiap-pos-ia-para-devs-fase4-tech-challenge-datasets:/app/datasets:ro` configurados.
- **Dockerfile:** `libgl1` e `libglib2.0-0` adicionados para OpenCV/MediaPipe em imagem slim.
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

---

## 2. Próximos Passos Imediatos

1. Implementar os analisadores restantes da Etapa 3:
   - **FISIO-002:** `ShoulderPendulumAnalyzer` (exercício pendular de ombro, desvios de elevação ativa, amplitude excessiva e braço rígido).
   - **FISIO-003:** `PelvicTiltAnalyzer` (inclinação pélvica em decúbito dorsal, elevação da pelve/ponte, movimento abrupto).
   - **FISIO-004:** `KneeRollsAnalyzer` (rotação de joelhos em decúbito, joelhos separados, ombros elevados, retorno incompleto).
   - **FISIO-005:** `ShoulderFlexionStickAnalyzer` (flexão de ombros com bastão bilateral, assimetria, pegada alterada).
   - **FISIO-006:** `ShoulderAbductionBandAnalyzer` (abdução de ombro com faixa elástica, inclinação do tronco, faixa fora de quadro).
   - **FISIO-007:** `ElbowFlexionDumbbellAnalyzer` (flexão de cotovelo com halter, balanço de tronco, retorno incompleto).
2. Adicionar os testes unitários de cada exercício em `backend/tests/unit/pose/`.
3. Etapa 4: Implementar o `VideoPoseProcessor` e `result_writer.py` (renderização de esqueleto no vídeo, HUD visual e salvamento de snapshots de evidência).
4. Etapa 5: CLI executável (`backend/src/cli/analyze_video.py`).
