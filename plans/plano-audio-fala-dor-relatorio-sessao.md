# Plano: áudio, transcrição e fala de dor no relatório da sessão

## Objetivo

Alterar o relatório individual da sessão para:

1. remover a faixa **Dor facial** da linha do tempo;
2. extrair o áudio do vídeo durante o processamento no backend;
3. transcrever o áudio em português com timestamps;
4. classificar as falas relacionadas a dor/desconforto;
5. persistir esses eventos como `fala_dor`;
6. fazer com que a faixa **Fala de dor** já existente na tela seja preenchida
   com os eventos persistidos.

Neste plano, “dor fácil” da solicitação é interpretado como **dor facial**, que
é o rótulo exibido na imagem e no componente atual.

## Estado atual identificado

- [`frontend/src/components/ds/Timeline.jsx`](../frontend/src/components/ds/Timeline.jsx)
  renderiza quatro faixas: repetições, desvios, dor facial e fala de dor.
- O tipo `fala_dor` já existe em
  [`backend/src/models/database/event.py`](../backend/src/models/database/event.py),
  mas [`backend/src/services/pose/sinks.py`](../backend/src/services/pose/sinks.py)
  só cria eventos de repetição e desvio.
- O relatório em
  [`backend/src/rest/routers/sessions.py`](../backend/src/rest/routers/sessions.py)
  já retorna todos os eventos persistidos sem filtrar por tipo; portanto, a
  inclusão dos novos eventos no MongoDB é suficiente para alimentar a API e a
  timeline.
- [`docs/code-examples/audio_to_text.py`](../docs/code-examples/audio_to_text.py)
  contém extração do áudio, conversão para mono/16 kHz, redução de ruído e
  transcrição com `faster-whisper`.
- [`docs/code-examples/pain_detection.py`](../docs/code-examples/pain_detection.py)
  contém normalização de texto, classificação de dor e geração de segmentos
  com início, fim, timestamp, nível, score e texto.
- As dependências de áudio/Whisper usadas pelos exemplos não estão declaradas
  em [`backend/pyproject.toml`](../backend/pyproject.toml).

## Implementação planejada

### 1. Extrair a lógica reutilizável de áudio para o backend

- Criar um módulo de serviço de áudio/transcrição dentro de
  `backend/src/services`, seguindo o fluxo de serviço já usado pelo backend.
- Levar dos exemplos somente as funções necessárias:
  - extração do áudio do vídeo;
  - preparação do áudio para transcrição;
  - carregamento preguiçoso e compartilhado do modelo Whisper;
  - transcrição segmentada com timestamps;
  - normalização e classificação de dor.
- Manter o prompt em português com contexto de fisioterapia e as opções de
  VAD/decodificação dos exemplos, mas tornar os caminhos e diretórios
  dependentes de `MediaStorage`, sem caminhos fixos de `docs/code-examples`.
- Usar um arquivo de áudio intermediário dentro do diretório de artefatos da
  sessão e removê-lo ao final quando ele não fizer parte do contrato de
  artefatos públicos. Se a decisão for manter o áudio para auditoria, expor
  o caminho no contrato de sessão em vez de deixar um arquivo órfão.
- Garantir fechamento dos recursos de vídeo/áudio e mensagens de log explícitas
  quando a extração ou transcrição falhar.

### 2. Integrar áudio e fala de dor ao pipeline de processamento

- Alterar [`backend/src/services/pose/video_processor.py`](../backend/src/services/pose/video_processor.py)
  para executar a etapa de áudio após a validação do vídeo e antes da
  persistência final dos resultados, mantendo a análise biomecânica existente.
- Passar os segmentos classificados para o sink por meio de um resultado
  tipado ou argumento explícito, evitando estado global e evitando acoplar o
  analisador de pose à implementação do Whisper.
- Definir o comportamento de erro: falha de áudio/transcrição deve ser
  registrada como etapa inconclusiva e não pode apagar os eventos biomecânicos
  válidos. O status final e a justificativa devem distinguir “sem fala
  detectada” de “áudio indisponível/erro de processamento”.
- Atualizar o progresso da sessão com uma etapa de transcrição para que o
  processamento assíncrono não pareça concluído antes dessa etapa.

### 3. Persistir eventos `fala_dor`

- Alterar [`backend/src/services/pose/sinks.py`](../backend/src/services/pose/sinks.py)
  para criar um `EventDocument` por segmento classificado como fala de dor ou
  desconforto.
- Usar:
  - `tipo`: `EventType.FALA_DOR`;
  - `instante_inicio`/`instante_fim`: timestamps do Whisper;
  - `descricao`: texto transcrito;
  - `valores`: `nivel`, `score` e timestamp formatado;
  - `evidencia`: texto original e, se disponível, referência ao áudio;
  - `severidade`: nível clínico textual apenas se isso for compatível com o
    contrato existente, sem reutilizar indevidamente severidade de desvio.
- Persistir na faixa **Fala de dor** os segmentos classificados como `dor`,
  `desconforto`, `muita_dor` e `pouca_ou_nenhuma_dor`. Este último deve
  aparecer com uma indicação visual/textual explícita de ausência ou baixa
  intensidade de dor, sem ser apresentado como uma queixa ativa. Segmentos
  classificados como `indeterminado` devem continuar disponíveis no artefato
  de transcrição/diagnóstico, mas não precisam aparecer na timeline.
- Ordenar os eventos pelo início e preservar exatamente o texto transcrito
  para tooltip e auditoria.
- Ajustar contagens/contratos somente onde necessário; fala de dor não deve
  ser contabilizada como desvio biomecânico nem alterar o score de
  conformidade sem uma regra clínica explícita.

### 4. Ajustar o relatório e a linha do tempo

- Em [`frontend/src/components/ds/Timeline.jsx`](../frontend/src/components/ds/Timeline.jsx),
  remover o filtro, o estado visual e a linha de **Dor facial**.
- Manter a faixa **Fala de dor**, seus cliques para seek e tooltips, usando os
  timestamps e a descrição vindos do backend.
- Atualizar comentários/documentação diretamente relacionados que ainda
  descrevam quatro faixas ou indiquem que dor facial é exibida.
- Não alterar a API do relatório para buscar eventos separadamente, pois
  `GET /sessoes/{id}/relatorio` já serializa a lista completa.
- Verificar se snapshots, cards de evidência, comparação clínica e impressão
  continuam sem referência residual a dor facial.

### 5. Dependências e configuração

- Declarar no `backend/pyproject.toml` as dependências efetivamente usadas:
  `moviepy`, `noisereduce`, `soundfile`, `faster-whisper` e eventuais
  dependências transitivas necessárias para o ambiente suportado.
- Não copiar modelos ou ambientes virtuais dos exemplos para o backend.
- Documentar variáveis/configuração do tamanho do modelo, dispositivo,
  diretório de cache e possibilidade de desabilitar transcrição quando o
  ambiente não tiver suporte de áudio.
- Manter o carregamento do Whisper preguiçoso para não aumentar o tempo de
  inicialização do FastAPI.

## Testes planejados

### Backend

- Testar normalização e classificação para:
  - “estou com dor”;
  - “está doendo bastante”;
  - “sinto um incômodo”;
  - “não sinto mais dor”;
  - texto sem relação com dor.
- Testar a conversão de segmentos do Whisper em eventos, incluindo timestamps,
  texto, nível e score.
- Testar que `dor`, `desconforto`, `muita_dor` e `pouca_ou_nenhuma_dor`
  geram eventos `fala_dor` com a classificação preservada, enquanto
  `indeterminado` não gera bloco na timeline.
- Testar o sink com eventos biomecânicos e de fala no mesmo resultado, sem
  alterar contagens de repetições/desvios.
- Testar falha na extração/transcrição sem perder a persistência dos eventos
  biomecânicos e com erro/log explícito.
- Testar o endpoint de relatório com eventos `fala_dor` e os campos de texto
  e timestamps serializados.
- Usar mocks para Whisper, MoviePy e arquivos de áudio nos testes unitários;
  reservar execução real do modelo para um teste de integração opcional,
  condicionado à presença dos recursos.

### Frontend

- Verificar que `Timeline` não renderiza mais o rótulo/faixa **Dor facial**.
- Verificar que eventos `fala_dor` renderizam bloco, texto no tooltip e seek
  no início do segmento, incluindo um estado visual/textual distinto para
  `pouca_ou_nenhuma_dor`.
- Verificar o estado vazio quando não houver fala de dor.
- Executar o build do frontend para detectar imports ou referências residuais.

### Validação manual

- Processar um vídeo com fala audível e confirmar no relatório:
  - áudio extraído;
  - transcrição com intervalos coerentes;
  - blocos na faixa **Fala de dor**;
  - clique no bloco posicionando o vídeo no instante correto;
  - ausência da faixa **Dor facial**.
- Processar vídeo sem áudio compreensível e confirmar uma mensagem/estado
  explícito, sem apresentar “nenhuma queixa” como se fosse evidência de
  ausência de dor.

## Critérios de aceite

- A linha do tempo exibe repetições, desvios e fala de dor, sem dor facial.
- Cada fala relevante aparece no instante correto e contém o texto transcrito.
- A análise de fala é persistida como evento `fala_dor` e retorna pelo relatório.
- Falhas de áudio não invalidam silenciosamente a análise biomecânica.
- Nenhum caminho de dataset ou código de execução dos exemplos é usado
  diretamente em produção.
- Dependências, configuração, testes e documentação do backend permanecem
  alinhados com a nova etapa de processamento.
