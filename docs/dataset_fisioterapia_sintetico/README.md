# Dataset Sintético Multimodal de Fisioterapia

**Versão:** 1.0  
**Conteúdo:** 7 casos clínicos fictícios, laudos sintéticos, prescrições estruturadas e roteiros de gravação com rótulos esperados.

## Aviso de uso
Todos os pacientes, idades, cenários clínicos, laudos, prescrições e falas são fictícios e destinam-se exclusivamente ao desenvolvimento e teste de software. Não são recomendações clínicas nem substituem avaliação por fisioterapeuta ou médico. Não provoque dor, lesão ou fadiga em participantes.

## Casos incluídos
1. FISIO-001 — Extensão de joelho sentado
2. FISIO-002 — Exercício pendular do ombro
3. FISIO-003 — Inclinação pélvica em decúbito dorsal
4. FISIO-004 — Rotação controlada dos joelhos
5. FISIO-005 — Flexão de ombro com bastão leve (detecção de objeto)
6. FISIO-006 — Abdução de ombro com faixa elástica leve (detecção de objeto)
7. FISIO-007 — Flexão de cotovelo com halter leve (detecção de objeto)

## Estrutura
- `cases/FISIO-xxx/laudo_sintetico.json`: contexto clínico fictício e achados simulados.
- `cases/FISIO-xxx/prescricao.json`: movimento, parâmetros, sequência esperada e limites de inferência.
- `cases/FISIO-xxx/roteiros_e_rotulos.json`: roteiros de clipes, fala sugerida e rótulos esperados.
- `dataset_index.json`: índice e orientações de gravação.

## Recomendações para gravação
- Grave vídeo e áudio sincronizados, preferencialmente a 30 fps, com câmera fixa.
- Faça um plano geral e, se possível, uma tomada lateral e outra frontal/oblíqua.
- Registre falas naturais e também cenários com silêncio ou ruído controlado.
- Os erros devem ser leves e encenados, sem forçar amplitude ou usar cargas perigosas.
- O rótulo descreve o que foi encenado, não um diagnóstico médico.
- Faça revisão de rótulos por profissional qualificado antes de usar o dataset para avaliar desempenho.
- Separe os conjuntos de treino, validação e teste por participante para evitar vazamento de identidade.

## Limitações
Vídeo RGB comum não mede com precisão ângulos articulares, força, tensão de faixa elástica, dor ou ativação muscular interna. O sistema deve poder retornar “inconclusivo” quando o corpo ou objeto estiver fora do enquadramento, o áudio estiver ininteligível ou a evidência for insuficiente.
