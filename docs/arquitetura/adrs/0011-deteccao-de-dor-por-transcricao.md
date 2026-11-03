# ADR 0011: Detecção de Dor por Transcrição de Áudio

- **Status:** Aprovado
- **Data:** Novembro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

## 1. Contexto

O relato verbal é uma fonte importante de informação porque o paciente pode
descrever dor, desconforto ou melhora durante a execução. A solução precisa
preservar quando a fala aconteceu e diferenciar expressões como “estou com
dor” de “não sinto mais dor”.

Nesta etapa, não foi adotado um classificador clínico treinado nem um serviço
de NLP em nuvem. A demonstração precisa ser determinística, reproduzível e
executável junto do backend local.

## 2. Decisão

A dor é estimada a partir da **transcrição segmentada do áudio**:

1. o áudio é extraído do vídeo;
2. o áudio é preparado e transcrito pelo Faster-Whisper;
3. cada segmento é dividido por pausas quando há timestamps de palavras;
4. o texto é normalizado, removendo diferenças de caixa e acentos;
5. regras de domínio identificam negação, dor, desconforto, intensidade e
   expressões de melhora;
6. cada segmento recebe nível, score opcional, texto e intervalo temporal;
7. a API persiste a timeline para o relatório e a interface a apresenta junto
   do vídeo e dos demais eventos.

Os níveis atuais são `pouca_ou_nenhuma_dor`, `desconforto`, `dor`,
`muita_dor` e `indeterminado`. A negação tem precedência para evitar que uma
frase como “não sinto mais dor” seja classificada como dor atual. O texto
original é mantido para explicabilidade e revisão pelo fisioterapeuta.

## 3. Alternativas consideradas

1. **Classificar apenas o áudio bruto:** descartado porque perde o conteúdo
   semântico do relato do paciente.
2. **Usar somente expressões faciais ou landmarks:** descartado porque não
   substitui o autorrelato e não cobre a informação verbal.
3. **Modelo clínico supervisionado ou serviço externo:** reservado para uma
   evolução futura, pois exige base anotada, validação clínica, governança e
   recursos que não fazem parte da demonstração.

## 4. Consequências

### Positivas

- O resultado é temporal, auditável e explicável pelo texto original;
- Frases de dor e de ausência de dor podem ser tratadas explicitamente;
- A timeline pode ser exibida junto da postura, dos alertas e do vídeo;
- A implementação é simples de testar e não depende de cloud.

### Negativas / Limitações

- Regras de texto não compreendem toda nuance, ironia, ambiguidade ou contexto
  clínico;
- Falas inaudíveis, transcrições incorretas e silêncio geram informação
  incompleta;
- A classificação é um indicador de apoio à decisão, não diagnóstico nem
  substituto da avaliação do fisioterapeuta;
- Um produto real deve validar o método com dados anotados e avaliação de
  profissionais de saúde antes de usar os scores clinicamente.
