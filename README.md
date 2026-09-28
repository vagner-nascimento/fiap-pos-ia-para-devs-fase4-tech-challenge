# FIAP POS IA — Tech Challenge Fase 4

Aplicação web composta por um frontend React servido por Nginx, uma API FastAPI e um banco MongoDB. O frontend consulta a API para exibir o estado do serviço e da conexão com o banco.

## Componentes

| Componente | Tecnologia | Acesso local |
| --- | --- | --- |
| Frontend | React 19, Vite (build) e Nginx | http://localhost:8080 |
| Backend | Python 3.11, FastAPI e Uvicorn | http://localhost:3000 |
| Banco de dados | MongoDB 7 | `mongodb://localhost:27017` |

O backend monta suas rotas sob `/api`; o endpoint disponível é `GET /api/health`. O frontend chama essa rota e mostra os estados da API e do MongoDB.

## Executar a aplicação com Docker Compose

Requisitos: Docker Engine/Desktop com o plugin `docker compose`.

Na raiz do repositório:

```sh
docker compose -f docker-compose.yaml up -d --build
```

O Compose constrói as imagens do backend e do frontend e inicia também o MongoDB. O backend aguarda o health check do MongoDB; o frontend depende do início do backend. O Nginx do frontend encaminha `/api` para o serviço `backend` pela rede interna do Compose.

Acesse http://localhost:8080. Para verificar diretamente a API, acesse http://localhost:3000/api/health. Para acompanhar os serviços:

```sh
docker compose -f docker-compose.yaml ps
docker compose -f docker-compose.yaml logs -f
```

Para parar os containers:

```sh
docker compose -f docker-compose.yaml down
```

Os dados do MongoDB ficam no volume nomeado `mongodb_data` e persistem ao parar/remover os containers com `down`. Para apagar também os dados persistidos, use `docker compose -f docker-compose.yaml down -v`.

### Scripts de conveniência

Na raiz estão os scripts `start_app.sh`, `stop_app.sh` e `restart_app.sh`. Eles executam, respectivamente:

- `start_app.sh`: `docker compose -f docker-compose.yaml up -d --build` — constrói/reconstrói as imagens quando necessário e inicia os serviços em segundo plano.
- `stop_app.sh`: `docker compose -f docker-compose.yaml down` — para e remove containers e rede do projeto, preservando o volume do MongoDB.
- `restart_app.sh`: executa primeiro o comando de parada e depois o comando de inicialização/build.

Execute-os em um terminal compatível com shell POSIX (Linux, macOS, WSL ou Git Bash), a partir da raiz:

```sh
sh start_app.sh
sh stop_app.sh
sh restart_app.sh
```

Os scripts são atalhos para Docker Compose; também é possível executar os comandos equivalentes diretamente, como mostrado acima.

## Executar cada aplicação individualmente

Para instruções de desenvolvimento, pacotes, rotas, variáveis de ambiente e execução individual de cada serviço, consulte:

- [README do backend](backend/README.md)
- [README do frontend](frontend/README.md)

Ao executar frontend e backend fora do Compose, deixe o MongoDB acessível ao backend. Se não houver um MongoDB local instalado, pode iniciar apenas o banco pelo Compose com `docker compose -f docker-compose.yaml up -d mongodb`.
