# Plano de implementação — exercícios FISIO-001, 002, 006 e 007

## 1. Objetivo e escopo

Integrar, validar e disponibilizar quatro exercícios do dataset sintético no fluxo
completo de análise de vídeo:

| Código | Exercício | Lado/metadado principal | Requisitos particulares |
|---|---|---|---|
| FISIO-001 | Extensão de joelho sentado | Direito | Amplitude, estabilidade do tronco e ritmo |
| FISIO-002 | Exercício pendular do ombro | Esquerdo | Braço relaxado, oscilação suave e apoio |
| FISIO-006 | Abdução de ombro com faixa elástica | Direito | Inclinação do tronco, amplitude e visibilidade da mão/faixa |
| FISIO-007 | Flexão de cotovelo com halter leve | Direito | Balanço do tronco, retorno e amplitude |

O trabalho futuro deve cobrir backend, persistência, API, catálogo de clipes,
frontend quando necessário e testes. Este documento é somente o plano; não
implementar as alterações nesta etapa.

## 2. Diagnóstico do fluxo existente

### 2.1 Onde as repetições são geradas

1. [`repetitions.py`](../backend/src/services/pose/repetitions.py) contém a
   `RepetitionDetector`, uma máquina de estados com histerese sobre o sinal de
   progresso normalizado. Ela aplica `enter`, `exit`, `min_peak` e
   `min_duration`, descarta excursões insuficientes e mantém repetições parciais
   que ultrapassam o pico mínimo.
2. [`base_analyzer.py`](../backend/src/services/pose/base_analyzer.py) calcula
   métricas por frame, suaviza/interpola os sinais, converte-os em progresso,
   executa o detector e chama `_build_repetitions`.
3. `_build_repetitions` transforma cada `RawRepetition` em `RepetitionEvent`,
   incluindo início, pico, fim, duração, ângulo/métrica de pico, progresso,
   conclusão, validade e nomes dos desvios associados.
4. O mesmo arquivo monta `SessionSummary`, com contagem detectada, válida,
   inválida, alvo, score de conformidade, fps e limitações.

### 2.2 Onde os desvios de postura são gerados

Cada estratégia concreta implementa `detect_deviations(ctx)` e usa
`ctx.make_deviation(...)` da classe base para produzir `DeviationEvent`.
O evento contém tipo, severidade, repetição, intervalo temporal, frames inicial
e final, frame de evidência e descrição.

Para os quatro casos:

- [`fisio_001_knee_extension.py`](../backend/src/services/pose/analyzers/fisio_001_knee_extension.py):
  amplitude reduzida, inclinação/compensação do tronco e ritmo/velocidade,
  conforme os limiares da configuração da estratégia.
- [`fisio_002_shoulder_pendulum.py`](../backend/src/services/pose/analyzers/fisio_002_shoulder_pendulum.py):
  amplitude pendular excessiva, braço rígido e elevação ativa do ombro.
- [`fisio_006_shoulder_abduction.py`](../backend/src/services/pose/analyzers/fisio_006_shoulder_abduction.py):
  amplitude reduzida, inclinação lateral compensatória e baixa visibilidade
  representada por `faixa_fora_de_quadro`.
- [`fisio_007_elbow_flexion.py`](../backend/src/services/pose/analyzers/fisio_007_elbow_flexion.py):
  amplitude reduzida, balanço do tronco e retorno incompleto.

### 2.3 Onde as evidências visuais e snapshots são gerados

1. [`video_processor.py`](../backend/src/services/pose/video_processor.py)
   recebe os `DeviationEvent`s, associa cada desvio aos frames ativos e escolhe
   `evidence_frame` (ou `start_frame`) como frame-alvo.
2. Durante a renderização, o processor desenha o esqueleto e o HUD no vídeo
   anotado. No frame de evidência, grava um JPEG via
   `MediaStorage.evidence_frame(...)` e preenche
   `dev.evidence_frame_path`.
3. [`media_paths.py`](../backend/src/config/media_paths.py) define o layout:
   `data/outputs/{run_id}/pose/evidence/*.jpg`, além de `annotated.mp4`,
   `analysis.json` e `telemetry.json`. Os caminhos persistidos são relativos a
   `MEDIA_ROOT`.
4. [`sinks.py`](../backend/src/services/pose/sinks.py) grava o resultado
   completo em `analysis.json` e a telemetria em `telemetry.json`. O
   `MongoResultSink` transforma repetições e desvios em `EventDocument`; o
   caminho do snapshot fica em `evidencia.evidence_frame_path`.
5. [`sessions.py`](../backend/src/rest/routers/sessions.py) converte o caminho
   persistido em URL `/media/...` no relatório da sessão e popula
   `evidence_urls`, que é o contrato usado pela tela de evidências e snapshots.

### 2.4 Como o sistema sabe qual exercício está sendo feito

O sistema não infere o exercício a partir do vídeo. O cliente envia
`exercicio_id` no upload ou em `POST /api/sessoes/referencia`. Esse valor é
encaminhado ao `VideoPoseProcessor` como `exercise_identifier`.

Em [`registry.py`](../backend/src/services/pose/registry.py), cada classe é
registrada por `case_id` e `exercise_id`. O `get_analyzer` normaliza o texto
(`strip`/`upper`) e instancia a estratégia correspondente. Assim,
`FISIO-001` e `KNEE_EXTENSION_SEATED`, por exemplo, selecionam a mesma classe.
Depois disso, a estratégia determina as articulações, métrica primária,
progresso, lado e regras de desvio. O MediaPipe fornece landmarks; ele não
decide qual exercício foi gravado.

O caminho do clipe é resolvido separadamente por `DATASET_ROOT`: primeiro pelo
`exercicio_id`, depois pelo prefixo `FISIO-XXX` do nome do arquivo e, por fim,
por busca recursiva. Portanto, o nome do vídeo não deve ser tratado como
classificador implícito; o identificador enviado deve ser obrigatório e
consistente com o clipe.

## 3. Estratégia recomendada para incluir os quatro exercícios

Manter o padrão Strategy/Template Method já aprovado em
[`0002-padrao-strategy-para-analisadores-de-exercicios.md`](../docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md):

1. Não criar condicionais por exercício no processor, sink ou router.
2. Concentrar cálculo de métricas, progresso, calibração e desvios na classe
   concreta de cada exercício.
3. Manter no registry o único ponto de resolução de identificadores.
4. Manter o contrato comum `ExerciseAnalysisResult`, para que contagem,
   desvios, telemetria, snapshots e relatório continuem funcionando sem
   tratamento especial na UI.
5. Externalizar para um catálogo versionado os nomes, aliases, lado padrão,
   prescrição, limiares e requisitos de câmera/objeto quando a quantidade de
   exercícios crescer. O catálogo deve alimentar API e validação, mas não
   substituir a estratégia biomecânica.

O escopo imediato é diferente de “criar quatro analisadores do zero”: as quatro
classes já existem e estão no registry. A implementação deve primeiro comprovar
que elas atendem aos rótulos reais do dataset; somente as regras faltantes
devem ser corrigidas nas respectivas estratégias.

## 4. Fases de implementação

### Fase 1 — Inventário e contrato de entrada

- Confirmar `DATASET_ROOT`, a estrutura `FISIO-001`, `FISIO-002`,
  `FISIO-006` e `FISIO-007` e a presença dos clipes reais.
- O diretório inspecionado contém os JSON de prescrição/roteiro, mas não foram
  encontrados arquivos `.mp4`; disponibilizar os 4 clipes por caso (C01–C04)
  antes da validação de vídeo.
- Ler `prescricao.json` e `roteiros_e_rotulos.json` como fonte de requisitos,
  preservando a ressalva de que dor, carga, força e diagnóstico não devem ser
  inferidos.
- Definir o contrato de identificadores: aceitar `FISIO-001`, etc., e aliases
  canônicos (`KNEE_EXTENSION_SEATED`, `SHOULDER_PENDULUM`,
  `SHOULDER_ABDUCTION_BAND`, `ELBOW_FLEXION_LIGHT_DUMBBELL`).
- Validar que o alvo padrão de cinco repetições não sobrescreve uma prescrição
  recebida explicitamente.

### Fase 2 — Conferência dos analisadores

- Comparar cada limiar e métrica com a prescrição e os quatro rótulos do caso.
- FISIO-001: confirmar extensão/retorno, estabilidade do tronco, amplitude
  parcial e ritmo; definir como “inconclusivo” quando landmarks críticos não
  estiverem visíveis.
- FISIO-002: validar lado esquerdo, baseline do ombro, relaxamento do cotovelo,
  amplitude pendular e a limitação de que “presença de apoio” não é inferida
  por pose. Se o apoio for requisito funcional, planejar detecção de objeto ou
  uma marcação explícita de insuficiência, sem afirmar que a mesa foi detectada.
- FISIO-006: validar abdução, inclinação lateral e retorno. Separar claramente
  “mão/landmark fora de quadro” de “faixa elástica detectada”; o analisador
  atual usa visibilidade de landmarks, não uma classe de objeto.
- FISIO-007: validar flexão, retorno, cotovelo próximo ao tronco e balanço.
  Planejar detecção/estado de “halter visível” se isso for necessário para
  satisfazer o rótulo, pois o analisador atual não valida peso/material/objeto.
- Não usar detecção de objeto para inferir carga, força ou segurança clínica.
  Reportar “não detectável/inconclusivo” quando a evidência visual não bastar.

### Fase 3 — Catálogo, API e frontend

- Consolidar nomes e aliases em uma fonte única para evitar divergência entre
  `registry.py`, `EXERCISE_NAMES`, `clips-referencia` e a UI.
- Expor no backend um catálogo de exercícios selecionáveis, preferencialmente
  por um endpoint como `GET /api/exercicios` ou reutilizando uma resposta
  explicitamente versionada do catálogo de referências. Cada item deve conter,
  no mínimo, `case_id`, `exercise_id` canônico, nome, lado padrão, descrição e
  indicação de requisitos de objeto/enquadramento. A resposta não deve depender
  da existência de arquivos de vídeo.
- Definir o contrato de entrada para ambos os fluxos:
  `exercicio_id` deve ser obrigatório no upload multipart e no endpoint de
  referência; aceitar o código `FISIO-001`, `FISIO-002`, `FISIO-006` ou
  `FISIO-007` e, se aliases forem suportados, normalizá-los para um identificador
  canônico antes de criar a sessão.
- No frontend, adicionar um campo **“Exercício”** no modal **“Enviar Arquivo
  MP4”**, antes da seleção do arquivo ou junto aos demais metadados. O campo
  deve ser um `select` carregado do catálogo do backend, mostrar código e nome
  amigável e não permitir iniciar a análise sem uma opção válida.
- No upload manual, substituir o valor fixo `FISIO-001` por
  `formData.append('exercicio_id', selectedExerciseId)`. O valor selecionado
  deve ser enviado junto com `file`, `paciente_id`, `side` e
  `target_repetitions`.
- No fluxo de clipes do dataset, preencher o mesmo seletor a partir de
  `clipInfo.case_id`/`clipInfo.exercise_id` e manter o `exercicio_id` derivado
  do clipe apenas como conveniência; o backend deve continuar validando a
  coerência entre exercício informado e clipe selecionado.
- Ao abrir o modal, carregar catálogo e clipes de forma independente. Se o
  catálogo falhar, exibir erro explícito e desabilitar o início da análise, em
  vez de assumir silenciosamente `FISIO-001`. Se a lista de clipes falhar,
  manter o upload manual disponível caso o catálogo tenha sido carregado.
- Ao trocar o exercício no upload, atualizar o lado padrão quando aplicável,
  sem impedir a escolha explícita de `auto`, `direito`, `esquerdo` ou `ambos`
  caso essa opção seja exposta na UI.
- Fazer `GET /api/sessoes/clips-referencia` retornar os quatro casos com nome,
  tipo, descrição e filename reais, sem fallback que apresente somente
  FISIO-001 quando o dataset estiver configurado.
- Validar `exercicio_id` antes de resolver o vídeo e criar a sessão e retornar
  erro HTTP explícito (`400` ou `422`) para identificador não suportado; não
  deixar o erro aparecer apenas no background.
- Para `dataset_clip`, validar que o caso inferido pelo nome do arquivo é o
  mesmo exercício selecionado. Se houver conflito, rejeitar a solicitação com
  mensagem clara, evitando analisar um vídeo de FISIO-002 como FISIO-001.
- Garantir que upload, clipe de referência e CLI usem a mesma resolução do
  analisador.
- Conferir a tela de relatório: nome do exercício, contagens, desvios,
  timeline e `evidence_urls` devem ser preenchidos pelos contratos existentes,
  sem lógica específica para cada código.

### Fase 4 — Persistência e evidências

- Manter `analysis.json` como fonte completa de repetição, desvio, telemetria e
  resumo.
- Manter eventos de repetição e desvio separados no MongoDB, incluindo índice da
  repetição, severidade, timestamps, descrição, frame de evidência e caminho do
  snapshot.
- Garantir nomes de snapshot únicos por repetição/tipo/frame; evitar colisão
  quando houver dois desvios do mesmo tipo na mesma repetição.
- Verificar que o snapshot salvo é o frame anotado que aparece no vídeo e que o
  caminho relativo continua servível por `/media`.
- Garantir que ausência de frame, pose ou evidência não gere URL falsa:
  o relatório deve indicar ausência/inconclusividade.

### Fase 5 — Testes

Adicionar ou ampliar testes diretamente em `backend/tests`, sem subpastas novas:

1. **Registry/catálogo**
   - quatro códigos e quatro aliases resolvem as classes esperadas;
   - identificador desconhecido produz erro explícito;
   - o endpoint de catálogo retorna os quatro exercícios com metadados
     consistentes;
   - nomes e clipes retornados pela API correspondem ao catálogo.
2. **Seleção e contrato frontend/backend**
   - a aba de upload manual renderiza o seletor de exercício;
   - o exercício selecionado é enviado no `FormData`, sem fallback fixo para
     FISIO-001;
   - o endpoint rejeita upload sem `exercicio_id` ou com ID desconhecido;
   - o endpoint de referência rejeita conflito entre `exercicio_id` e
     `dataset_clip`;
   - selecionar cada um dos quatro exercícios gera a estratégia correta.
3. **Analisadores**
   - séries sintéticas de amplitude completa, parcial e retorno incompleto;
   - casos com inclinação/balanço e visibilidade insuficiente;
   - lado automático e lado explícito;
   - ausência de pose e resultado inconclusivo, sem falso “válido”.
4. **Repetições**
   - cinco repetições, repetição aberta no fim, gaps de landmarks e ruído;
   - validade ligada aos desvios da mesma repetição.
5. **Snapshots/sinks**
   - um desvio gera JPEG, caminho relativo e evento Mongo correspondente;
   - `analysis.json`, `telemetry.json`, vídeo anotado e URLs do relatório;
   - múltiplos desvios não sobrescrevem snapshots.
6. **Integração com dataset**
   - executar C01–C04 dos quatro casos, quando os `.mp4` estiverem disponíveis;
   - comparar contagem, tipos de desvio, severidade e presença de evidência
     com os rótulos esperados;
   - não usar a fala de dor simulada como resultado biomecânico.

### Fase 6 — Aceite operacional

- Executar cada caso por `POST /api/sessoes/referencia?sync=true` e também pelo
  caminho assíncrono.
- Confirmar status `processando` → `concluido`/`erro`, persistência e consulta
  do relatório.
- Inspecionar visualmente vídeo anotado, timeline, cards de desvio e snapshots.
- Registrar limitações por enquadramento, oclusão, apoio/objeto ausente e
  ausência de áudio compreensível.
- Validar separação de participantes entre treino/validação/teste, conforme o
  README do dataset, sem misturar clipes do mesmo participante entre conjuntos.

## 5. Critérios de pronto

- Os quatro códigos e aliases são aceitos por API, CLI e processor.
- A tela de nova análise permite selecionar explicitamente o exercício também
  ao enviar um MP4 próprio; nenhum upload manual usa FISIO-001 implicitamente.
- O backend expõe o catálogo necessário, valida `exercicio_id` antes do
  processamento e encaminha o identificador validado ao registry.
- Um clipe de dataset só pode ser processado com o exercício correspondente ao
  seu caso.
- Cada caso produz `SessionSummary`, eventos de repetição, desvios,
  telemetria, vídeo anotado e snapshots quando há evidência suficiente.
- O relatório mostra contagens, severidades, descrições e URLs funcionais sem
  código específico por tela para cada exercício.
- C01–C04 são avaliados contra seus rótulos, com divergências documentadas.
- Requisitos que não podem ser observados por pose (mesa, faixa ou halter)
  aparecem como ausência/inconclusivo, nunca como detecção inventada.
- Os testes existentes permanecem verdes e os novos testes cobrem o contrato
  comum e as quatro estratégias.

## 6. Riscos e decisões que devem ser confirmadas antes da execução

- **Identificação:** manter seleção explícita pelo `exercicio_id` é mais seguro
  que classificar automaticamente o vídeo; classificação automática deve ser
  um projeto separado, com dataset e métricas próprias.
- **Objetos:** decidir se “faixa/halter/apoio” é requisito bloqueante,
  advertência ou apenas metadado. A decisão altera o contrato de resultado e
  os critérios de validade.
- **Calibração:** ângulos em vídeo RGB são aparentes; não apresentar valores
  como medição clínica exata.
- **Dataset ausente:** sem os `.mp4`, a validação fica limitada a testes
  sintéticos e contratos; os vídeos precisam ser fornecidos antes do aceite
  end-to-end.
- **Compatibilidade:** alterações no contrato `ExerciseAnalysisResult`,
  `EventDocument` ou `SessionReportResponse` exigem atualização coordenada de
  sinks, repositórios e frontend.
