# Backend — FIAP POS IA

API REST em Python 3.11 usando FastAPI e Uvicorn. A aplicação expõe atualmente um health check que verifica a conexão com MongoDB.

## Estrutura e pacotes

```text
src/
├── infra/
│   ├── azure/                         # ponto reservado para integrações Azure
│   └── database/
│       ├── mongodb_client.py          # cliente, conexão e acesso a collections
│       └── repositories/              # ponto reservado para repositories
├── mappers/                           # ponto reservado para conversões entre modelos
├── models/
│   ├── database/                      # ponto reservado para modelos MongoDB
│   └── rest/health.py                 # resposta do health check
├── observability/logger.py            # configuração de logging
├── rest/routers/
│   ├── __init__.py                    # descoberta e registro de rotas
│   └── health.py                      # endpoint de health
├── services/                          # ponto reservado para regras de negócio
├── main.py                            # carrega ambiente e inicia Uvicorn
└── server.py                          # cria/configura FastAPI e monta routers
```

`server.py` cria a aplicação FastAPI e monta as rotas sob `/api`. O `main.py` carrega o `.env` com `python-dotenv` e inicia o servidor na porta 3000. No startup, o lifespan configura o logger e verifica a disponibilidade do MongoDB; se a conexão falhar, o startup falha.

Os diretórios reservados representam a arquitetura pretendida, não integrações já implementadas. Para endpoints de negócio, mantenha a separação router → service → repository/infra. Os contratos HTTP ficam em `models/rest` e devem usar `pydantic.BaseModel` e `Field` com descrições e validações adequadas.

## Rotas atuais

| Método | Caminho | Descrição |
| --- | --- | --- |
| `GET` | `/api/health` | Retorna status da aplicação, timestamp e estado do MongoDB. |

O response segue o modelo `HealthResponse`, com os campos `status`, `timestamp` e `database`. A documentação OpenAPI do FastAPI fica disponível em `/docs` e `/openapi.json` na aplicação principal.

## Configuração e variáveis de ambiente

Copie `.env.example` para `.env` no diretório `backend` e ajuste os valores para o ambiente local:

```dotenv
MONGO_DB_SERVER=mongodb://localhost:27017
MONGO_DB_USER=fiap-pos-ia-user
MONGO_DB_PASSWORD=fiap-pos-ia-password
MONGO_DB_NAME=fiap-pos-ia-db
```

| Variável | Uso | Padrão no código |
| --- | --- | --- |
| `MONGO_DB_SERVER` | URI do servidor MongoDB | `mongodb://localhost:27017` |
| `MONGO_DB_USER` | Usuário enviado ao driver MongoDB | Sem usuário |
| `MONGO_DB_PASSWORD` | Senha enviada ao driver MongoDB | Sem senha |
| `MONGO_DB_NAME` | Banco usado por `get_collection` | `fiap-pos-ia-db` |

O `.env` é carregado pelo `main.py` ao iniciar pelo comando documentado abaixo. Não versione credenciais reais. No Docker Compose, as variáveis são configuradas no próprio `docker-compose.yaml` e `MONGO_DB_SERVER` usa o hostname de serviço `mongodb`.

## Executar localmente pelo terminal

Requisitos: Python 3.11 ou superior, `uv` e um MongoDB acessível. A partir da raiz do repositório:

```sh
cd backend
cp .env.example .env
uv sync
uv run python -m src.main
```

No Windows PowerShell, o comando de cópia pode ser `Copy-Item .env.example .env`. O servidor inicia em `http://localhost:3000`; a rota é `http://localhost:3000/api/health`. O MongoDB precisa estar disponível antes do início do backend.

Para iniciar somente o MongoDB usando o Compose da raiz, execute na raiz do repositório:

```sh
docker compose -f docker-compose.yaml up -d mongodb
```

## Executar o backend em Docker

Na raiz do repositório:

```sh
docker compose -f docker-compose.yaml up -d --build backend mongodb
```

O serviço do backend é publicado na porta `3000` do host, e o Compose configura a URI MongoDB apropriada para comunicação entre containers. O Dockerfile constrói a aplicação com Python 3.11 e `uv`. Para logs e parada, use:

```sh
docker compose -f docker-compose.yaml logs -f backend
docker compose -f docker-compose.yaml stop backend mongodb
```

Para executar diretamente via Docker Compose, o MongoDB deve estar disponível; o serviço `backend` declara dependência com condição de health check do banco.
