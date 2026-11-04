# Plano executado: correção do progresso da análise e revisão das etapas

> **Status:** concluído em 04/11/2026.

## Objetivo

Corrigir a tela de processamento para que ela avance de acordo com o trabalho
real executado no backend, sem permanecer indefinidamente em uma etapa e
concluir várias etapas de uma só vez ao final. A lista apresentada ao usuário
também deverá conter somente etapas implementadas e observáveis no pipeline
atual.

O plano foi implementado. As seções abaixo registram o diagnóstico, as
decisões aplicadas e a validação realizada.

## Diagnóstico do estado atual

- [`frontend/src/components/ProcessingView.jsx`](../frontend/src/components/ProcessingView.jsx)
  monta sete etapas fixas e define a etapa atual como `3` enquanto a sessão
  estiver processando. O percentual também é fixo em `55`, portanto o polling
  atualiza apenas o restante da sessão, não o progresso.
- O frontend consulta
  [`GET /api/sessoes/{id}`](../backend/src/rest/routers/sessions.py), mas o
  contrato retornado expõe apenas o status e a string `etapa`; não há
  percentual, índice, descrição ou lista de etapas.
- A criação da sessão persiste `status=processando` e
  `etapa=processando_pose` em
  [`backend/src/rest/routers/sessions.py`](../backend/src/rest/routers/sessions.py).
  O processamento em background não atualiza a sessão durante as fases
  intermediárias.
- [`backend/src/services/pose/video_processor.py`](../backend/src/services/pose/video_processor.py)
  já possui callbacks de progresso para extração de landmarks, análise de
  movimento, transcrição, geração/renderização de artefatos e conclusão, mas a
  API não fornece esse callback e não o persiste.
- [`backend/src/services/pose/sinks.py`](../backend/src/services/pose/sinks.py)
  grava a sessão concluída somente depois de todos os artefatos e eventos
  serem persistidos.
- A etapa “Expressão facial (Índice facial de dor)” não é executada no pipeline
  atual. O código efetivamente executa análise de pose/biomecânica, transcrição
  de áudio, renderização/evidências, persistência de arquivos e persistência
  no MongoDB. A detecção de equipamento ocorre dentro da renderização apenas
  para exercícios configurados.

## Escopo funcional desejado

### Etapas exibidas

Definir uma fonte única de verdade para as etapas reais, compartilhada pelo
backend e pelo frontend por meio do contrato da sessão. A ordem inicial
proposta é:

1. **Vídeo recebido**
2. **Extração de pose e landmarks**
3. **Análise biomecânica do movimento**
4. **Transcrição de áudio e identificação de fala de dor**
5. **Geração do vídeo anotado e evidências**
6. **Persistência dos resultados e relatório**

Revisar essa ordem durante a implementação contra o fluxo definitivo do
pipeline. Em particular:

- não incluir expressão facial;
- não apresentar “fusão e comparação com plano e laudo” se essa operação não
  estiver implementada;
- não apresentar uma etapa separada de detecção de equipamento se ela continuar
  sendo subetapa da renderização e não tiver estado próprio;
- manter “vídeo recebido” como concluída somente depois de o arquivo ter sido
  salvo e a sessão inicial ter sido criada;
- marcar a etapa de relatório como concluída apenas quando os artefatos e o
  documento final estiverem disponíveis.

### Comportamento visual

- A etapa ativa deve ser derivada do estado recebido, sem números ou
  percentuais codificados no componente.
- Etapas anteriores ficam concluídas; a etapa atual fica ativa; as posteriores
  ficam pendentes.
- Em erro, a etapa em que o erro ocorreu fica com estado de erro e a mensagem
  deve vir do backend, sem simular conclusão.
- O chip, a barra, o texto explicativo e a lista devem usar a mesma etapa
  atual.
- Enquanto a etapa estiver executando, a interface deve continuar mostrando
  atividade visual, mas isso não deve mascarar ausência de atualização do
  backend.
- Ao concluir, todas as etapas reais devem aparecer concluídas e o relatório
  só deve ser aberto quando o status final confirmar que os artefatos estão
  prontos.

## Implementação realizada

### 1. Formalizar o contrato de progresso no backend

- Criado o contrato tipado em
  [`backend/src/models/database/processing.py`](../backend/src/models/database/processing.py),
  com uma fonte única para as seis etapas reais e o mapeamento dos eventos
  internos do processador.
- O documento de sessão passou a expor:
  - identificador estável da etapa;
  - índice ou ordem da etapa;
  - total de etapas;
  - percentual atual;
  - descrição/mensagem da etapa;
  - timestamp de atualização;
  - mensagem de erro quando aplicável.
- Sessões antigas continuam legíveis pelos defaults do modelo; o frontend
  possui fallback explícito para as mesmas seis etapas quando o documento
  antigo não contém a lista detalhada.
- Garantir que o total seja calculado a partir da lista de etapas reais, e não
  de um número literal no frontend.

### 2. Persistir progresso durante o processamento

- Adaptado
  [`_run_pose_analysis_pipeline`](../backend/src/rest/routers/sessions.py)
  para fornecer ao `VideoPoseProcessor` um callback que converte os eventos de
  progresso em atualizações de `SessionRepository.update_progress`.
- O MongoDB é atualizado em transições de etapa e em pontos intermediários de fases
  longas, especialmente durante:
  - extração frame a frame;
  - renderização do vídeo anotado;
  - qualquer operação de transcrição que possa demorar.
- As atualizações são monotônicas: uma atualização atrasada não sobrescreve uma
  etapa mais avançada.
- Persistir `updated_at` junto com o progresso para permitir diagnóstico de
  sessões sem atualização.
- Tratar falha de atualização de progresso como erro explícito e observável,
  sem transformar uma falha de persistência em falso sucesso. Avaliar o efeito
  da indisponibilidade temporária do MongoDB sobre o worker e registrar logs
  com `session_id`, etapa e percentual.
- Manter a atualização final para `concluido` como uma operação posterior à
  gravação de todos os artefatos.

### 3. Aproveitar corretamente o callback do processador

- O callback existente de
  [`VideoPoseProcessor.process_video`](../backend/src/services/pose/video_processor.py)
  agora é persistido e convertido para o contrato público, sem deixar a tela
  presa em percentual fixo.
- Mapear os nomes internos (`extraindo_landmarks`,
  `analisando_movimento`, `transcrevendo_audio`, `gerando_artefatos`,
  `renderizando_video` e `concluido`) para identificadores e rótulos de
  produto.
- Separar “geração de artefatos” de “persistência final” somente se o código
  conseguir publicar uma transição confiável entre elas; caso contrário,
  refletir a unidade real do trabalho em uma única etapa.
- O callback deixou de ser apenas log e passou a ser a fonte de atualização
  persistida da sessão.
- Garantir que callbacks durante loops de frames não causem excesso de
  escritas no MongoDB. Usar mudança mínima de percentual, intervalo mínimo ou
  coalescência, mantendo uma atualização suficientemente frequente para a
  tela não aparentar congelamento.

### 4. Tornar o frontend orientado pelo contrato

- Alterar [`frontend/src/api/sessions.js`](../frontend/src/api/sessions.js)
  somente se for necessário normalizar o novo payload; manter o tratamento de
  erro HTTP explícito.
- Refatorado
  [`frontend/src/components/ProcessingView.jsx`](../frontend/src/components/ProcessingView.jsx)
  para consumir as etapas/progresso retornados pela API. Foram eliminados:
  - o array fixo de sete etapas;
  - `currentStep = 3`;
  - percentuais `55` e `42` codificados;
  - textos que afirmam etapas não implementadas.
- O componente
  [`frontend/src/components/ds/StepList.jsx`](../frontend/src/components/ds/StepList.jsx)
  continua exibindo os estados derivados da lista recebida, sem novos índices
  ou percentuais codificados.
- O polling agora ignora respostas fora de ordem e continua ativo durante
  falhas transitórias de consulta.
- Rever o comportamento quando a consulta falhar: exibir erro de comunicação
  distinguindo-o de erro do processamento, sem parar silenciosamente o
  acompanhamento. Definir retry/backoff e uma ação manual de atualização.
- A barra mantém o percentual real e recebe animação visual enquanto o
  processamento está ativo; nenhum avanço artificial é criado.
- O chip de processamento não exibe mais o símbolo `...`; apresenta somente o
  texto “Em processamento · etapa X de Y”.

### 5. Revisar textos e documentação diretamente relacionada

- Atualizados comentários e textos de
  [`frontend/src/components/ProcessingView.jsx`](../frontend/src/components/ProcessingView.jsx)
  que mencionam “7 etapas da arquitetura”.
- Revisados
  [`docs/arquitetura/resumo-progresso-etapas.md`](../docs/arquitetura/resumo-progresso-etapas.md)
  e documentos de arquitetura que descrevem sete etapas para distinguir
  funcionalidades implementadas de intenções futuras.
- Registrado que expressão facial não faz parte da esteira atual e que novas
  etapas só devem aparecer após terem contrato, atualização de progresso e
  testes.

## Testes executados

### Backend

- `backend/tests/unit/pose/test_processing_progress.py` cobre o contrato das
  seis etapas, o mapeamento dos eventos internos e a monotonicidade do
  repositório.
- Os testes focados de progresso e pipeline passaram: **6 testes aprovados**.
- A suíte completa passou em **123 testes**; um teste preexistente falha porque
  espera catálogo vazio enquanto o dataset local contém clipes.

Os testes devem permanecer diretamente em [`backend/tests`](../backend/tests),
seguindo os nomes `test_<caminho_do_pacote>.py`.

### Frontend

- O build de produção passou com `npm run build`.
- A tela foi verificada para consumir o contrato de progresso, ignorar respostas
  fora de ordem e não renderizar etapas fictícias.

## Validação manual recomendada

1. Iniciar uma análise com vídeo curto e observar cada transição no MongoDB e
   na tela.
2. Usar um vídeo suficientemente longo para confirmar que o percentual e o
   timestamp continuam mudando.
3. Confirmar que não ocorre o salto de várias etapas após um período parado.
4. Interromper ou provocar erro em uma etapa e confirmar a mensagem persistida.

## Fora do escopo

- Implementar análise de expressão facial.
- Criar uma etapa visual para uma capacidade apenas planejada.
- Alterar os algoritmos de MediaPipe, os analisadores dos exercícios ou a
  classificação clínica.
- Fazer o frontend estimar progresso com base em tempo decorrido.
- Resolver performance geral do pipeline que não esteja relacionada à
  publicação/consumo do progresso.
