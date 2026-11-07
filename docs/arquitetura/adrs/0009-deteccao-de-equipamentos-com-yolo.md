# ADR 0009: Detecção de Equipamentos com YOLO em CPU

- **Status:** Aprovado
- **Data:** Novembro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

## 1. Contexto

Os exercícios FISIO-006 (abdução de ombro) e FISIO-007 (flexão de cotovelo)
dependem, respectivamente, de faixa elástica e halter. A análise postural com
MediaPipe Pose fornece landmarks da pessoa, mas não identifica objetos e não
permite informar se o equipamento prescrito está presente no vídeo.

Era necessário acrescentar essa informação sem substituir os landmarks, os
alertas biomecânicos ou o HUD já existentes. A detecção também precisava rodar
no mesmo ambiente CPU-only usado pelo backend.

## 2. Decisão

Adotamos **YOLO**, seguindo o exemplo de `docs/code-examples/yolo_detect.py`,
como detector de objetos. O modelo é executado somente quando o exercício
cadastrado exige equipamento:

| Exercício | Classe detectada |
|---|---|
| FISIO-006 | `faixa_elastica` |
| FISIO-007 | `halter` |

O detector é integrado ao `VideoPoseProcessor` e compartilha cada frame com o
pipeline de pose. Assim, o vídeo anotado preserva landmarks, esqueleto,
alertas, telemetria e acrescenta caixa/status do equipamento. O relatório
também registra os percentuais de frames não detectados, parcialmente
detectados e totalmente detectados; exercícios sem equipamento exibem
`Nenhum` e não executam YOLO.

O treinamento não acontece na API. O melhor checkpoint é treinado fora da
aplicação e salvo em `backend/src/yolo/best.pt`, que é carregado apenas para
inferência. A configuração usa `device="cpu"` e as dependências PyTorch/
Torchvision CPU-only, evitando a instalação dos runtimes CUDA e dos pacotes
NVIDIA.

## 3. Treinamento, Métricas e Limitações

O checkpoint usado nesta demonstração foi treinado fora da API a partir do script [`docs/code-examples/yolo_training.py`](../../code-examples/yolo_training.py), utilizando o dataset rotulado em [`docs/code-examples/yolo_dataset/`](../../code-examples/yolo_dataset) e registrando os artefatos de execução em [`docs/code-examples/runs/yolo_training/two_objects/`](../../code-examples/runs/yolo_training/two_objects). Os pesos finais foram versionados em [`backend/src/yolo/best.pt`](../../../backend/src/yolo/best.pt) exclusivamente para inferência em CPU.

### Resumo do Dataset e Hiperparâmetros de Treinamento (`args.yaml`)

| Parâmetro | Valor Utilizado |
|---|---|
| **Modelo Base** | `yolo11n.pt` (Ultralytics YOLO11 Nano, pré-treinado) |
| **Classes (`2`)** | `0: faixa_elastica` (FISIO-006) · `1: halter` (FISIO-007) |
| **Dataset Anotado** | **23 imagens** rotuladas no formato YOLO (`19` treino / `4` validação, `val_fraction=0.2`, `seed=42`) |
| **Distribuição por Classe** | Treino: `9` `faixa_elastica` + `10` `halter` · Validação: `2` `faixa_elastica` + `2` `halter` |
| **Épocas / Resolução / Batch** | `epochs=100` · `imgsz=640` · `batch=2` |
| **Otimizador e Taxa de Aprendizado** | `optimizer=auto` · `lr0=0.01` · `lrf=0.01` · `warmup_epochs=3.0` |
| **Data Augmentation** | `mosaic=1.0`, `fliplr=0.5`, `auto_augment=randaugment`, `erasing=0.4` |
| **Tempo Total de Treinamento** | `188,8 s` (~3,1 minutos para 100 épocas) |

### Métricas de Validação Obtidas (`results.csv`)

| Marco do Treinamento | Precision (`B`) | Recall (`B`) | mAP50 (`B`) | mAP50-95 (`B`) | `val/box_loss` | `val/cls_loss` |
|---|---:|---:|---:|---:|---:|---:|
| **Época 1 (Início)** | 0,31% | 50,00% | 2,12% | 0,69% | 1,5431 | 5,9862 |
| **Época 49 (Convergência Intermediária)** | 72,27% | 67,18% | 66,17% | 44,14% | 1,8348 | 1,9582 |
| **Época 68 (Pico de mAP50)** | 61,50% | 73,16% | **68,34%** | 40,14% | 1,9154 | 1,5203 |
| **Época 74 (Pico de Precisão)** | **93,90%** | 50,00% | 67,64% | 40,98% | 2,1569 | 1,5057 |
| **Épocas 93–96 (Melhor mAP50-95 / `best.pt`)** | **76,36%** | **75,00%** | **67,60%** | **44,97%** | 2,0942 | 1,2435 |
| **Época 100 (Final)** | 79,12% | 75,00% | 67,60% | 42,48% | 2,0702 | 1,2158 |

Esse conjunto é suficiente para demonstrar o fluxo nos vídeos do projeto (com **76,36% de precisão**, **75,00% de recall** e **67,60% de mAP50** no checkpoint selecionado), mas não caracteriza um modelo pronto para produção clínica generalizada. Em um projeto real, o treinamento deveria usar uma base muito maior e diversa, com exemplos dos objetos em diferentes distâncias, ângulos, cores, iluminações, oclusões e tamanhos, separando conjuntos de treino, validação e teste por participante.

## 4. Alternativas consideradas

1. **MediaPipe Object Detector:** descartado porque adicionaria um modelo e
   um contrato de detecção genérico sem aproveitar o treinamento específico
   das classes do projeto; o exemplo e os pesos YOLO já atendiam diretamente
   ao caso de faixa elástica e halter.
2. **Classificação manual ou por regras de cor:** descartada por ser frágil a
   iluminação, escala, posição e aparência do equipamento.
3. **Treinamento dentro da aplicação:** descartado por aumentar o tempo,
   consumo de recursos e complexidade operacional da API.

## 5. Consequências

### Positivas

- Mantém a análise de pose e a detecção de equipamento no mesmo vídeo;
- Permite feedback por frame e resumo percentual no relatório;
- Executa em CPU, sem exigir GPU ou serviços externos;
- Restringe custo de inferência aos dois exercícios que possuem equipamento.

### Negativas / Mitigações

- O modelo pequeno da demonstração pode falhar fora dos cenários representados;
  a limitação é explicitada no relatório e deve ser resolvida com dataset real
  maior antes de qualquer uso clínico;
- Inferência adicional aumenta o tempo de processamento dos vídeos FISIO-006 e
  FISIO-007; os demais exercícios permanecem sem esse custo.
