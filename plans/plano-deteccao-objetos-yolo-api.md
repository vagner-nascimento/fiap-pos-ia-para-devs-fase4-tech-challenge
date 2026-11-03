# Plano: detecção de objetos YOLO na análise de vídeos

## Objetivo

Integrar à análise de vídeos da API a detecção de objetos baseada no exemplo
`docs/code-examples/yolo_detect.py`, sem treinar o YOLO durante a execução da
aplicação.

Objetos esperados:

- FISIO-006: faixa elástica;
- FISIO-007: halter.

Nos demais exercícios não haverá carregamento do modelo, inferência, caixas,
percentual ou aviso visual.

## Modelo pré-treinado

1. Copiar somente o melhor modelo já treinado:
   `docs/code-examples/runs/yolo_training/two_objects/weights/best.pt`.
2. Armazenar a cópia em `backend/src/yolo/best.pt`.
3. Não executar treinamento nem incluir treinamento no fluxo da API.
4. Adicionar `ultralytics` às dependências do backend.
5. Centralizar o caminho do modelo, o limiar de confiança e o mapeamento das
   classes.

Mapeamento do modelo:

- classe `0`: `faixa_elastica`, exibida como `faixa elástica`;
- classe `1`: `halter`, exibida como `halter`.

O modelo deverá ser carregado uma vez por processador/serviço, e não uma vez
por frame.

## Cadastro dos exercícios

Atualizar o cadastro retornado por `GET /api/sessoes/exercicios` para manter o
pré-requisito do objeto:

- FISIO-001 a FISIO-005: nenhum objeto YOLO;
- FISIO-006: faixa elástica;
- FISIO-007: halter.

A configuração deverá ser baseada no exercício normalizado, e não no nome do
arquivo de vídeo. O cadastro deve distinguir o requisito textual do exercício
do objeto que será usado na detecção.

## Serviço de detecção

Criar um módulo específico para:

1. receber um frame OpenCV;
2. executar `YOLO.predict` com o limiar configurado;
3. filtrar somente a classe esperada;
4. retornar caixas, confiança e estado de detecção;
5. acumular total de frames e frames com detecção;
6. calcular o percentual final.

Percentual:

`frames com detecção válida / total de frames analisados * 100`

Falhas de carregamento do modelo, arquivo ausente ou inferência inválida
deverão ser registradas explicitamente e interromper a análise dos exercícios
que exigem objeto. Não produzir um resultado falso como se o objeto estivesse
ausente.

## Integração no pipeline

Integrar a detecção ao `VideoPoseProcessor` e à geração do vídeo anotado.

Para FISIO-006 e FISIO-007:

- executar a inferência nos frames renderizados;
- desenhar as caixas delimitadoras do objeto;
- acumular o percentual de exibição;
- incluir o resultado nos artefatos da análise;
- exibir o status no canto esquerdo inferior.

### Convivência com os recursos atuais

A detecção de objetos será uma camada adicional da anotação, sem substituir
nenhum recurso já existente. O mesmo vídeo anotado deverá continuar exibindo
simultaneamente:

- landmarks e esqueleto corporal do MediaPipe;
- alertas biomecânicos e desvios do exercício;
- métricas atuais do HUD;
- caixas delimitadoras do objeto, quando detectado;
- aviso do objeto no canto esquerdo inferior, somente para FISIO-006 e
  FISIO-007.

O frontend continuará consumindo o vídeo anotado retornado no relatório da
sessão. Portanto, landmarks, alertas e detecção de objetos aparecerão juntos
no player do frontend. Os eventos e alertas estruturados continuarão
disponíveis na timeline e no relatório, sem serem removidos ou substituídos
pelos dados do YOLO.

Para FISIO-001 a FISIO-005:

- não carregar o modelo;
- não executar inferência;
- não desenhar caixas;
- não exibir aviso;
- não incluir dados de detecção no resultado.

## Aviso visual

Adicionar uma área independente do HUD superior, no canto esquerdo inferior,
com margem proporcional à resolução e contraste suficiente.

Durante o vídeo, mostrar o estado do frame. Ao final, o aviso deverá refletir o
percentual consolidado:

- `faixa elástica: XX%`;
- `halter: XX%`.

Quando o objeto não for detectado em nenhum frame, manter:

- `faixa elástica: Não detectado`;
- `halter: Não detectado`.

Usar Pillow para preservar a renderização correta dos caracteres acentuados,
seguindo o padrão existente do `HudRenderer`.

## Resultado persistido

Adicionar os dados em `ExerciseAnalysisResult.extra`, preservando o contrato
existente e permitindo a gravação no `analysis.json` e no MongoDB:

```json
{
  "object_detection": {
    "object_name": "faixa elástica",
    "class_name": "faixa_elastica",
    "detected": true,
    "detection_percentage": 82.4,
    "total_frames": 1200,
    "frames_detected": 989,
    "confidence_threshold": 0.25
  }
}
```

Quando não houver nenhuma detecção, usar `detected: false` e
`detection_percentage: 0.0`. Para exercícios sem objeto, não incluir
`object_detection`.

## API e frontend

Verificar se o relatório de sessão precisa expor o resumo além do vídeo
anotado. Se necessário:

- adicionar um campo opcional ao `SessionReportResponse`;
- mapear os dados salvos em `extra`;
- exibir o resumo somente para FISIO-006 e FISIO-007.

Nesta etapa, a ausência do objeto não deve alterar automaticamente o score
biomecânico nem a classificação clínica.

## Testes

Adicionar testes para:

1. mapear FISIO-006 para faixa elástica;
2. mapear FISIO-007 para halter;
3. garantir que os demais exercícios não executem detecção;
4. filtrar corretamente as classes YOLO;
5. calcular percentuais de 100%, parcial e 0%;
6. gerar a mensagem `Não detectado`;
7. renderizar o aviso no canto esquerdo inferior;
8. persistir os dados no `analysis.json`;
9. falhar explicitamente quando `best.pt` estiver ausente ou inválido;
10. preservar o fluxo atual de MediaPipe, HUD, áudio, evidências e MongoDB.

Os testes devem permanecer em `backend/tests`, conforme a convenção existente.

## Validação

Executar:

```sh
cd backend
uv sync
uv run pytest tests -q
```

Validar manualmente vídeos de FISIO-006 com e sem faixa elástica, vídeos de
FISIO-007 com e sem halter e pelo menos um exercício entre FISIO-001 e
FISIO-005, confirmando que os últimos não exibem detecção nem aviso.

## Fora do escopo

- treinar ou retreinar o YOLO na aplicação;
- alterar o modelo MediaPipe Pose;
- detectar objetos nos exercícios sem pré-requisito;
- penalizar automaticamente o score biomecânico pela ausência do objeto.
