# Tech Challenge – Fase 4

> Transcrição do edital `IADT_-_Fase_4_-_Tech_challenge.pdf` (5 páginas), mantendo o texto original. Apenas a formatação foi adaptada para Markdown.

---

## Tech Challenge

Tech Challenge é o projeto que engloba os conhecimentos obtidos em todas as disciplinas dessa fase. Esta é uma atividade que, a princípio, deve ser desenvolvida em grupo. É importante atentar-se ao prazo de entrega, uma vez que essa atividade é obrigatória, valendo 90% da nota de todas as disciplinas da fase.

## Desafio

Com a IA integrada aos processos médicos da instituição — analisando exames, documentos e apoiando decisões clínicas — o hospital agora deseja monitorar continuamente os pacientes por meio de dados multimodais (áudio, vídeo e texto) para identificar sinais precoces de risco.

Além de processar laudos e exames, o sistema passará a:

- Analisar vídeos de cirurgias ou sessões de fisioterapia para identificar padrões anômalos;
- Processar gravações de voz de pacientes em consultas, detectando sintomas relacionados à fala (fadiga, disartria);
- Detectar anomalias em sinais vitais, prescrições e evolução clínica, alertando a equipe médica em tempo real;
- Integrar tudo isso com serviços gerenciados em nuvem, como Azure Cognitive Services.

## Objetivo

- Realizar a análise e fusão de diferentes tipos de dados médicos (texto, áudio, vídeo);
- Utilizar serviços em nuvem para ampliar a capacidade de processamento e inteligência;
- Aplicar técnicas de detecção de anomalias em tempo real para monitoramento preventivo.

## Requisitos obrigatórios

### Entregas técnicas

#### 1. Análise de Vídeo

- Processar vídeos clínicos (exemplo: sessões de fisioterapia ou cirurgias gravadas);
- Detectar movimentos ou eventos fora do padrão esperado, utilizando modelos como:
  - OpenPose para análise postural;
  - YOLOv8 para detecção de objetos e áreas críticas.
- Gerar relatórios automáticos indicando desvios ou falhas no procedimento.

#### 2. Análise de Áudio

- Processar áudios de consultas médicas;
- Detectar alterações vocais indicativas de condições médicas (exemplo: cansaço, dificuldades respiratórias);
- Utilizar Azure Speech to Text para transcrever e analisar os áudios;
- Identificar termos críticos e sentimentos com Azure Text Analytics.

#### 3. Detecção de Anomalias

- Aplicar técnicas de detecção de anomalias em:
  - Séries temporais de sinais vitais (batimentos, pressão arterial, oxigenação);
  - Evolução de prescrições (alterações inesperadas no tratamento);
  - Padrões de movimentação do paciente durante a internação.
- Gerar alertas automáticos para a equipe médica com base nas anomalias detectadas.

## Sugestão de datasets

- https://physionet.org/
- https://research.google.com/audioset/

## Entregáveis da Fase 4

### Repositório Git

- Código-fonte completo da solução;
- Relatório técnico com:
  - Descrição do fluxo multimodal.
  - Modelos aplicados em cada tipo de dado.
  - Resultados obtidos e exemplos de anomalias detectadas.

### Vídeo com até 15 minutos demonstrando

- Upload no YouTube ou Vimeo (público ou não listado);
- Demonstração do processamento multimodal:
  - Exemplo prático da análise de áudio e vídeo;
  - Detecção e resposta a anomalias;
  - Integração dos serviços Azure;
  - Fluxo final do alerta à equipe médica.
