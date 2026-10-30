# ADR 0003: Detecção Automática de Lado Ativo (`BodySide.AUTO`)

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

Nos exercícios unilaterais (como extensão de joelho `FISIO-001`, abdução de ombro `FISIO-006` e flexão de cotovelo `FISIO-007`), o paciente pode estar executando o exercício com a perna/braço direito ou esquerdo.

Exigir que o fisioterapeuta ou o paciente informe manualmente com precisão o lado antes de cada gravação apresenta alto índice de erro operacional:
- A câmera frontal espelhada gera confusão frequente entre direita e esquerda pelo usuário;
- Fixar um lado no código quebra a avaliação se o paciente filmar o outro membro;
- Em caso de membros paralisados ou em recuperação, o membro inativo permanece estático enquanto o membro ativo se move.

---

## 2. Decisão

Implementamos no `BaseExerciseAnalyzer` o modo **`BodySide.AUTO`** como padrão para todos os exercícios unilaterais:
1. O analisador processa a série temporal calculando os ângulos simultaneamente para o hemicorpo **direito** (`BodySide.RIGHT`) e **esquerdo** (`BodySide.LEFT`);
2. Para cada lado, é calculado um score composto baseado em dois fatores:
   $$\text{Score} = \text{Visibilidade Média dos Landmarks} \times \text{Amplitude Angular Total } (\Delta \theta)$$
3. O lado com maior score (maior clareza visual e movimento intencional comprovado) é eleito como o lado ativo da sessão;
4. O lado escolhido é persistido no relatório final sob o campo `side_evaluated`, permitindo rastreabilidade completa.

Caso o fisioterapeuta queira forçar a análise de um lado específico (ex.: para verificar se uma perna lesada realmente não se moveu), ele pode passar explicitamente `--side direito` ou `--side esquerdo`.

---

## 3. Consequências

### Positivas
- **Resiliência a vídeos espelhados ou posições variadas:** O sistema analisa corretamente o membro correto sem depender de configurações manuais prévias;
- **Zero fricção para o usuário final:** O paciente pode simplesmente se posicionar e realizar a série;
- **Transparência clínica:** O lado selecionado automaticamente fica registrado de forma auditável no laudo (`analysis.json`).

### Negativas / Mitigações
- **Custo computacional residual:** Durante a extração dos ângulos, são computadas as fórmulas trigonométricas de ambos os lados. Como o cálculo de ângulos 2D em NumPy é extremamente leve (ordem de microssegundos), o impacto no tempo total de processamento é desprezível (< 0.1%).
