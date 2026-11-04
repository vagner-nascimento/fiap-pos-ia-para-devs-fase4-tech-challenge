# Plano — download e seleção do dataset na nova análise

## Objetivo

Substituir a alimentação frágil da tela **Nova Análise de Biomecânica** por um fluxo
baseado no repositório público oficial de datasets:

`https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge-datasets`

O backend deverá controlar a disponibilidade local do dataset, e a tela deverá
oferecer **Download Dataset** somente quando os vídeos ainda não estiverem
disponíveis. Nenhuma análise deverá ser iniciada com nomes ou clipes fictícios de
fallback.

## Diagnóstico da implementação atual

- [`backend/src/rest/routers/sessions.py`](../backend/src/rest/routers/sessions.py)
  já expõe `GET /sessoes/clips-referencia`, mas lê apenas `DATASET_ROOT` e cria
  uma lista artificial quando nenhum clipe é encontrado.
- O mesmo router mantém `EXERCISE_OPTIONS` hardcoded e a resolução de clipes
  tenta caminhos alternativos, inclusive busca recursiva e `video_path`.
- [`frontend/src/components/SessionsListView.jsx`](../frontend/src/components/SessionsListView.jsx)
  carrega exercícios e clipes ao abrir o modal, porém não distingue dataset
  ausente de catálogo vazio e não oferece download.
- [`frontend/src/api/sessions.js`](../frontend/src/api/sessions.js) possui
  apenas a consulta do catálogo e o disparo da sessão; não há cliente para
  status/download.
- [`docker-compose.yaml`](../docker-compose.yaml) monta um clone externo do
  dataset em `/app/datasets:ro`. Esse acoplamento deve deixar de ser a fonte
  obrigatória em Docker.
- O repositório de datasets contém atualmente os casos `FISIO-001`,
  `FISIO-002`, `FISIO-006` e `FISIO-007`, cada um com quatro vídeos MP4. Os
  nomes observados incluem:
  - `FISIO-001-correto.mp4`, `FISIO-001-extensao-parcial.mp4`,
    `FISIO-001-inclinacao-tronco.mp4`, `FISIO-001-velocidade-irregular.mp4`;
  - quatro variações de `FISIO-002`;
  - `FISIO-006-C01.mp4` a `FISIO-006-C04.mp4`;
  - `FISIO-007-C01.mp4` a `FISIO-007-C04.mp4`.

## Etapas de implementação

### 1. Inventariar e remover a alimentação que não funciona

1. Confirmar quais partes do catálogo atual são realmente suportadas pelos
   analisadores registrados em `services/pose/registry.py`.
2. Remover o fallback artificial de `list_reference_clips`; dataset ausente deve
   ser representado explicitamente como indisponível, nunca como um clipe que
   parece existir.
3. Remover dos endpoints e do frontend qualquer dependência de dados de exemplo
   que não tenham origem no clone local.
4. Revisar a resolução de caminhos para aceitar apenas clipes catalogados no
   diretório gerenciado do dataset, com validação de caso, arquivo, extensão e
   permanência dentro da raiz autorizada.
5. Manter o upload manual como fluxo separado; não permitir que um caminho
   arbitrário do host seja usado como substituto silencioso do dataset.
6. Atualizar testes que hoje esperam o clipe fallback e adicionar casos para
   dataset ausente, catálogo vazio e clipe inexistente.

### 2. Criar o armazenamento e o serviço de dataset no backend

1. Definir uma raiz persistente e configurável para o clone, preferencialmente
   sob `MEDIA_ROOT` (por exemplo, `MEDIA_ROOT/datasets/fisio`), evitando que o
   código dependa de um diretório irmão do projeto.
2. Fixar no backend a URL oficial do repositório e a branch/ref permitida;
   não aceitar URL arbitrária enviada pelo navegador.
3. Criar uma camada de serviço responsável por:
   - verificar se o clone está completo e utilizável;
   - listar casos e vídeos MP4 com caminhos relativos;
   - clonar com `git clone --depth 1` para um diretório temporário;
   - validar a estrutura esperada antes de publicar o clone;
   - publicar de forma atômica e idempotente;
   - evitar dois downloads concorrentes;
   - relatar falhas de `git`, permissões, espaço em disco e estrutura inválida.
4. Definir o que significa “baixado”: clone concluído, diretórios esperados
   presentes e pelo menos um MP4 válido. Um download interrompido não pode ser
   exibido como pronto.
5. Ajustar o ambiente Docker para ter `git` instalado e persistir a nova raiz
   por volume. Remover o volume de desenvolvimento que aponta para o repositório
   externo como requisito de execução.
6. Documentar a variável de raiz, a URL/ref e o comportamento de persistência no
   `.env.example`, `docker-compose.yaml` e READMEs relacionados.

### 3. Expor o estado e o catálogo por API

Adicionar contratos REST explícitos, sem misturar controle de download com criação
de sessão:

1. `GET /api/datasets/fisio/status`:
   - `available`/`downloaded`;
   - estado `not_downloaded`, `downloading`, `ready` ou `error`;
   - mensagem de erro quando aplicável;
   - quantidade de casos e clipes quando pronto.
2. `POST /api/datasets/fisio/download`:
   - inicia o clone de forma segura e retorna `202` enquanto estiver em andamento,
     ou resposta idempotente quando já estiver pronto;
   - não dispara uma análise automaticamente.
3. `GET /api/datasets/fisio/clips`:
   - retorna somente os arquivos reais do clone;
   - inclui `case_id`, identificador do exercício, nome do arquivo, tipo,
     descrição e caminho lógico usado pelo endpoint de análise.
4. Fazer `GET /sessoes/clips-referencia` consumir o catálogo do serviço, ou
   descontinuá-lo após migrar o frontend, evitando duas fontes de verdade.
5. Alterar `POST /sessoes/referencia` para aceitar apenas um item retornado pelo
   catálogo pronto e usar o caminho interno resolvido pelo serviço.
6. Atualizar modelos Pydantic, documentação OpenAPI e testes de contrato para
   respostas de sucesso, ausência, download em andamento e erro.

### 4. Adaptar a tela “Nova Análise”

1. Ao abrir o modal, consultar primeiro o status do dataset.
2. Se não estiver pronto, exibir estado vazio explicativo e o botão exatamente
   como **Download Dataset**.
3. Ao clicar, chamar o endpoint de download, desabilitar o botão, exibir
   progresso/estado “baixando” e impedir o início da análise até a conclusão.
4. Após sucesso, atualizar o status e carregar os clipes reais sem exigir
   recarregamento da página.
5. Se já estiver pronto, ocultar o botão e exibir o catálogo para seleção,
   agrupado ou filtrável por `FISIO-001`, `FISIO-002`, `FISIO-006` e `FISIO-007`.
6. Selecionar o exercício a partir do clipe escolhido; impedir combinações
   incompatíveis entre exercício e vídeo.
7. Preservar os campos de paciente e meta de repetições e manter o upload manual
   em uma aba separada.
8. Exibir mensagens acionáveis para download falho, dataset vazio, indisponível,
   análise sem clipe selecionado e erro de rede.
9. Atualizar o cliente em `src/api/sessions.js` e os estilos somente onde forem
   necessários para os estados do botão e do catálogo.

### 5. Integrar o clipe selecionado ao pipeline

1. Ao iniciar uma análise via dataset, enviar o identificador lógico do clipe,
   não um caminho absoluto fornecido pelo cliente.
2. Resolver o arquivo no backend dentro da raiz validada e passá-lo ao pipeline
   existente de pose/background task.
3. Garantir que o registro da sessão grave um caminho reproduzível e seguro para
   o vídeo utilizado, sem quebrar a geração dos resultados em `MEDIA_ROOT`.
4. Verificar que os sete analisadores existentes continuam disponíveis, mas que
   a tela lista apenas casos com vídeos presentes no dataset baixado.
5. Não alterar o comportamento do upload manual além das validações necessárias
   para separar os dois fluxos.

### 6. Testes e documentação

Adicionar ou atualizar testes diretamente em `backend/tests`, seguindo o padrão
de nomes existente:

- serviço: clone bem-sucedido, clone interrompido, estrutura inválida,
  idempotência e concorrência;
- API: status antes/depois do download, `202`, erro explícito e catálogo real;
- segurança de caminhos: traversal, arquivo inexistente, extensão inválida e
  caso incompatível;
- sessão: seleção de cada caso do dataset e rejeição de item não catalogado;
- frontend: estado inicial sem dataset, clique no download, erro, sucesso e
  seleção após download;
- regressão: upload manual, listagem de sessões e início da análise.

Atualizar `backend/README.md`, `frontend/README.md`, `README.md`, `api.http` e
eventuais documentos de arquitetura para refletir o novo fluxo. A documentação
deve deixar claro que o clone é feito pelo backend e que o dataset não é
embutido no bundle frontend.

## Critérios de aceite

- Em uma instalação limpa, a tela não mostra clipes fictícios nem permite iniciar
  uma análise via dataset antes do download.
- O botão **Download Dataset** aparece somente quando o dataset não está pronto.
- Um download concluído sobrevive à reinicialização dos containers e não é
  repetido ao abrir novamente a tela.
- Dois cliques ou duas requisições simultâneas não produzem clones concorrentes
  nem deixam um estado parcialmente publicado.
- O catálogo exibe somente vídeos reais dos quatro diretórios publicados no
  repositório e cada vídeo inicia a análise correspondente.
- Falhas de rede, Git, permissão, espaço ou validação são visíveis para o usuário
  e deixam o dataset marcado como não pronto/erro.
- O upload manual continua funcionando e o pipeline de análise, persistência e
  relatório não sofre regressão.

## Sequência sugerida de entrega

1. Remover fallback e consolidar o inventário de exercícios/clipes.
2. Implementar serviço de armazenamento/clone e cobertura unitária.
3. Expor status, download e catálogo na API.
4. Migrar o endpoint de referência para o catálogo gerenciado.
5. Alterar modal e cliente frontend.
6. Ajustar Docker, ambiente e documentação.
7. Executar testes backend/frontend e validar manualmente o fluxo em uma
   instalação limpa e em uma instalação com dataset já baixado.
