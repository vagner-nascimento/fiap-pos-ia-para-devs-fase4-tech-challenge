# Plano: correção do progresso da análise e revisão das etapas

## Objetivo

Corrigir a tela de processamento para que ela avance de acordo com o trabalho
real executado no backend, sem permanecer indefinidamente em uma etapa e
concluir várias etapas de uma só vez ao final. A lista apresentada ao usuário
também deverá conter somente etapas implementadas e observáveis no pipeline
atual.

O plano não inclui a implementação nesta etapa.

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

## Implementação planejada

### 1. Formalizar o contrato de progresso no backend

- Criar constantes ou um modelo tipado para as etapas, evitando strings
  espalhadas entre router, processor, modelo de banco e frontend.
- Definir campos no documento/response da sessão para:
  - identificador estável da etapa;
  - índice ou ordem da etapa;
  - total de etapas;
  - percentual atual;
  - descrição/mensagem da etapa;
  - timestamp de atualização;
  - mensagem de erro quando aplicável.
- Preservar compatibilidade de leitura com sessões antigas que só possuem
  `etapa` e `status`; nesses casos, aplicar um mapeamento explícito ou informar
  progresso desconhecido, sem afirmar uma etapa incorreta.
- Garantir que o total seja calculado a partir da lista de etapas reais, e não
  de um número literal no frontend.

### 2. Persistir progresso durante o processamento

- Adaptar
  [`_run_pose_analysis_pipeline`](../backend/src/rest/routers/sessions.py)
  para fornecer ao `VideoPoseProcessor` um callback que converta os eventos de
  progresso em atualizações de `SessionRepository.update_status` ou em um
  método específico de atualização de progresso.
- Atualizar MongoDB em transições de etapa e em pontos intermediários de fases
  longas, especialmente durante:
  - extração frame a frame;
  - renderização do vídeo anotado;
  - qualquer operação de transcrição que possa demorar.
- Fazer as atualizações de forma monotônica: uma atualização atrasada não pode
  sobrescrever uma etapa mais avançada.
- Persistir `updated_at` junto com o progresso para permitir diagnóstico de
  sessões sem atualização.
- Tratar falha de atualização de progresso como erro explícito e observável,
  sem transformar uma falha de persistência em falso sucesso. Avaliar o efeito
  da indisponibilidade temporária do MongoDB sobre o worker e registrar logs
  com `session_id`, etapa e percentual.
- Manter a atualização final para `concluido` como uma operação posterior à
  gravação de todos os artefatos.

### 3. Aproveitar corretamente o callback do processador

- Ajustar a granularidade do callback de
  [`VideoPoseProcessor.process_video`](../backend/src/services/pose/video_processor.py)
  para que o percentual represente a fase real, sem saltos que façam várias
  etapas parecerem concluídas ao mesmo tempo.
- Mapear os nomes internos (`extraindo_landmarks`,
  `analisando_movimento`, `transcrevendo_audio`, `gerando_artefatos`,
  `renderizando_video` e `concluido`) para identificadores e rótulos de
  produto.
- Separar “geração de artefatos” de “persistência final” somente se o código
  conseguir publicar uma transição confiável entre elas; caso contrário,
  refletir a unidade real do trabalho em uma única etapa.
- Não usar o callback apenas para log: ele deve ser a fonte de atualização do
  estado persistido da sessão.
- Garantir que callbacks durante loops de frames não causem excesso de
  escritas no MongoDB. Usar mudança mínima de percentual, intervalo mínimo ou
  coalescência, mantendo uma atualização suficientemente frequente para a
  tela não aparentar congelamento.

### 4. Tornar o frontend orientado pelo contrato

- Alterar [`frontend/src/api/sessions.js`](../frontend/src/api/sessions.js)
  somente se for necessário normalizar o novo payload; manter o tratamento de
  erro HTTP explícito.
- Refatorar
  [`frontend/src/components/ProcessingView.jsx`](../frontend/src/components/ProcessingView.jsx)
  para consumir as etapas/progresso retornados pela API, eliminando:
  - o array fixo de sete etapas;
  - `currentStep = 3`;
  - percentuais `55` e `42` codificados;
  - textos que afirmam etapas não implementadas.
- Ajustar
  [`frontend/src/components/ds/StepList.jsx`](../frontend/src/components/ds/StepList.jsx)
  para receber estado já normalizado ou uma lista com identificadores estáveis,
  sem inferir a etapa com base em índices mágicos.
- Garantir atualização contínua do polling e impedir que uma resposta antiga
  substitua uma resposta mais nova. Se necessário, controlar requisições em
  voo e o ciclo de polling com cancelamento/versão da resposta.
- Rever o comportamento quando a consulta falhar: exibir erro de comunicação
  distinguindo-o de erro do processamento, sem parar silenciosamente o
  acompanhamento. Definir retry/backoff e uma ação manual de atualização.
- Exibir “última atualização” ou uma mensagem de falta de atualização quando o
  timestamp do backend exceder um limite acordado. Isso deve sinalizar
  possível travamento, não avançar artificialmente a etapa.

### 5. Revisar textos e documentação diretamente relacionada

- Atualizar comentários e textos de
  [`frontend/src/components/ProcessingView.jsx`](../frontend/src/components/ProcessingView.jsx)
  que mencionam “7 etapas da arquitetura”.
- Revisar
  [`docs/arquitetura/resumo-progresso-etapas.md`](../docs/arquitetura/resumo-progresso-etapas.md)
  e documentos de arquitetura que descrevem sete etapas para distinguir
  funcionalidades implementadas de intenções futuras.
- Registrar claramente que expressão facial não faz parte da esteira atual e
  que novas etapas só devem aparecer após terem contrato, atualização de
  progresso e testes.

## Testes planejados

### Backend

- Testar o mapeamento de cada evento interno do processador para a etapa,
  rótulo, ordem e faixa de percentual esperados.
- Testar que as atualizações de progresso são monotônicas e que uma transição
  final não é publicada antes da persistência dos artefatos.
- Testar atualização durante extração/renderização com callback simulado,
  incluindo processamento longo e múltiplas notificações.
- Testar falha em cada etapa: status `erro`, etapa correta, mensagem
  explícita e ausência de `concluido`.
- Testar compatibilidade com documento antigo sem os novos campos.
- Testar que a lista de etapas não contém expressão facial, fusão inexistente
  ou qualquer operação que não esteja presente no pipeline.
- Testar o endpoint `GET /api/sessoes/{id}` com sessão em andamento, concluída
  e com erro.

Os testes devem permanecer diretamente em [`backend/tests`](../backend/tests),
seguindo os nomes `test_<caminho_do_pacote>.py`.

### Frontend

- Testar a normalização/renderização de uma sessão em cada etapa real.
- Testar que somente as etapas recebidas pela API são renderizadas e que
  “Expressão facial” não aparece.
- Testar os estados ativo, pendente, concluído e erro.
- Testar que o percentual e o rótulo do chip acompanham o mesmo estado.
- Testar respostas fora de ordem ou repetidas sem regressão visual.
- Testar erro de consulta, atualização manual e indicação de sessão sem
  atualização recente.
- Executar build de produção para validar o contrato e os imports do
  frontend.

## Validação manual

1. Iniciar uma análise com vídeo curto e observar cada transição no MongoDB e
   na tela.
2. Usar um vídeo suficientemente longo para manter a extração e a
   renderização em andamento; confirmar que o percentual e o timestamp
   continuam mudando.
3. Confirmar que não ocorre o salto de várias etapas após um período parado.
4. Interromper ou provocar erro em uma etapa e confirmar que a tela identifica
   o ponto real da falha.
5. Confirmar que a lista final contém somente etapas executadas, incluindo
   áudio quando disponível e sem expressão facial.
6. Repetir com transcrição indisponível e verificar o comportamento definido
   para essa capacidade opcional, sem perder o resultado biomecânico.
7. Abrir o relatório somente após a sessão e seus artefatos estarem
   efetivamente concluídos.

## Fora do escopo

- Implementar análise de expressão facial.
- Criar uma etapa visual para uma capacidade apenas planejada.
- Alterar os algoritmos de MediaPipe, os analisadores dos exercícios ou a
  classificação clínica.
- Fazer o frontend estimar progresso com base em tempo decorrido.
- Resolver performance geral do pipeline que não esteja relacionada à
  publicação/consumo do progresso.
