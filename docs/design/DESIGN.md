# Fisio Coach — Design (para implementação)

Fonte: PRD v1.2 + `jornada-proposta-001.md`. Tokens em `tokens.css` / `tokens.json`; mocks de referência em `mocks/` (HTML legível, **não** copiar: reescrever como componentes React com os tokens).
Stack: React 19 + Vite, servido pelo Nginx; API em `/api` (FastAPI). Todos os dados de demonstração são fictícios.

## 1. Princípios
1. Evidência junto do veredito: toda classificação mostra o que a causou (frame, trecho, gráfico).
2. Apoio à decisão, nunca diagnóstico: manter o aviso nas telas de relatório e alerta.
3. "Sem dado" ≠ "sem dor" (RF-07): rosto fora de quadro aparece como "sem dado".
4. Estado nunca só por cor: chip = símbolo + texto + cor (● Verde, ▲ Atenção, ■ Crítico).
5. Acessibilidade: `<button>`, `<a>`, `<input>` + `<label>` reais; alvo ≥ 44px; contraste ≥ 4.5:1; `aria-label` em ícones.

## 2. Componentes
| Componente | Especificação |
|---|---|
| `AppShell` | Sidebar fixa 220px (`--fc-primary-dark`), conteúdo com padding 32/40, gap 20. Menu por perfil. |
| `Card` | Superfície branca, borda `--fc-border`, raio 14, padding 20. |
| `Button` | Variantes `primary` (fundo `--fc-primary`, texto branco) e `secondary` (borda 1.5px). Altura 44, raio 10, peso 700. |
| `Field` | `<label>` 13px/700 acima do `<input>`; altura 44, borda `--fc-border-field` 1.5px, raio 10. `textarea` altura mínima 96. |
| `StatusChip` | Props `level: ok|warn|crit|info`. Pílula 12px/700 com símbolo + texto. `info` usa `primarySoft`. |
| `Timeline` | Faixas de 28px (`--fc-track-bg`), blocos de 20px com raio 4. Uma faixa por tipo: repetições, desvios, dor facial, fala. Eixo X comum, sincronizado com o player. |
| `PainScore` | Número grande (34px/800) "x,x / 10", linha de apoio com relato/face/voz e limite do plano, chip "Acima do limite" quando excede. |
| `StepList` | Etapas com marcador circular: concluída (✓ verde), ativa (… teal), pendente (número cinza). |
| `AlertRow` | Chip de severidade + motivo + evidência resumida + tempo + botão "Abrir". |
| `VideoPlayer` | Controla o cursor da `Timeline`; clique em evento salta para o instante. |

## 3. Telas, rotas e API
| # | Tela / perfil | Rota | Passo da jornada | Endpoints |
|---|---|---|:---:|---|
| 1 | Plano e laudo (fisio) | `/pacientes/:id/plano` | 1 | `POST/GET /api/pacientes/{id}/plano`, `POST/GET /api/pacientes/{id}/laudo` |
| 2 | Minha prescrição (paciente) | `/prescricao` | 2 | `GET /api/pacientes?nome=`, `GET /api/pacientes/{id}/plano`, `GET /api/pacientes/{id}/laudo` |
| 3 | Enviar sessões (paciente) | `/enviar` | 3 | `POST /api/sessoes` (multipart: `paciente_id`, `exercicio`; um envio por sessão; responde 202) |
| 4 | Processamento | `/sessoes/:id/processamento` | 4 | `GET /api/sessoes/{id}` (polling; SSE opcional) |
| 5 | Relatório da sessão | `/sessoes/:id/relatorio` | 5 | `GET /api/sessoes/{id}`, `GET /api/sessoes/{id}/eventos`, `GET /api/sessoes/{id}/relatorio` |
| 6 | Painel de alertas | `/alertas` | 5 | `GET /api/alertas`, `PATCH /api/alertas/{id}` |
| 7 | Histórico do paciente (a desenhar) | `/pacientes/:id/historico` | — | `GET /api/pacientes/{id}/sessoes` |
| 8 | Cadastro de paciente (a desenhar) | `/pacientes/novo` | 1 | `POST /api/pacientes` |

Observações:
- Tela 2 e 3 estão na mesma página do mock; podem ser uma rota só (`/prescricao`) com seção de envio.
- "Marcar como avaliado" na tela 5 usa o alerta da sessão: `PATCH /api/alertas/{id}` com estado `tratado`.
- Navegação: ao concluir o envio, ir para `/sessoes/:id/processamento`; ao `status = concluido`, oferecer link para o relatório.

## 4. Estados que os mocks não mostram
| Tela | Estados a implementar |
|---|---|
| Todas | Carregando (skeleton), erro de API (mensagem + "Tentar novamente"), lista vazia |
| Enviar | Arquivo inválido/grande demais (limite ~200 MB), upload em andamento com progresso, falha de upload |
| Processamento | Status da sessão: `enviado`, `extraindo_trilhas`, `video`, `audio`, `fusao`, `concluido`, `erro`. No `erro`: etapa que falhou + "Reprocessar sessão" |
| Relatório | Rosto sem dado (faixa de dor facial hachurada, texto "sem dado"); inconsistência entre fontes (chip + explicação); sessão Verde (sem alertas); sem fala de dor |
| Alertas | Filtro por severidade e estado (novo, lido, tratado); alerta sem evidência de áudio |
| Plano e laudo | Extração do laudo incerta: campos editáveis e destaque "confira" |

## 5. Regras de implementação
- Importar `tokens.css` uma vez na raiz; componentes usam apenas `var(--fc-*)`. Nada de hex solto.
- Layout desktop-first (largura-base 1280); o envio de vídeo deve funcionar bem em celular (`/enviar`), com coluna única abaixo de 768px.
- Textos em pt-BR; mensagens de status vêm do backend como códigos e são traduzidas no front.
- Linguagem do relatório: "indica", "sugere"; nunca "diagnóstico".
