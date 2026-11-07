# ADR 0013: Busca Privada de Prescrição, Upload de Vídeos por Slot e Rastreabilidade de Consentimento LGPD

- **Status:** Aprovado
- **Data:** Novembro de 2026
- **Decisores:** Time de Engenharia Fisio Coach (FIAP Fase 4 - Issues #4 e #5)

## 1. Contexto

Nos Passos 2 e 3 da jornada principal do **Fisio Coach** (`docs/jornada-proposta-001.md` e PRD v1.2) e nas Telas 2 e 3 do Design System (`docs/design/DESIGN.md` e Mock `02-Paciente-Envio.dc.html`), o **Paciente** precisa:
1. Localizar sua prescrição e laudo médico sem ter acesso à listagem de outros pacientes cadastrados (proteção de privacidade e dados sensíveis de saúde sob a LGPD);
2. Visualizar os limites clínicos (dor máxima aceitável `0–10`, faixa de amplitude esperada e restrições do laudo) e a lista de **slots de exercícios prescritos** (`SLOT-1`, `SLOT-2`, ...);
3. Realizar o envio de vídeo (`.mp4` de até `200 MB`) **individualmente para cada slot de exercício prescrito** (1 upload por sessão de fisioterapia), com feedback de progresso em tempo real e recuperação de falhas;
4. Registrar explicitamente o aceite do **Termo de Consentimento LGPD** para captação e processamento automatizado de imagem (postura e equipamento) e voz (transcrição local de relato de dor), mantendo esse registro auditável tanto nas telas de listagem quanto no Relatório da Sessão.

## 2. Decisão

Adotamos as seguintes decisões arquiteturais no backend (`FastAPI` + `MongoDB`) e no frontend (`React 19`):

1. **Busca Tolerante a Acentos e Privacidade na Visão do Paciente (Issue #4):**
   - O repositório `PatientRepository.list_patients(nome_query)` constrói expressões regulares insensíveis a diacríticos em português (`_build_accent_insensitive_regex`), permitindo que buscas como `"claudia"` encontrem `"Cláudia M."` (`PAC-003`);
   - A tela do paciente (`PatientPrescriptionView.jsx`) inicia sem listar pacientes: exige que o paciente informe seu nome ou código identificador (`PAC-001`) para carregar o bundle `GET /api/pacientes/{id}` (contendo `patient`, `laudo`, `plano` e `sessoes_recentes`).
2. **Vínculo Exato por `slot_id` e Preservação no Pipeline Assíncrono (Issue #5):**
   - O documento `SessionDocument` (coleção `sessoes`) foi estendido com os campos `slot_id`, `lgpd_aceite`, `original_filename` e `file_size_bytes`;
   - Os endpoints `POST /api/sessoes` (`multipart/form-data`, aceitando tanto `exercicio_id` quanto o alias `exercicio`) e `POST /api/sessoes/referencia` gravam esses metadados já no registro inicial (`status="processando"`);
   - Ao concluir o processamento em segundo plano, `MongoResultSink.save` consulta o documento pré-existente da sessão e preserva `slot_id`, `lgpd_aceite`, `original_filename`, `file_size_bytes` e `created_at`, evitando que a atualização final sobrescreva o vínculo com o slot da prescrição.
3. **Validação de Mídia, Progresso via XHR e Aceite Obrigatório LGPD (Issue #5):**
   - O backend valida obrigatoriamente `lgpd_aceite=True` (`HTTP 422` se recusado), extensão de vídeo suportada (`.mp4`, `.mov`, `.webm`, `.mkv`, `.avi`) e tamanho máximo de `200 MB` (`HTTP 413` se excedido);
   - No frontend (`frontend/src/api/sessions.js`), `createSessionUpload` utiliza `XMLHttpRequest` quando um callback `onProgress` é fornecido, reportando o percentual real de upload (`0%` a `100%`) por slot;
   - O aceite LGPD registrado na sessão (`lgpd_aceite`) é exibido visualmente por meio do selo **`● Termo LGPD aceito`** na linha do slot enviado (`PatientPrescriptionView.jsx`), na tabela geral de sessões (`SessionsListView.jsx`) e no cabeçalho e quadro de comparação clínica do relatório individual (`SessionReportView.jsx`).

## 3. Alternativas Consideradas

1. **Dropdown listando todos os pacientes na tela do paciente:** descartado por expor nomes e códigos de outros pacientes na visão do paciente, contrariando boas práticas de privacidade (LGPD).
2. **Associar sessões aos slots apenas por `exercicio_id`:** descartado como mecanismo único porque um plano pode conter múltiplos slots ou reenvios específicos; priorizar `slot_id` com fallback para `exercicio_id`/`case_id` garante precisão e retrocompatibilidade com sessões antigas.
3. **Upload via `fetch` sem progresso:** descartado para o fluxo de envio de vídeo porque arquivos de até `200 MB` exigem feedback visual de progresso e opção de **"Tentar novamente"** por slot conforme especificado na seção 4 de `docs/design/DESIGN.md`.

## 4. Consequências

### Positivas
- **Rastreabilidade ponta a ponta:** cada slot do plano sabe exatamente qual arquivo foi enviado, seu tamanho e o status do processamento/relatório;
- **Conformidade e auditabilidade LGPD:** nenhum vídeo é processado sem consentimento explícito (`422`), e o fisioterapeuta visualiza a confirmação do aceite tanto na listagem de sessões quanto no laudo/relatório impresso em PDF;
- **Experiência resiliente em desktop e mobile:** validação imediata antes do upload, barra de progresso por slot e opção complementar de selecionar clipes de demonstração do dataset sintético para testes rápidos.

### Evoluções Futuras Mapeadas
- Validação de múltiplas séries de repetições (`series` $\times$ `repeticoes`) por exercício prescrito ([Issue #21](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge/issues/21));
- Exibição do histórico de múltiplas execuções dentro de cada slot e comparativo evolutivo entre sessões do mesmo exercício ([Issue #22](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge/issues/22)).

## 5. Referências
- [Issue #4 - Busca de dados de laudo e prescrições pelo paciente](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge/issues/4)
- [Issue #5 - Upload de vídeos e termo de aceite pelo paciente](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge/issues/5)
- [Plano de Implementação da Issue #4](../../../plans/plano-issue-4-busca-laudo-prescricoes.md)
- [Plano de Implementação da Issue #5](../../../plans/plano-issue-5-upload-videos-paciente.md)

