# Frontend — FIAP POS IA

Aplicação web de monitoramento construída com React 19 e Vite. A tela atual consulta o health check do backend e exibe o estado da API e do MongoDB, o horário da última consulta, a resposta recebida e o estado de carregamento/erro.

## Estrutura e pacotes

```text
frontend/
├── index.html                 # documento e elemento #root
├── vite.config.js             # plugin React e proxy local /api
├── nginx.conf                 # arquivos estáticos e proxy /api em Docker
├── Dockerfile                 # build Vite e imagem final Nginx
└── src/
    ├── api/health.js          # requisição HTTP do health check
    ├── App.jsx                # interface e estado da tela
    ├── main.jsx               # inicialização React e CSS global
    └── styles.css             # estilos globais
```

Mantenha as chamadas HTTP em `src/api`, separadas da apresentação. Conforme o frontend crescer, componentes reutilizáveis podem ser extraídos para `src/components`, páginas para `src/pages`, hooks compartilhados para `src/hooks` e recursos estáticos para `src/assets`.

## Integração e rotas

O frontend não declara rotas de navegação próprias. A tela atual acessa o backend por:

| Método | Caminho | Uso |
| --- | --- | --- |
| `GET` | `/api/health` | Obtém o status da API e do MongoDB para a tela de monitoramento. |

Em desenvolvimento, o Vite encaminha `/api` para `http://localhost:3000`. No container, o Nginx encaminha `/api/` para `http://backend:3000` pela rede do Docker Compose; as demais requisições servem o bundle React e usam fallback para `index.html`.

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
