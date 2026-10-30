# Documentação de Arquitetura – Fisio Coach

Bem-vindo à documentação de arquitetura do projeto **Fisio Coach**, desenvolvido para o **Tech Challenge da Fase 4** da **Pós-Tech IA para Devs (FIAP)**.

---

## 📚 Estrutura da Documentação

A documentação está organizada nas seguintes seções:

### 1. [Arquitetura do Sistema](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/arquitetura-do-sistema.md)
Documento mestre contendo a visão integral do projeto:
- **Visão Geral e Contexto:** Objetivos multimodais, escopo e problema resolvido;
- **Diagramas C4:**
  - **C4 Nível 1:** Contexto do Sistema (Atores e Sistemas Externos);
  - **C4 Nível 2:** Containers (Frontend React, Backend FastAPI, MongoDB, Storage de Mídias);
  - **C4 Nível 3:** Componentes do Backend (Rotas da API, Pose Engine, Fusão Multimodal, Infraestrutura);
- **Pipeline de Processamento Multimodal:** Diagrama de sequência ponta a ponta (vídeo, áudio, pose, laudo);
- **Arquitetura do Motor de Visão:** Padrão Strategy para os 7 exercícios clínicos, histerese e interpolação;
- **Arquitetura de Armazenamento:** Estrutura de pastas de mídias (`MEDIA_ROOT`), isolamento e coleções do MongoDB;
- **Requisitos Não-Funcionais:** Decisões de performance em CPU, segurança de dados (LGPD) e renderização responsiva.

---

### 2. Architecture Decision Records (ADRs)

Registros formais de decisões arquiteturais que orientaram a concepção do sistema:

| ADR | Título | Status | Tema |
|---|---|---|---|
| [ADR 0001](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0001-escolha-mediapipe-pose.md) | **Adoção do Google MediaPipe Pose em Substituição ao OpenPose** | Aprovado | Visão Computacional / CPU / Docker |
| [ADR 0002](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0002-padrao-strategy-para-analisadores-de-exercicios.md) | **Padrão Strategy e Template Method para Analisadores de Exercícios** | Aprovado | Padrões de Projeto / Extensibilidade |
| [ADR 0003](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0003-deteccao-automatica-de-lado-ativo.md) | **Detecção Automática de Lado Ativo (`BodySide.AUTO`)** | Aprovado | Biomecânica / Usabilidade |
| [ADR 0004](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0004-armazenamento-desacoplado-de-midias.md) | **Armazenamento Desacoplado de Mídias via `MediaStorage`** | Aprovado | Armazenamento / LGPD / Segurança |
| [ADR 0005](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0005-renderizacao-de-hud-com-pillow-utf8.md) | **Renderização de HUD com Pillow e Suporte a UTF-8** | Aprovado | Renderização de Vídeo / UX |
| [ADR 0006](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/adrs/0006-adocao-do-mongodb-para-persistencia.md) | **Adoção do MongoDB 7 para Persistência Documental e Telemetria** | Aprovado | Banco de Dados / Persistência |

---

### 3. Documentos Complementares
- [Plano Detalhado do Motor de Pose](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/plano-motor-deteccao-pose-mediapipe.md): Especificação inicial aprovada para o motor de visão;
- [Resumo de Progresso das Etapas](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/arquitetura/resumo-progresso-etapas.md): Acompanhamento e status de implementação das etapas;
- [Walkthrough do Motor de Detecção de Pose](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/docs/walkthrough-motor-deteccao-pose.md): Guia de validação prática e testes via CLI.
