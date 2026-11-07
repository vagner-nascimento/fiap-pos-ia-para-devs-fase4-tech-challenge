# Frontend — Fisio Coach (React 19 & Vite)

interface web do sistema Fisio Coach para envio de vídeos de sessões, acompanhamento do processamento em tempo real, visualização de telemetria biomecânica, detecção de equipamentos e painel de alertas do fisioterapeuta.

> Para detalhes sobre a arquitetura integrada do sistema, consulte a [Documentação de Arquitetura](../docs/arquitetura/arquitetura-do-sistema.md).

## Estrutura e pacotes

```text
frontend/
├── index.html                 # Documento HTML5 e elemento #root
├── vite.config.js             # Configuração do Vite com proxy /api e /media
├── nginx.conf                 # Nginx de produção (proxy /api, /media e upload até 250MB)
├── Dockerfile                 # Build multi-stage (Node 20 + Nginx Alpine)
└── src/
    ├── tokens.css             # Design Tokens oficiais (--fc-* e Plus Jakarta Sans)
    ├── api/                   # Clientes REST desacoplados (patients.js, sessions.js, alerts.js, health.js)
    ├── components/            # Telas da jornada e componentes do Design System
    │   ├── ds/                # Componentes base: Button, Card, Field, StatusChip, StepList, Timeline, VideoPlayer
    │   ├── PlanAndReportView.jsx          # Tela 1 e 8: Cadastro de paciente, plano de exercícios (multi-dias) e laudo médico (Fisio)
    │   ├── PatientPrescriptionView.jsx    # Telas 2 e 3: Minha prescrição e envio de vídeos por dia/slot com termo LGPD (Paciente)
    │   ├── SessionsListView.jsx           # Listagem de sessões e modal de nova análise
    │   ├── ProcessingView.jsx             # Tela 4: Acompanhamento de processamento com polling
    │   ├── SessionReportView.jsx          # Tela 5: Relatório da sessão (vídeo, timeline, séries, dor, equipamento e laudo)
    │   ├── AlertsPanelView.jsx            # Tela 6: Painel de alertas clínicos com contadores e tratativa (Issue #7)
    │   └── PatientEvolutionReportView.jsx # Tela 7: Relatório final de evolução longitudinal multi-dias (Issue #7)
    ├── App.jsx                # Shell da aplicação com sidebar de 220px
    ├── main.jsx               # Bootstrap React com importação de tokens
    └── styles.css             # Estilos utilitários globais
```

## Integração e rotas da API

O frontend acessa o backend por meio das seguintes rotas REST e estáticas:

| Método | Caminho | Uso |
| --- | --- | --- |
| `GET` | `/api/health` | Obtém o status da API e do MongoDB para a tela de monitoramento. |
| `GET` / `POST` | `/api/pacientes` | Lista e cadastra pacientes sintéticos (com filtro `?nome=` insensível a acentos). |
| `GET` | `/api/pacientes/{id}` | Recupera dados consolidados do paciente (`patient`, `laudo`, `plano` e `sessoes_recentes`). |
| `GET` | `/api/pacientes/{id}/sessoes` | Lista o histórico de sessões enviadas/concluídas pelo paciente. |
| `POST` | `/api/pacientes/laudo/extrair` | Extrai entidades clínicas do texto do laudo em tempo real para conferência na UI. |
| `GET` / `POST` | `/api/pacientes/{id}/laudo` | Consulta e salva o laudo médico estruturado do paciente. |
| `GET` / `POST` | `/api/pacientes/{id}/plano` | Consulta e salva o plano de prescrição de exercícios (`dias_tratamento`, `dias_prescritos` por exercício, séries e repetições) e limites de dor/amplitude. |
| `GET` | `/api/pacientes/{id}/relatorio-evolucao` | Obtém o Relatório Final de Evolução Longitudinal do Paciente (Amplitude, Consistência e Nível de Dor por dia/exercício/série). |
| `POST` | `/api/pacientes/{id}/seed-evolucao` | Simula/popula a jornada multi-dias completa do paciente (3 dias de tratamento) para demonstração imediata. |
| `POST` | `/api/pacientes/{id}/avaliar-evolucao` | Registra a avaliação final longitudinal do fisioterapeuta/médico. |
| `GET` | `/api/pacientes/catalogo-exercicios` | Retorna o catálogo completo dos 7 exercícios clínicos (`FISIO-001` a `FISIO-007`). |
| `POST` | `/api/sessoes` | Envia upload de vídeo (`multipart/form-data`, até 200MB) por dia e slot (`dia_tratamento`, `slot_id`, `series_prescritas`, `repeticoes_por_serie`, `paciente_id`, `exercicio`/`exercicio_id`, `lgpd_aceite`) com progresso via `XMLHttpRequest` e inicia a análise (`202 Accepted`). |
| `POST` | `/api/sessoes/referencia` | Dispara análise a partir de clipe de dataset de referência via JSON (suportando `slot_id`, `dia_tratamento`, `series_prescritas`, `repeticoes_por_serie` e `lgpd_aceite`). |
| `GET` | `/api/sessoes/clips-referencia` | Alias de compatibilidade para o catálogo real do dataset baixado. |
| `GET` | `/api/datasets/fisio/status` | Consulta se o dataset oficial já foi baixado. |
| `POST` | `/api/datasets/fisio/download` | Solicita o download idempotente do dataset pelo backend. |
| `GET` | `/api/datasets/fisio/clips` | Lista os vídeos reais do dataset baixado. |
| `GET` | `/api/sessoes` | Lista as sessões do paciente com filtros, datas, scores e status. |
| `GET` | `/api/sessoes/{id}` | Recupera detalhes, classificação de risco e progresso da sessão (`current_step`, `current_step_index`, `total_steps`, `progress_percent`, `progress_message` e `processing_steps`). |
| `GET` | `/api/sessoes/{id}/eventos` | Recupera a linha do tempo de repetições e desvios posturais. |
| `GET` | `/api/sessoes/{id}/relatorio` | Payload estruturado para a tela de relatório individual e impressão médica. |
| `PATCH` | `/api/sessoes/{id}/avaliar` | Marca a sessão individual como avaliada pelo fisioterapeuta. |
| `GET` / `PATCH` | `/api/alertas` / `/api/alertas/{id}` | Lista alertas clínicos com contadores por severidade e atualiza o status (`novo`, `lido`, `tratado`). |
| `GET` | `/media/...` | Streaming de vídeos anotados H.264 (`annotated.mp4`) e snapshots fotográficos (`evidence/*.jpg`). |


Em desenvolvimento, o Vite encaminha `/api` para `http://localhost:3000`. No container, o Nginx encaminha `/api/` para `http://backend:3000` pela rede do Docker Compose; as demais requisições servem o bundle React e usam fallback para `index.html`. O backend também possui CORS liberado para comunicação direta no host.

O relatório exibe o vídeo anotado com landmarks, alertas e detecção do
equipamento na mesma camada visual. Para FISIO-006 e FISIO-007, o painel
**Equipamento** mostra o nome, o percentual total e a divisão entre não
detectado, parcialmente detectado e totalmente detectado. Para exercícios sem
equipamento, mostra somente **Nenhum**.

### Acompanhamento do processamento

`ProcessingView` consulta `GET /api/sessoes/{id}` a cada dois segundos enquanto
a sessão está `processando`. A lista de etapas vem do campo `processing_steps`
e o estado visual é derivado de `current_step_index` e `progress_percent`.
O backend publica seis etapas reais: vídeo recebido, extração de pose e
landmarks, análise biomecânica, transcrição de áudio e fala de dor, geração do
vídeo anotado/evidências e persistência/relatório.

O frontend ignora respostas de consultas que chegaram fora de ordem e mantém a
barra com o percentual real. Durante uma etapa ativa, um efeito visual indica
atividade sem inventar progresso. O chip de processamento não usa símbolo
adicional; exibe apenas o texto da etapa atual. Expressão facial e fusão com
plano/laudo não são exibidas porque não fazem parte do pipeline implementado.

## Configuração e variáveis de ambiente

| Variável | Uso | Padrão |
| --- | --- | --- |
| `VITE_BACKEND_API_URL` | URL base usada por `src/api/health.js` | `/api` |

Para chamar diretamente o backend no host, `.env.example` contém `VITE_BACKEND_API_URL=http://localhost:3000/api`. Copie o arquivo para `.env` no diretório `frontend` antes de iniciar o Vite. Variáveis com prefixo `VITE_` são incorporadas ao bundle e ficam visíveis no navegador; não coloque segredos nelas.

No Docker Compose, o frontend usa a configuração padrão `/api` e o proxy reverso do Nginx. A variável `VITE_BACKEND_API_URL` é lida durante o build Vite; o Compose atual não a configura.

## Executar localmente pelo terminal

Requisitos: Node.js 20 ou superior e npm. A partir da raiz do repositório:

```sh
cd frontend
npm ci
cp .env.example .env
npm run dev
```

No Windows PowerShell, para copiar o arquivo de exemplo use `Copy-Item .env.example .env`. Acesse a URL impressa pelo Vite, normalmente `http://localhost:5173`. Com a URL base padrão `/api`, o proxy exige que o backend esteja ativo em `http://localhost:3000`. Alternativamente, configure `VITE_BACKEND_API_URL=http://localhost:3000/api` no `.env` para chamar o backend diretamente.

Scripts adicionais:

```sh
npm run build    # gera o bundle de produção em dist/
npm run preview  # serve localmente o bundle gerado
```

## Executar o frontend em Docker

O modo integrado recomendado é iniciar os serviços a partir da raiz do repositório:

```sh
docker compose -f docker-compose.yaml up -d --build frontend backend mongodb
```

O container frontend constrói os arquivos estáticos com Node/Vite e os serve com Nginx. O host publica a porta `8080`, que encaminha para a porta `80` do Nginx. Acesse http://localhost:8080. O Nginx usa o nome de serviço `backend` para encaminhar `/api`.

Para construir e executar o frontend isoladamente, sem o backend Compose:

```sh
docker build -t fiap-pos-ia-frontend ./frontend
docker run --rm -p 8080:80 fiap-pos-ia-frontend
```

Nesse modo isolado, a página estática abre em `http://localhost:8080`, mas as chamadas `/api` só funcionarão se o Nginx conseguir alcançar um backend chamado `backend` na rede Docker. Para desenvolvimento local integrado, prefira executar `npm run dev` com o backend na porta 3000 ou subir o Compose completo.
