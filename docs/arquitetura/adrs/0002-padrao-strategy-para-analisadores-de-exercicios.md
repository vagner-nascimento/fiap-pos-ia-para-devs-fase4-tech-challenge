# ADR 0002: Padrão Strategy e Template Method para Analisadores de Exercícios

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

O sistema Fisio Coach necessita analisar múltiplos exercícios de fisioterapia (iniciando com 7 exercícios de referência do dataset sintético: FISIO-001 a FISIO-007). Cada exercício possui:
- Articulações-alvo e limites angulares específicos;
- Padrões de repetição distintos (movimentos de extensão, flexão, pêndulo, rotação);
- Regras clínicas de desvio postural exclusivas (ex.: inclinação de tronco, hiperlordose, compensação de ombro, movimento excessivamente rápido, membro fora de quadro).

Se essas regras fossem implementadas em funções monolíticas ou cheias de estruturas `if/elif` condicionais, o código rapidamente se tornaria frágil, difícil de testar e quase impossível de estender com novos exercícios.

---

## 2. Decisão

Adotamos a combinação dos padrões de projeto **Strategy** e **Template Method**:
1. Criamos a classe abstrata base `BaseExerciseAnalyzer`, responsável por fornecer o pipeline estrutural comum:
   - Pré-processamento e alinhamento dos frames (`PoseFrame`);
   - Interpolação de gaps de detecção e suavização de ruído por média móvel;
   - Algoritmo de histerese para detecção estável de repetições e fases do movimento (`repouso`, `concentrica`, `pico`, `excentrica`);
   - Resolução dinâmica do lado ativo do corpo (`BodySide.AUTO`, `RIGHT`, `LEFT`, `BOTH`);
   - Cálculo padronizado de métricas de conformidade e geração do relatório `ExerciseAnalysisResult`.
2. Para cada exercício do catálogo (`FISIO-001` a `FISIO-007`), implementamos uma subclasse concreta que herda de `BaseExerciseAnalyzer` e sobrescreve apenas os métodos de domínio específico:
   - `extract_primary_angle`: Extrai a métrica angular que rege o ciclo do exercício;
   - `check_deviations_frame`: Avalia desvios pontuais a cada frame;
   - `check_cycle_deviations`: Avalia desvios consolidados ao final de cada repetição (ex.: amplitude mínima não atingida, velocidade excessiva).
3. Centralizamos o instanciamento no `ExerciseRegistry`, que mapeia o identificador do exercício (ex.: `FISIO-001`) para a classe correspondente.

---

## 3. Consequências

### Positivas
- **Alta Extensibilidade (Open/Closed Principle):** Adicionar um 8º exercício no futuro consiste apenas em criar uma nova classe e registrá-la no catálogo, sem tocar em nenhum código existente de orquestração ou de outros exercícios;
- **Testabilidade Granular:** Cada analisador pode ser testado isoladamente com mocks de ângulos sintetizados, sem necessidade de carregar vídeos pesados ou instanciar o MediaPipe em tempo de teste unitário;
- **Reuso de Código:** Algoritmos complexos de histerese, interpolação temporal e cálculo de conformidade residem em um único ponto testado e validado.

### Negativas / Mitigações
- **Hierarquia de Classes:** Exige familiaridade dos desenvolvedores com os padrões Strategy e Template Method. Documentamos a classe base com docstrings detalhadas e tipagem estrita com Pydantic e MyPy.
