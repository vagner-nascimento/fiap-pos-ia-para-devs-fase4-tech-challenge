# Fisio Coach
## Relatório Técnico - Tech Challenge Fase 4

**Curso:** FIAP Pos-Tech IA para Devs  
**Projeto:** Fisio Coach  
**Versão do relatório:** 1.0  
**Data:** novembro de 2026  
**Repositorio:** fiap-pos-ia-para-devs-fase4-tech-challenge

> Este documento descreve a implementação existente no repositório. Quando um resultado quantitativo de acurácia ou latência não está medido por benchmark versionado, o texto identifica a evidência como funcional/estrutural, sem apresentar números estimados como se fossem métricas experimentais.

---

## Resumo executivo

O Fisio Coach e uma plataforma multimodal para apoio ao fisioterapeuta no acompanhamento remoto de sessões de reabilitação. A entrada principal e um vídeo gravado pelo paciente, contendo imagem, movimento e, quando disponível, a fala relacionada a dor. O sistema combina quatro fontes de informação:

1. **Vídeo:** landmarks corporais, ângulos articulares, fases do movimento, repetições, desvios biomecânicos e equipamentos.
2. **Áudio:** extração da trilha, transcrição local em português e classificação de relatos de dor/desconforto com timestamps.
3. **Texto clínico:** laudo e prescrição estruturados a partir de texto em português, com limites de movimento, dor aceitável e exercícios prescritos.
4. **Histórico:** comparação de sessões ao longo dos dias, produzindo indicadores de amplitude, consistência e dor.

Os resultados são persistidos em arquivos e MongoDB, apresentados em relatórios de sessão e evolução, e convertidos em alertas com severidade `verde`, `atencao` ou `critico`. O frontend apresenta o vídeo anotado, a linha do tempo de eventos, evidências fotográficas e o painel de alertas.

A solução atende diretamente ao núcleo de análise de vídeo, áudio, texto, anomalias e fusão multimodal. Há uma diferença importante em relação ao enunciado: a implementação atual usa Faster-Whisper local e um classificador determinístico de domínio, em vez de Azure Speech to Text e Azure Text Analytics. Essa decisão está documentada nos ADRs e prioriza custo zero, reprodutibilidade e execução local. A integração Azure permanece como extensão planejada, e não é apresentada neste relatório como funcionalidade concluída.

---

## 1. Contexto, objetivo e escopo

O desafio da Fase 4 propõe integrar IA a processos médicos, analisando dados multimodais para identificar sinais precoces de risco e alertar a equipe. O recorte escolhido foi o acompanhamento de exercícios de fisioterapia, no qual o paciente grava uma sessão e o fisioterapeuta precisa verificar se o movimento foi executado conforme a prescrição.

### 1.1 Objetivo do produto

O objetivo do Fisio Coach e reduzir o trabalho manual de revisão de sessões, oferecendo ao profissional:

- contagem automática de repetições;
- verificacao de amplitude e fase do movimento;
- identificacao de compensacoes biomecanicas;
- verificacao de equipamento quando aplicável;
- correlação entre eventos do vídeo e relatos de dor;
- comparação longitudinal entre dias de tratamento;
- evidências auditáveis para justificar cada alerta.

O sistema não substitui avaliação clínica. Ele produz sinais, medidas e evidências para apoiar a decisão do fisioterapeuta.

### 1.2 Escopo implementado

O MVP suporta quatro exercícios:

| Codigo | Exercício |
|---|---|
| FISIO-001 | Extensao de joelho sentado |
| FISIO-002 | Pendulo de ombro (Codman) |
| FISIO-006 | Abdução de ombro com elástico |
| FISIO-007 | Flexao de cotovelo com halter |

A aplicação suporta cadastro de paciente, laudo, prescrição, upload por slot prescrito, processamento assíncrono, relatório individual, evolução longitudinal e painel de alertas. O armazenamento de demonstração usa dados sintéticos.

### 1.3 Fora do escopo atual

Não fazem parte da implementação atual:

- análise de cirurgias;
- sinais vitais como batimentos, pressão arterial e oxigenação;
- diagnóstico médico;
- treinamento de um modelo próprio de visão ou fala durante a execução;
- integração efetiva com Azure Cognitive Services;
- garantia clínica de acurácia sem validação com dataset anotado e avaliação profissional.

---

## 2. Aderencia aos entregáveis da Fase 4

O edital solicita repositório Git, relatório técnico com fluxo multimodal, modelos aplicados e resultados/exemplos de anomalias, além de vídeo demonstrativo. Este arquivo é o relatório técnico do repositório. O vídeo de demonstração será entregue separadamente, conforme a orientação do edital; o link não fica no repositório e, por isso, não é incorporado a este documento.

| Entregavel ou requisito | Evidência no projeto | Situacao |
|---|---|---|
| Repositorio com código-fonte | Backend FastAPI, frontend React/Vite, Docker Compose, testes e documentacao | Implementado |
| Fluxo multimodal | Pipeline de vídeo, áudio, texto clínico e evolução | Implementado |
| Modelos de vídeo | MediaPipe Pose, analisadores de exercício e YOLO para equipamentos | Implementado |
| Modelos de áudio | Faster-Whisper local e regras de classificação de dor | Implementado com substituição local |
| Resultados e exemplos de anomalias | Relatórios JSON, vídeo anotado, telemetria, snapshots e alertas | Implementado |
| Alertas automáticos | Severidade e persistência em `alertas`, painel web | Implementado |
| Azure Speech to Text | Não há cliente Azure no código atual | Não implementado, justificativa na seção 9 |
| Azure Text Analytics | Não há cliente Azure no código atual | Não implementado, justificativa na seção 9 |
| Vídeo de até 15 minutos | Será entregue separadamente, fora do repositório | Entrega externa ao repositório |

---

## 3. Arquitetura da solução

### 3.1 Componentes

A aplicação e executada com Docker Compose em tres serviços principais:

- **Frontend:** React 19, Vite e Nginx, exposto na porta 8080.
- **Backend:** Python 3.11, FastAPI e motor de IA, exposto na porta 3000.
- **MongoDB:** MongoDB 7 para persistência, exposto na porta 27017.

O diretório `data` e montado como armazenamento persistente para vídeos originais, vídeos anotados, snapshots e arquivos JSON.

O backend separa as responsabilidades entre routers REST, services, motor de pose, motor de áudio, repositórios, armazenamento de mídia e sinks de resultado. O processamento pode gravar simultaneamente em disco e banco por meio do `CompositeResultSink`.

### 3.2 Fluxo ponta a ponta

![Diagrama do fluxo multimodal ponta a ponta](fluxo-ponta-a-ponta.svg)

A API retorna `202 Accepted` para o processamento assíncrono. O frontend consulta o status e atualiza o progresso até a conclusão ou erro.

### 3.3 Persistência e rastreabilidade

As principais coleções MongoDB são:

- `pacientes`: dados cadastrais sintéticos;
- `laudos`: região, lesão, restrições e limites angulares;
- `planos`: dias, exercícios, séries, repetições, lado, equipamento e dor máxima;
- `sessoes`: status, metadados, métricas, consentimento e referências de mídia;
- `eventos`: repetições, desvios, evidências e falas relacionadas a dor;
- `alertas`: severidade, justificativa, status e vínculo com paciente/sessão.

Cada execução também pode produzir:

- `annotated.mp4`: vídeo com esqueleto, HUD, eventos e equipamento;
- `analysis.json`: resumo executivo estruturado;
- `telemetry.json`: série temporal de medidas;
- `evidence/*.jpg`: quadros que comprovam desvios.

---

## 4. Modelos e técnicas aplicados

### 4.1 Vídeo e postura

O `MediaPipe Pose` extrai 33 landmarks corporais. As coordenadas são normalizadas e usadas para calcular ângulos e distancias por geometria 2D. O pipeline identifica o lado ativo automaticamente quando o exercício permite, considerando visibilidade e amplitude observada.

A detecção de repetições usa uma máquina de estados com fases de repouso, movimento concêntrico, pico e movimento excêntrico. Interpolacao de gaps e suavização reduzem o impacto de oclusões momentâneas e ruído. A histerese evita que oscilações próximas do limiar sejam contadas como repetições adicionais.

O padrão Strategy permite que cada exercício implemente seus ângulos primários e suas regras de desvio sem duplicar o pipeline comum. Os quatro analisadores ativos ficam registrados em um catálogo de exercícios.

### 4.2 Objetos e equipamentos

O detector baseado em YOLO usa o modelo `best.pt` para reconhecer os equipamentos relevantes nos exercícios FISIO-006 e FISIO-007:

- `faixa_elastica`;
- `halter`.

O resultado e associado aos frames e agregado no relatório. O HUD mostra a caixa e o status do equipamento; a ausência ou baixa cobertura pode gerar um achado de execução.

### 4.3 Áudio e fala

A trilha de áudio e extraída e convertida para mono, 16 kHz, com redução de ruído e normalização. O `Faster-Whisper` realiza a transcrição local em português. O resultado preserva timestamps para a fusão temporal com repetições e desvios.

A classificação de dor e determinística e orientada ao domínio. As categorias são:

- `pouca_ou_nenhuma_dor`;
- `desconforto`;
- `dor`;
- `muita_dor`.

As regras consideram termos e precedencia de negacao para reduzir classificacoes falsas em frases como “não estou com dor”. O resultado não e um modelo clínico de sentimento geral; e um classificador explicável para relatos de dor e desconforto.

### 4.4 Texto clínico

O extrator clínico interpreta laudo e prescrição em português para obter campos estruturados, como região anatômica, lesão, movimentos restritos, limites angulares, dias de tratamento, exercícios, séries, repetições e dor máxima aceitável.

Esses dados funcionam como contexto para avaliar se uma sessão está dentro da prescrição. A mesma medida biomecânica pode ser aceitável para um paciente e gerar alerta para outro, dependendo do limite registrado.

### 4.5 Evolucao e anomalias

A avaliação longitudinal organiza as sessões por dia, exercício, série e repetição. Os indicadores principais são:

- **Amplitude articular:** medida em graus, comparada a faixa esperada;
- **Consistencia biomecânica:** escore de 0 a 100% derivado da regularidade das execuções;
- **Dor:** escore de 0 a 10 obtido da prescrição e dos relatos classificados.

As regras de alerta combinam violação de limite angular, compensação, repetição inválida, dor acima do limite e tendência desfavorável na evolução. A situação adequada é apresentada visualmente na cor verde; os estados de alerta são `atencao` e `critico`, sempre com justificativa persistida para permitir revisão humana.

---

## 5. Exemplos de anomalias detectadas

Os exemplos abaixo representam os tipos de achado gerados pela implementação e seus artefatos de evidência. Eles descrevem o comportamento funcional e não devem ser interpretados como estatística de desempenho clínico.

### 5.1 Desvio de amplitude ou limite angular

Quando o ângulo calculado ultrapassa o limite do laudo ou fica fora da faixa prescrita, o evento recebe referencia temporal, exercício, repetição e evidência fotográfica. O relatório pode indicar a amplitude observada, o limite aplicável e a recomendação de revisão pelo fisioterapeuta.

**Evidência produzida:** evento em `eventos`, registro em `analysis.json`, quadro em `evidence/*.jpg` e marcador no vídeo anotado.

### 5.2 Compensacao postural

Os analisadores verificam regras especificas do exercício, como inclinacao de tronco, assimetria, movimento de segmento não desejado ou falha da fase esperada. O achado e vinculado ao ciclo ou frame em que ocorreu.

**Resposta do sistema:** a repetição pode ser marcada como inválida, o motivo aparece na timeline e a severidade e recalculada para o resumo da sessão.

### 5.3 Dor relatada durante a execução

Uma fala transcrita como “estou com muita dor” e associada ao timestamp do áudio. O segmento passa a compor a timeline multimodal e pode elevar o risco quando supera a dor máxima definida na prescrição.

**Resposta do sistema:** o evento `fala_dor` é persistido, aparece junto ao player e pode alimentar alerta `atencao` ou `critico`, conforme a regra configurada.

### 5.4 Equipamento ausente ou inadequado

Nos exercícios com faixa elastica ou halter, o detector verifica a presença do objeto. A cobertura temporal e o status são agregados no relatório. Um resultado inconsistente e uma evidência para revisão da sessão, sem afirmar sozinho que o movimento foi clínicamente incorreto.

### 5.5 Piora longitudinal

Se a amplitude diminui, a consistência cai ou a dor aumenta ao longo dos dias, o servico de evolução registra a tendencia e gera alerta para o painel do fisioterapeuta. O alerta mantém a justificativa e a relação com as sessões que o originaram.

---

## 6. Interface e jornada do usuario

### 6.1 Paciente

1. Consulta a prescrição e os slots do dia.
2. Envia o vídeo correspondente ao exercício.
3. Confirma o consentimento LGPD da sessão.
4. Acompanha o processamento.
5. Consulta o resultado liberado pela aplicação.

### 6.2 Fisioterapeuta

1. Cadastra paciente e laudo.
2. Registra ou revisa a prescrição estruturada.
3. Consulta sessões e relatórios individuais.
4. Reproduz o vídeo anotado com timeline sincronizada.
5. Inspeciona snapshots e métricas.
6. Consulta evolução multi-dias.
7. Le, marca e trata alertas.

### 6.3 Privacidade e governanca

O upload exige aceite explícito de consentimento por sessão. A demonstração utiliza dados sintéticos e mantém as mídias separadas por identificador de execução. O sistema foi desenhado como apoio a decisão, com justificativas e evidências para revisão profissional, sem automatizar diagnóstico.

---

## 7. Execução e reproducibilidade

### 7.1 Execução completa

Na raiz do repositório:

```sh
sh start_app.sh
```

Ou diretamente:

```sh
docker compose -f docker-compose.yaml up -d --build
```

Acessos:

- Frontend: `http://localhost:8080`
- OpenAPI: `http://localhost:3000/docs`
- Health check: `http://localhost:3000/api/health`
- MongoDB: `mongodb://localhost:27017`

Para encerrar ou reiniciar:

```sh
sh stop_app.sh
sh restart_app.sh
```

### 7.2 Execução do backend e testes

O backend requer Python `>=3.11,<3.13` e usa `uv` no fluxo documentado:

```sh
cd backend
uv sync
uv run pytest tests -v
```

A suite cobre transcrição, dataset, geometria, repetições, analisadores, processador de vídeo, YOLO, HUD, armazenamento de mídia, progresso, APIs de sessão, pacientes, evolução e alertas. Os arquivos de configuração do repositório declaram 147 testes automatizados.

### 7.3 Execução CLI de um vídeo

```sh
uv run ./backend/src/cli/analyze_video.py \
  --video /caminho/para/video.mp4 \
  --case FISIO-001 \
  --side auto \
  --target-reps 5 \
  --run-id sessao_teste_01
```

Para cada caso, o resultado deve ser inspecionado junto com o vídeo anotado, o JSON executivo, a telemetria e as evidências. A interpretação clínica continua sendo responsabilidade do profissional.

### 7.4 Frontend isolado

```sh
cd frontend
npm ci
npm run build
npm run dev
```

---

## 8. Validacao, resultados e limites da evidência

### 8.1 Evidencias de implementação

O repositório contem:

- código dos quatro analisadores ativos (FISIO-001, FISIO-002, FISIO-006 e FISIO-007);
- testes unitarios e de integração;
- diretórios de saida de sessões com resultados de pose;
- documentacao de arquitetura e ADRs;
- endpoints HTTP documentados em `api.http`;
- componentes web para relatório individual, evolução e alertas.

Isso comprova a existência do fluxo implementado e permite uma demonstração reproduzível. Não substitui, porém, uma avaliação de acurácia contra ground truth clínico.

### 8.2 Plano e resultados da validação experimental

Para complementar as evidências de implementação, o repositório mantém o documento **Plano e Resultados da Validação Experimental**. Seu conteúdo foi incorporado a esta seção como registro do protocolo, das medições e dos resultados observados nas execuções reais.

#### 8.2.1 Escopo e protocolo

O protocolo avalia oito quesitos do pipeline multimodal: precisão, recall e F1 por exercício e desvio; erro de contagem de repetições; Word Error Rate (WER) da transcrição; classificação de dor; detecção de equipamentos; latência em CPU; taxa de falha sob condições de qualidade, oclusão e iluminação; e concordância entre alertas e avaliação de fisioterapeutas.

As execuções reais descritas no plano cobrem FISIO-001, FISIO-006 e FISIO-007. FISIO-002 possui sessão preliminar sem rotulagem temporal fina. Os resultados de FISIO-003, FISIO-004 e FISIO-005 presentes no documento original não são tratados como escopo ativo deste relatório, que considera apenas FISIO-001, FISIO-002, FISIO-006 e FISIO-007.

#### 8.2.2 Precisão de desvios e equipamentos

| Exercício | Achado avaliado | Base | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| FISIO-001 | `amplitude_reduzida` | 6 repetições | 100,0% | 100,0% | 1,00 |
| FISIO-001 | `inclinacao_tronco` | 5 repetições | 80,0% | 80,0% | 0,80 |
| FISIO-001 | `velocidade_irregular` | 5 repetições | 80,0% | 80,0% | 0,80 |
| FISIO-006 | `inclinacao_tronco` | 16 repetições | 100,0% | 100,0% | 1,00 |
| FISIO-006 | `faixa_elastica` via YOLO | 4 vídeos | 100,0% | 100,0% | 1,00 |
| FISIO-007 | `amplitude_reduzida` | 16 repetições | 91,7% | 100,0% | 0,96 |
| FISIO-007 | `balanco_tronco` | 16 repetições | 100,0% | 100,0% | 1,00 |
| FISIO-007 | `halter` via YOLO | 5 vídeos | 100,0% | 100,0% | 1,00 |
| **Média ponderada** | **Desvios em vídeos reais** | **52 repetições** | **93,9%** | **96,9%** | **0,95** |

Nos vídeos reais, a faixa elástica foi detectada em 83,8% dos frames avaliados e o halter em 61,8%. O checkpoint YOLO11 Nano foi treinado externamente à API com 23 imagens rotuladas e é utilizado apenas para inferência em CPU.

#### 8.2.3 Erro de contagem de repetições

A base experimental totaliza 52 repetições avaliadas nos três exercícios com vídeos rotulados. O plano registra **MAE = 0,06 repetição por série** e **OEC = 1,1%**, abaixo da meta de 10% definida no PRD. FISIO-006 e FISIO-007 apresentaram aderência exata aos ciclos encenados nas sessões avaliadas.

#### 8.2.4 Transcrição e classificação de dor

O benchmark de áudio clínico registrou WER médio ponderado de **4,2%**. Os cenários de dor aguda, desconforto, dor residual e ausência de dor obtiveram 0,0% individualmente; o cenário ruidoso obteve 12,5%.

Para a classificação determinística de dor, a matriz experimental registrou **93,7% de acurácia exata** e **100,0% de tolerância clínica em até um nível**, acima da meta de 80% do PRD. A avaliação considera as classes `pouca_ou_nenhuma_dor`, `desconforto`, `dor`, `muita_dor` e `indeterminado`.

#### 8.2.5 Latência em CPU

Para um minuto de vídeo a 30 fps, o plano registrou **67,4 segundos** para FISIO-001 e **85,8 segundos** para FISIO-006/007. Os fatores de tempo real foram, respectivamente, **RTF = 1,12** e **RTF = 1,43**. A latência registrada para emissão do alerta no painel foi inferior a dois segundos após a fusão.

#### 8.2.6 Robustez e concordância de alertas

Nas sessões de FISIO-006 e FISIO-007, foram analisados 6.580 frames sem perda de pose quando o paciente permaneceu enquadrado. O protocolo de estresse também registrou aumento de perdas em baixa resolução, oclusão física e contraluz, com marcação de sessão inconclusiva quando o tronco ficou majoritariamente fora do quadro.

Em um painel simulado com 30 sessões, a concordância absoluta entre o sistema e fisioterapeutas foi de **90,0%**, com **Kappa de Cohen = 0,848**. Não foram observados falsos negativos críticos no conjunto avaliado.

#### 8.2.7 Interpretação dos resultados

As métricas acima são resultados experimentais do protocolo descrito no documento de validação e não uma garantia de desempenho clínico geral. A base é pequena, sintética e concentrada em condições controladas. Os resultados sustentam a demonstração técnica do pipeline, mas o uso clínico exigiria ampliação da amostra, separação entre treino, validação e teste, rotulagem independente e avaliação por profissionais de saúde.

### 8.3 Riscos conhecidos

- Camera, iluminacao, roupa e oclusao podem reduzir a qualidade dos landmarks.
- A classificação por regras não cobre todo o vocabulário de dor, fadiga ou dificuldade respiratoria.
- Whisper local depende da qualidade do áudio e do modelo escolhido.
- YOLO depende do domínio representado no modelo `best.pt`.
- A execução local em CPU pode aumentar o tempo de processamento.
- Dados sintéticos não representam a variabilidade de pacientes reais.
- Alertas são sinais de apoio e precisam de validação profissional.

---

## 9. Lacunas em relação ao edital e plano de evolução

### 9.1 Justificativa para não usar Azure nesta versão

O edital cita Azure Speech to Text e Azure Text Analytics. A equipe avaliou essa alternativa, mas decidiu não depender de recursos Azure na versão demonstrativa por uma combinacao de restrições de custo, infraestrutura, privacidade e reproducibilidade. Essa escolha está registrada nos ADRs 0010 (Faster-Whisper), 0011 (detecção de dor por transcrição) e 0012 (extração de laudos e prescrições).

#### Criterios da decisão

1. **Orcamento da demonstração:** o projeto não possui orçamento para serviços de nuvem. O uso de APIs gerenciadas introduziria custo recorrente por volume de áudio, texto e chamadas, enquanto as alternativas locais não possuem custo por requisição.
2. **Reproducibilidade:** a entrega precisa ser executavel por avaliadores com `docker compose up`, sem criar conta, provisionar recurso, cadastrar endpoint ou configurar chave de API. Os modelos e regras locais permitem repetir a demonstração com a mesma entrada e o mesmo contrato de dados.
3. **Execução em CPU:** MediaPipe Pose, YOLO e Faster-Whisper foram configurados para CPU, com PyTorch/Torchvision CPU-only e Whisper em `int8`. Isso evita GPU dedicada, CUDA e custos de instâncias de GPU na nuvem.
4. **Privacidade e LGPD:** áudio, transcrições, laudos e prescrições permanecem no ambiente local. Assim, a demonstração não precisa enviar dados de saúde a um provedor externo; o projeto ainda usa dados sintéticos e registra o consentimento por sessão.
5. **Explicabilidade:** a dor e extraída de segmentos transcritos com timestamps, normalização e regras de domínio, incluindo precedencia de negacao. O laudo usa extração determinística e revisão humana antes da persistência. O profissional consegue ver o texto e revisar os campos, em vez de receber apenas uma classificação opaca.
6. **Testabilidade:** os componentes locais são determinísticos o suficiente para testes unitarios, sem flutuação causada por rede, indisponibilidade, limite de quota ou mudanca de modelo remoto durante a avaliação.
7. **Complexidade operacional:** Azure exigiria credenciais, configuração de recursos, observabilidade, tratamento de falhas de rede e controle de segredos. Remover essa dependencia manteve o backend portável entre máquina local e container Docker.

#### Recursos locais escolhidos

| Necessidade | Recurso local | Motivo da escolha |
|---|---|---|
| Landmarks e postura | MediaPipe Pose | Roda em CPU, possui wheel Python, 33 landmarks e licenca permissiva; evita a dependencia de CUDA e a compilacao complexa do OpenPose (ADR 0001). |
| Equipamentos | YOLO com `best.pt` | Detecta apenas `faixa_elastica` e `halter` nos exercícios FISIO-006 e FISIO-007, em CPU, sem chamada externa (ADR 0009). |
| Transcrição | Faster-Whisper local | Mantém áudio e timestamps no ambiente local, sem custo por requisição, rede ou credenciais (ADR 0010). |
| Dor na fala | Regras determinísticas sobre a transcrição | E explicável, reproduzível e adequado ao vocabulario restrito da demonstração; não exige um classificador clínico ou NLP em nuvem (ADR 0011). |
| Laudo e prescrição | `clinical_extractor.py` + revisão humana | Extrai campos em português sem serviço pago e permite correção pelo fisioterapeuta antes de salvar (ADR 0012). |
| Persistência e execução | MongoDB, Docker Compose e armazenamento em `data/` | Mantém a stack local, auditavel e reproduzível, sem depender de banco ou armazenamento gerenciado. |

“Gratuito” neste contexto significa sem tarifa de servico por requisição e baseado em componentes locais/open source ou em artefatos do próprio projeto. Isso não elimina custos de hardware, energia, armazenamento ou manutencao, nem representa uma afirmacao de que todos os componentes possuem a mesma licenca.

#### Trade-offs aceitos

A decisão reduz escalabilidade e pode aumentar a latência em CPU em comparação com uma API cloud. O Whisper local também pode errar em ruído, sotaques e falas sobrepostas; as regras de dor não compreendem toda nuance clínica; e o extrator de laudos cobre apenas o vocabulario mapeado. Por isso, os resultados são apoio a decisão, não diagnóstico, e precisam de validação com dados anotados e profissionais de saúde antes de uso clínico.

### 9.2 Azure Cognitive Services como evolução compativel

A decisão local não fecha a porta para Azure. Para diversificar a cobertura dos requisitos em uma futura implantação, pode-se criar portas de transcrição e análise de linguagem com duas implementações:

- adaptador local para desenvolvimento, testes e modo offline;
- adaptador Azure selecionado por configuração para ambiente de demonstração ou produção.

As credenciais devem permanecer em variaveis de ambiente e nunca no frontend ou no repositório. O resultado dos dois adaptadores deve manter o mesmo contrato interno de segmentos, timestamps, texto e classificação, permitindo trocar o provedor sem alterar o frontend nem a persistência.

### 9.3 Sinais vitais

A arquitetura de anomalias poderia receber um modulo de séries temporais para batimentos, pressão e oxigenação, com janela, baseline individual e regras de ausência/outlier. Esse modulo poderia compartilhar o contrato de alerta, mas permanecer separado do analisador biomecanico.

---

## 10. Conclusao

O Fisio Coach entrega uma implementação funcional de acompanhamento multimodal para fisioterapia: processa vídeo e áudio, interpreta contexto textual, gera evidências, persiste resultados e transforma anomalias em alertas revisáveis. A arquitetura separa API, services, motores de IA, persistência e apresentação, permitindo evolução incremental.

O principal ponto de conformidade parcial e a camada de serviços Azure, substituida na versão atual por processamento local documentado. Essa limitacao está explícitada para que o avaliador diferencie o que foi implementado do que permanece como evolução. Dentro do recorte de fisioterapia e com dados sintéticos, o projeto oferece o fluxo técnico necessário para demonstrar análise multimodal, detecção de anomalias e apoio ao acompanhamento clínico.

---

## Referências do repositório

- `README.md`
- `docs/edital-tech-challenge-fase4.md`
- `docs/arquitetura/arquitetura-do-sistema.md`
- `docs/arquitetura/adrs/`
- `backend/src/services/pose/`
- `backend/src/services/audio_transcription.py`
- `backend/src/services/clinical_extractor.py`
- `backend/src/services/evolution_service.py`
- `backend/tests/`
- `frontend/src/`
- `docker-compose.yaml`
- `api.http`
