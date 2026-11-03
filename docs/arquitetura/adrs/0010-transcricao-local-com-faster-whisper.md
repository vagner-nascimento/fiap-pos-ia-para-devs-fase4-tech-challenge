# ADR 0010: Transcrição Local com Faster-Whisper

- **Status:** Aprovado
- **Data:** Novembro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

## 1. Contexto

O áudio do vídeo contém relatos espontâneos do paciente sobre dor,
desconforto e evolução do exercício. A análise precisa de texto em português
brasileiro, com timestamps suficientes para relacionar a fala ao momento do
movimento.

Foram consideradas a biblioteca `speech_recognition` usando a API de
reconhecimento do Google e um modelo local baseado em Whisper. O projeto é uma
demonstração sem orçamento para serviços de nuvem, e uma integração cloud
traria custos recorrentes, credenciais, configuração, observabilidade,
manutenção e dependência de rede.

## 2. Decisão

Adotamos **`faster-whisper`** com execução local em CPU. O backend usa o modelo
configurado para o projeto, `device="cpu"` e `compute_type="int8"`, sem enviar
áudio para um provedor externo. A transcrição é feita antes da classificação
de dor e preserva segmentos temporais para a timeline do relatório.

O áudio é preparado antes da inferência:

1. conversão para mono;
2. reamostragem para 16 kHz;
3. redução de ruído estacionário;
4. normalização do pico;
5. gravação temporária em WAV PCM.

As opções de decodificação fixam o idioma `pt`, temperatura zero, beam size
5, filtro de atividade de voz (VAD), preenchimento de fala e ausência de
condicionamento pelo texto anterior. O prompt inicial orienta o modelo para
português brasileiro e vocabulário de fisioterapia/dor, incluindo regiões e
termos como ombro, cotovelo, dor, incômodo e melhora. A implementação também
ignora eco do próprio prompt e aplica correção pontual para uma confusão
recorrente de transcrição antes da classificação.

## 3. Alternativas consideradas

1. **`speech_recognition` + Google Speech API:** descartado por depender de
   serviço externo, rede e credenciais, além de introduzir custo e
   complexidade incompatíveis com a demonstração.
2. **Azure Speech to Text ou outro serviço cloud:** descartado pelo mesmo
   motivo e por não haver orçamento para criação, configuração e manutenção
   desses recursos na nuvem.
3. **Whisper local sem preparação de áudio ou prompt:** descartado porque
   ruído, amostragem variável e ausência de contexto reduzem a qualidade das
   extrações de domínio.

## 4. Consequências

### Positivas

- Não há custo por requisição nem dependência de disponibilidade externa;
- O áudio permanece no ambiente local, simplificando privacidade e reprodução
  da demonstração;
- Segmentos e palavras podem ser alinhados temporalmente ao vídeo;
- O prompt e o pós-processamento tornam a saída mais adequada ao vocabulário
  clínico usado pelo projeto.

### Negativas / Mitigações

- Inferência local em CPU é mais lenta que uma solução cloud escalável;
  o modelo e o tipo `int8` reduzem o consumo para o cenário demonstrativo;
- O modelo pode cometer erros de reconhecimento em sotaques, ruído e falas
  sobrepostas; o relatório deve tratar o resultado como apoio, não como
  transcrição clínica definitiva.
