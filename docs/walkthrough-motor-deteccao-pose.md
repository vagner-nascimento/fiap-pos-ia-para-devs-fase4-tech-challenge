# Walkthrough: Motor de Detecção de Pose e Movimento com MediaPipe (Passo 1)

Concluímos com sucesso a implementação do **Motor de Detecção de Movimentos e Desvios Posturais com MediaPipe Pose** para o projeto **Fisio Coach**, atendendo aos requisitos funcionais **RF-01, RF-02 e RF-03** do PRD e cobrindo todos os **7 exercícios** do dataset sintético (`FISIO-001` a `FISIO-007`).

---

## 1. O Que Foi Entregue

### Arquitetura & Infraestrutura de Mídia
- `MediaStorage` (`backend/src/config/media_paths.py`): centraliza a resolução de caminhos, garantindo segurança contra *path traversal* e gerando caminhos relativos prontos para o banco de dados.
- Diretórios de mídia estruturados fora do Git (`data/inputs/` e `data/outputs/`) com `.gitkeep`.
- `docker-compose.yaml` e `Dockerfile` configurados com volumes (`/app/data` e `/app/datasets:ro`) e bibliotecas de sistema (`libgl1`, `libglib2.0-0`).

### Núcleo de Visão Computacional (MediaPipe)
- `geometry.py`: Ângulos 2D, distâncias euclidianas e inclinações em pixels sem distorções de aspecto.
- `joint_mapper.py`: Resolução dinâmica de lado (`BodySide.RIGHT`, `LEFT` ou `AUTO`), eliminando qualquer amarração com lado fixo.
- `models.py`: Modelos Pydantic para `SessionSummary`, `RepetitionEvent`, `DeviationEvent`, `TelemetryPoint` e `ExerciseAnalysisResult`.
- `repetitions.py`: Suavização de sinal, interpolação de lacunas e detector de repetições com histerese (registra repetições parciais para apontar desvios de amplitude).
- `base_analyzer.py`: Estrutura Strategy base com auto-detecção de lado ativo (baseada em amplitude x visibilidade de landmarks) e fases do movimento (`repouso`, `concentrica`, `pico`, `excentrica`).
- `landmark_extractor.py`: Extração via MediaPipe com amostragem inteligente de FPS (`max_fps=30.0` e `stride`) para alta performance em vídeos gravados a altas taxas (como 120fps).

### Cobertura dos 7 Exercícios (`registry.py`)
1. **FISIO-001 (`KneeExtensionAnalyzer`)**: Extensão de joelho sentado; desvios de `amplitude_reduzida`, `compensacao_tronco` e `ritmo_acelerado`.
2. **FISIO-002 (`ShoulderPendulumAnalyzer`)**: Exercício pendular do ombro; desvios de `elevacao_ativa`, `amplitude_excessiva` e `braco_rigido`.
3. **FISIO-003 (`PelvicTiltAnalyzer`)**: Inclinação pélvica em decúbito dorsal; desvios de `elevacao_pelve` (ponte) e `movimento_abrupto`.
4. **FISIO-004 (`KneeRollsAnalyzer`)**: Rotação controlada dos joelhos em decúbito; desvios de `joelhos_separados`, `ombros_elevados` e `retorno_incompleto`.
5. **FISIO-005 (`ShoulderFlexionStickAnalyzer`)**: Flexão bilateral de ombro com bastão; desvios de assimetria (`objeto_nao_utilizado`) e `pegada_alterada`.
6. **FISIO-006 (`ShoulderAbductionBandAnalyzer`)**: Abdução de ombro com faixa elástica; desvios de `inclinacao_tronco`, `amplitude_reduzida` e `faixa_fora_de_quadro`.
7. **FISIO-007 (`ElbowFlexionAnalyzer`)**: Flexão de cotovelo com halter; desvios de `balanco_tronco`, `retorno_incompleto` e `amplitude_reduzida`.

### Renderizador & CLI
- `video_processor.py`: Gera o vídeo anotado `annotated.mp4` com esqueleto MediaPipe desenhado, HUD superior com métricas e banners de alerta em tempo real, além de salvar os snapshots `.jpg` de cada desvio na pasta `evidence/`.
- `analyze_video.py`: CLI executável para rodar a análise diretamente em qualquer vídeo via terminal.

---

## 2. Validação & Testes

### 2.1 Testes Unitários Automatizados
Execução de toda a suíte com pytest:
```bash
uv run pytest tests -q
# 85 passed
```
Foram cobertos:
- `test_media_paths.py`: 15 testes de segurança e resolução de caminhos.
- `test_geometry.py`: 14 testes geométricos.
- `test_joint_mapper.py`: 8 testes de resolução de lados dinâmicos.
- `test_repetitions.py`: 11 testes de FSM e tratamento de sinal.
- `test_base_analyzer.py`: 11 testes da base com auto-detecção de lado e tolerância a frames sem pose.
- `test_knee_extension.py`: 12 testes de FISIO-001 com sinais sintéticos.
- `test_all_analyzers.py`: 8 testes de instanciação e suporte dos 7 exercícios.
- `test_video_processor.py`: 1 teste end-to-end de renderização e criação de arquivos.

### 2.2 Teste Real Ponta a Ponta via CLI
Execução no vídeo `FISIO-001-extensao-parcial.mp4` (2.374 frames gravados a 120fps):
```bash
PYTHONPATH=src uv run python -m cli.analyze_video \
  --video ../../fiap-pos-ia-para-devs-fase4-tech-challenge-datasets/FISIO-001/FISIO-001-extensao-parcial.mp4 \
  --case FISIO-001 \
  --side auto \
  --target-reps 5 \
  --run-id demo_extensao_parcial
```
**Resultado Obtido:**
- **Tempo de processamento:** 56.1 segundos (atende com folga à meta de desempenho do PRD de processar vídeo sem GPU).
- **Auto-detecção de lado:** elegeu corretamente o lado `direito`.
- **Contagem de repetições:** 6 repetições detectadas.
- **Detecção de desvios:** identificou `amplitude_reduzida` em todas as 6 repetições (extensão entre 137° e 149°, contra ≥ 150° esperado).
- **Artefatos gerados em disco:**
  - `analysis.json`
  - `telemetry.json`
  - `annotated.mp4`
  - `evidence/rep01_amplitude_reduzida.jpg` a `rep06_amplitude_reduzida.jpg` (6 snapshots capturados no instante de pico).
