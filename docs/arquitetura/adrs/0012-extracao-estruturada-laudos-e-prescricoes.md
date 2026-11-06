# ADR 0012: Extração Estruturada de Laudos Médicos com Revisão Humana e Persistência de Prescrições

- **Status:** Aprovado
- **Data:** Novembro de 2026
- **Decisores:** Time de Engenharia Fisio Coach (FIAP Fase 4 - Issue #3)

## 1. Contexto

Na jornada clínica do **Fisio Coach** (Passo 1 do PRD v1.2 e Tela 1 do Design System), o fisioterapeuta ou médico cadastra para cada paciente:
1. O **laudo médico** em texto livre (descrevendo a região anatômica afetada, a lesão diagnosticada e movimentos ou ângulos restritos);
2. O **plano de prescrição de exercícios** (limites de dor aceitável na escala 0–10, faixa de amplitude esperada em graus e lista ordenada de exercícios prescritos entre `FISIO-001` e `FISIO-007` com séries, repetições, lado e equipamento).

O sistema precisa transformar o texto livre do laudo em metadados estruturados (`regiao`, `lesao`, `movimentos_restritos`, `limite_amplitude_max`) para exibição imediata em chips de apoio à decisão e comparação clínica nos relatórios das sessões, sem depender de chaves ou serviços pagos de NLP em nuvem e preservando a supervisão do profissional de saúde (*human-in-the-loop*).

## 2. Decisão

Adotamos uma arquitetura em três camadas para o gerenciamento de pacientes, laudos e prescrições:

1. **Extrator Determinístico Local em Português (`backend/src/services/clinical_extractor.py`):**
   - Normaliza o texto livre do laudo (remoção de diacríticos e padronização léxica);
   - Identifica regiões anatômicas (`ombro direito/esquerdo`, `joelho direito/esquerdo`, `coluna lombar e pelve`, `cotovelo direito/esquerdo`, etc.) e lesões ortopédicas do domínio (`tendinopatia`, `pós-LCA`, `osteoartrite`, `lombalgia`, `epicondilite lateral`);
   - Extrai restrições angulares explícitas via expressões regulares (ex.: *"evitar elevação acima de 90°"* $\rightarrow$ `movimentos_restritos: ["elevação > 90°"]`, `limite_amplitude_max: 90.0`) e restrições qualitativas (*extensão forçada*, *rotação lombar ampla sob carga*, *carga acima do limite*).
2. **Revisão Humana Explícita (*Human-in-the-Loop*):**
   - A interface web (`PlanAndReportView.jsx`) aciona o endpoint de preview `POST /api/pacientes/laudo/extrair` e apresenta os chips sob o aviso **"Extraído automaticamente (confira):"**;
   - Caso a extração automática seja incerta ou incompleta, o fisioterapeuta pode abrir os campos editáveis (`Região`, `Lesão`, `Movimentos restritos`), ajustá-los manualmente e salvar com a flag `revisado_profissional = true`.
3. **Persistência Documental e Seed Sintético no MongoDB:**
   - Três coleções dedicadas no MongoDB: `pacientes` (`PatientDocument`), `laudos` (`MedicalReportDocument`) e `planos` (`PlanDocument`, com itens `PrescribedExerciseItem` identificados por `slot_id`);
   - Inicialização automática (`ensure_seed_clinical_data`) com os 4 casos sintéticos de demonstração do PRD seção 8.3 (`PAC-001` a `PAC-004` / `LAU-A` a `LAU-D`), garantindo dados fictícios conformes à LGPD desde o primeiro acesso.

## 3. Alternativas Consideradas

1. **Serviço de NLP em nuvem (Azure Text Analytics / LLM externo):** descartado para o pipeline padrão de demonstração local por exigir credenciais externas, conectividade e custo, mantendo-se a arquitetura 100% reproduzível via `docker compose up` em CPU.
2. **Extração puramente automática sem edição pelo profissional:** descartada por violar o requisito de segurança clínica e o estado previsto na seção 4 de `docs/design/DESIGN.md` (*"Extração do laudo incerta: campos editáveis e destaque 'confira'"*).
3. **Armazenar plano e laudo embutidos apenas na sessão:** descartado porque um mesmo paciente realiza múltiplas sessões para os exercícios prescritos em seu plano; separar as coleções `pacientes`, `laudos` e `planos` viabiliza a busca pelo paciente (Issue #4) e os slots de upload por exercício prescrito (Issue #5).

## 4. Consequências

### Positivas
- **Zero custo e zero latência de rede:** extração instantânea em CPU, determinística e 100% testável com testes unitários rápidos;
- **Segurança clínica e explicabilidade:** o profissional visualiza os chips extraídos antes de salvar e pode sobrescrever qualquer campo;
- **Integração direta com o relatório da sessão:** `GET /api/sessoes/{id}/relatorio` enriquece automaticamente a comparação clínica com os limites reais do plano (`dor_maxima_aceitavel`, `amplitude_esperada_texto`) e restrições do laudo do paciente;
- **Prontidão para as Issues #4 e #5:** cada exercício prescrito já possui `slot_id`, `exercicio_id`, `series`, `repeticoes`, `lado` e `equipamento`.

### Negativas / Limitações
- O extrator baseado em regras cobre o vocabulário ortopédico e fisioterapêutico mapeado no projeto, podendo não reconhecer abreviações médicas atípicas fora do domínio (mitigado pelos campos editáveis na interface).

## 5. Referências
- [Issue #3 - Inserção de dados de laudo e prescrições](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge/issues/3)
- [Plano de Implementação da Issue #3](../../../plans/plano-issue-3-insercao-laudo-prescricoes.md)

