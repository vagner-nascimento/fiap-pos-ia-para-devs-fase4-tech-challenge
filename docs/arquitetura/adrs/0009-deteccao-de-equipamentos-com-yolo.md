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

## 3. Treinamento e limitações

O checkpoint usado nesta demonstração foi obtido a partir de um conjunto
pequeno e específico para as duas classes. Os pesos são copiados para a pasta
`backend/src/yolo` e versionados como artefato de inferência; a aplicação não
possui fluxo de treinamento, fine-tuning ou atualização automática do modelo.

Esse conjunto é suficiente para demonstrar o fluxo, mas não caracteriza um
modelo pronto para produção. Em um projeto real, o treinamento deveria usar
uma base muito maior e diversa, com exemplos dos objetos em diferentes
distâncias, ângulos, cores, iluminações, oclusões e tamanhos. Também seria
necessário separar conjuntos de treino, validação e teste e acompanhar
precisão, recall e falsos positivos por cenário.

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
