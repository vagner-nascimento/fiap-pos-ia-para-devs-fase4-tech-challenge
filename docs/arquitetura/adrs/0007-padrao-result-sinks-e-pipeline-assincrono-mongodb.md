# ADR 0007: Padrão Result Sinks, Pipeline Assíncrono e Integração com MongoDB

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

Com a conclusão do motor de visão computacional (Passo 1), o pipeline passou a gerar resultados biomecânicos ricos:
1. Resumo executivo consolidado da sessão (`SessionSummary`);
2. Lista de eventos de repetições com timestamps, ângulos de pico e flags de validade;
3. Lista de eventos de desvios posturais com timestamps, severidades e caminhos para snapshots de evidência fotográfica;
4. Séries temporais de telemetria angular (`telemetry.json`);
5. Vídeo anotado com HUD responsivo (`annotated.mp4`).

Surgiu a necessidade de persistir esses dados de forma estruturada no MongoDB (Passo 2) atendendo aos seguintes requisitos de engenharia:
- **Desacoplamento Rigoroso:** O motor de visão (`VideoPoseProcessor`) não deve ter dependência direta do driver de banco de dados ou acoplamento com esquemas de persistência específicos;
- **Flexibilidade de Consumidores:** O sistema precisa permitir execução via CLI salvando apenas em disco, execução via API salvando no MongoDB, ou execução híbrida salvando em ambos simultaneamente;
- **Não-Bloqueio da API REST (UX):** O processamento de vídeos pesados de 30 FPS a 120 FPS via CPU pode levar de 5 a 60 segundos. A requisição HTTP `POST /api/sessoes` não pode ficar presa aguardando a finalização do MediaPipe sob risco de timeout em navegadores e proxies (Nginx);
- **Consumo Imediato pelo Frontend:** O frontend precisa de rotas para consultar status de processamento, exibir relatórios e carregar mídias pesadas (vídeos e imagens) sem trafegar binários embutidos no banco.

---

## 2. Decisão

Adotamos a seguinte arquitetura de persistência e integração assíncrona:

### 2.1 Padrão Strategy para Saídas (`ResultSink`)

Introduzimos a interface `ResultSink` em `backend/src/services/pose/sinks.py`:

```python
class ResultSink(ABC):
    @abstractmethod
    def save(self, result: ExerciseAnalysisResult, run_id: str, **kwargs) -> dict[str, Any]:
        pass
```

Implementamos três estratégias concretas:
1. **`FileResultSink`:** Responsável exclusivo por gravar `analysis.json` e `telemetry.json` na estrutura física de pastas gerenciada pelo `MediaStorage`;
2. **`MongoResultSink`:** Avalia as regras de negócio clínicas (classificação de risco explicável: `VERDE`, `ATENCAO`, `CRITICO`), transforma eventos biomecânicos em entidades documentais e persiste nas coleções `sessoes` e `eventos` via repositórios dedicados;
3. **`CompositeResultSink`:** Composição estrutural que executa uma cadeia sequencial de sinks sem duplicar lógica de transformação.

### 2.2 Camada de Repositórios Especializada

Criamos a camada de acesso a dados em `infra/database/repositories/`:
- **`SessionRepository`:** Executa operações atômicas de upsert (`update_one` com `upsert=True`), consultas filtradas por paciente e atualizações de status (`processando` -> `concluido` / `erro`);
- **`EventRepository`:** Executa gravação em lote (*batch insert* via `insert_many`) para dezenas de repetições e desvios de forma performática.

### 2.3 Pipeline Assíncrono com FastAPI `BackgroundTasks`

Na camada de transporte REST (`rest/routers/sessions.py`):
1. **`POST /api/sessoes` (multipart/form-data):** Recebe o arquivo de vídeo enviado pelo paciente ou clipe de referência;
2. **`POST /api/sessoes/referencia` (application/json):** Permite disparar execuções a partir de clipes sintéticos do dataset sem novo upload;
3. A rota inicializa o documento da sessão no MongoDB com status `processando` (`etapa: "video_received"`), agenda a tarefa de visão no `BackgroundTasks` e responde **imediatamente com status `202 Accepted`**. O worker atualiza incrementalmente a etapa, o índice, o percentual e a mensagem conforme o pipeline avança;
4. Parâmetro opcional `?sync=true` permite execução síncrona aguardando o processamento para scripts automatizados e testes de integração.

### 2.4 Servidor de Mídias Estáticas e Habilitação de CORS

- Montagem de rota estática `/media` no FastAPI mapeando diretamente o volume `data/` (`MEDIA_ROOT`), permitindo que o frontend carregue vídeos MP4 e imagens JPEG via URLs convencionais com suporte a *range requests*;
- Configuração de `CORSMiddleware` no servidor liberando conexões de origens web cruzadas (porta 8080 do container Nginx e portas locais de desenvolvimento).

---

## 3. Consequências

### Positivas
- **Acoplamento Zero:** O `VideoPoseProcessor` aceita qualquer implementação de `ResultSink` por injeção de dependência, facilitando testes unitários rápidos com mocks;
- **Resiliência a Timeouts:** O padrão de resposta `202 Accepted` com processamento em background garante que vídeos longos sejam processados sem quebrar conexões HTTP;
- **Rastreabilidade e Explicabilidade:** O `MongoResultSink` injeta justificativas textuais em português para o fisioterapeuta entender o motivo da classificação de risco;
- **Pronto para o Frontend:** As coleções `sessoes` e `eventos` fornecem ao frontend todos os dados para visualização de linha do tempo, listagens e detalhes.

### Negativas / Mitigações
- **Necessidade de Polling no Frontend:** Ao receber `202 Accepted`, o frontend precisa consultar periodicamente (`GET /api/sessoes/{id}`) para identificar quando o status mudar de `processando` para `concluido`.  
  *Mitigação:* As respostas de consulta são ultraleves (< 2 KB), permitindo intervalos de polling curtos (ex: a cada 2 segundos) até a finalização do processo.
