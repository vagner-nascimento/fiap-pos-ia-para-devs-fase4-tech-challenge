# ADR 0001: Adoção do Google MediaPipe Pose em Substituição ao OpenPose

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

O edital e a proposta inicial do projeto (RF-01 do PRD) citavam o uso de modelos de pose estimation como OpenPose para extrair keypoints articulares e calcular ângulos frame a frame.

Contudo, durante o planejamento da infraestrutura de execução e conteinerização, identificamos os seguintes desafios com o OpenPose:
1. **Dependência obrigatória de GPU NVIDIA:** O OpenPose possui compilação C++ complexa e requer CUDA/cuDNN de versões específicas para ter desempenho minimamente utilizável;
2. **Inviabilidade em ambientes CPU e Docker genérico:** Em CPU, a inferência do OpenPose cai para menos de 1–2 quadros por segundo (FPS), tornando inviável a execução de vídeos de 30 a 60 segundos nos prazos de demonstração e testes contínuos;
3. **Licenciamento restritivo:** O OpenPose possui licença restritiva para uso não acadêmico.

O PRD v1.2 já contemplava explicitamente o MediaPipe como alternativa aprovada ("Plano B") caso surgissem limitações de infraestrutura.

---

## 2. Decisão

Decidimos adotar o **Google MediaPipe Pose** (arquitetura BlazePose) como o motor padrão de visão computacional para rastreamento de postura e extração de landmarks 2D/3D no projeto Fisio Coach.

---

## 3. Consequências

### Positivas
- **Alta performance em CPU:** O MediaPipe foi concebido para rodar em tempo real mesmo em CPUs de entrada (x86_64 e ARM), processando um vídeo de 30s em menos de 1 minuto em uma máquina portátil sem placa de vídeo dedicada;
- **Instalação simples via wheels Python:** Disponível via `pip install mediapipe==0.10.21`, integrando-se nativamente com o ecossistema `uv` e Python 3.11 no Docker;
- **Excelente precisão com 33 landmarks corporais:** Mapeamento anatômico completo incluindo ombros, cotovelos, punhos, quadris, joelhos, tornozelos e pés, com flags individuais de visibilidade e presença por landmark;
- **Licença permissiva:** Licenciado sob Apache 2.0.

### Negativas / Mitigações
- **Incompatibilidade temporária com Python 3.14:** O wheel oficial do MediaPipe ainda não suporta Python 3.14 (lançado recentemente).  
  *Mitigação:* Fixamos a versão do Python no projeto como `requires-python = ">=3.11,<3.13"`, usando o Python 3.11 estável tanto no Dockerfile quanto no ambiente virtual local.
- **Detecção mono-pessoa prioritária:** O modelo BlazePose prioriza a pessoa mais proeminente no quadro.  
  *Mitigação:* O caso de uso do Fisio Coach foca na gravação individual do paciente realizando a reabilitação, o que torna essa característica uma vantagem que descarta interferências no fundo.

---

## 4. Alternativas Consideradas

1. **OpenPose:** Descartado devido à dependência crítica de CUDA, compilação complexa e lentidão inviável em CPU.
2. **YOLOv8-Pose:** Excelente opção, porém mais pesada para inferência em CPU comparada ao BlazePose e com menor granularidade de keypoints faciais/extremidades nos modelos nano/small.
