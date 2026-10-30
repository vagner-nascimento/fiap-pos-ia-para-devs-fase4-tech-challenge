# ADR 0006: Adoção do MongoDB 7 para Persistência Documental e Telemetria

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

O sistema Fisio Coach manipula dados clínicos e biomecânicos com características distintas:
1. **Dados semiestruturados e polimórficos:** Laudos ortopédicos e prescrições de fisioterapia variam amplamente em termos de articulações afetadas, limites prescritos e detalhes textuais;
2. **Séries temporais variáveis:** Cada sessão gravada possui duração arbitrária e gera milhares de pontos de telemetria contendo timestamps, ângulos medidos, fases de movimento e flags de visibilidade;
3. **Eventos aninhados com metadados ricos:** Repetições registradas contêm tempos de início, pico e fim, além de listas de desvios posturais com evidências fotográficas vinculadas;
4. **Infraestrutura pré-estabelecida:** O boilerplate do Tech Challenge já fornecia o serviço MongoDB 7 pré-configurado no `docker-compose.yaml`.

---

## 2. Decisão

Confirmamos o uso do **MongoDB 7** como o banco de dados principal da aplicação, utilizando o driver assíncrono `Motor` no FastAPI para acesso às coleções.

### Modelagem Documental Adotada

Organizamos os dados nas seguintes coleções otimizadas:
1. **`pacientes`:** Cadastro básico do paciente e histórico clínico;
2. **`planos`:** Prescrição do fisioterapeuta contendo lista de exercícios, repetições alvo, limiares de amplitude mínima/máxima e dor máxima tolerável;
3. **`laudos`:** Diagnóstico ortopédico com regiões anatômicas contraindicadas e amplitudes seguras;
4. **`sessoes`:** Documento central agregando metadados da sessão, status (`enviado`, `processando`, `concluido`, `erro`), resultado consolidado (`ExerciseAnalysisResult`), matriz de risco (`verde`, `atencao`, `critico`) e referências aos arquivos no `MediaStorage`;
5. **`telemetria`:** Coleção com índices compostos por `session_id` e `timestamp` para consultas eficientes na renderização dos gráficos temporais no frontend.

---

## 3. Consequências

### Positivas
- **Flexibilidade de Esquema (Schema-on-Read):** Adaptação imediata a novas métricas biomecânicas ou dados de fusão multimodal (como picos de dor de áudio/face) sem necessidade de migrações complexas de esquema relacional;
- **Desempenho em Consultas Aninhadas:** Possibilidade de recuperar em uma única leitura atômica o resumo completo da sessão com todas as repetições e desvios associados;
- **Integração com Pydantic:** Mapeamento direto entre os modelos Pydantic (`SessionSummary`, `ExerciseAnalysisResult`) e documentos BSON do MongoDB via `model_dump()`.

### Negativas / Mitigações
- **Armazenamento de Séries Temporais Grandes:** Sessões muito longas com centenas de frames poderiam exceder o limite de 16 MB por documento no BSON caso a telemetria completa fosse embutida diretamente no documento da sessão.  
  *Mitigação:* A telemetria detalhada frame a frame é salva em arquivo JSON dedicado (`telemetry.json`) sob `MediaStorage`, mantendo o documento da sessão no MongoDB conciso e rápido, armazenando apenas o resumo executivo no banco.
