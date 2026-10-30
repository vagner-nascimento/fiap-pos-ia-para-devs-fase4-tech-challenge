# ADR 0004: Armazenamento Desacoplado de Mídias via MediaStorage

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

Vídeos de sessões de fisioterapia geram arquivos volumosos (de 5 MB a mais de 100 MB por gravação em alta definição). Além disso, o processo de inferência gera múltiplos artefatos por execução:
- Vídeo original gravado (`original.mp4`);
- Vídeo pós-processado com anotação visual do esqueleto e HUD (`annotated.mp4`);
- Frames congelados em formato JPEG dos momentos de pico e desvio (`evidence/*.jpg`);
- Arquivos de intercâmbio de dados (`analysis.json`, `telemetry.json`).

Salvar binários pesados diretamente no banco de dados MongoDB (ex.: via GridFS ou strings Base64) inflaria desnecessariamente a base, degradaria o tempo de resposta das consultas da API e complicaria backups e restaurações.

Por outro lado, permitir que diferentes partes do backend salvem arquivos em caminhos arbitrários no disco introduz riscos graves de:
1. Vulnerabilidades de segurança (*Path Traversal* / `../../etc/passwd`);
2. Divergências entre o ambiente local (host do desenvolvedor) e o ambiente conteinerizado do Docker Compose;
3. Risco de commitar dados confidenciais ou sensíveis de pacientes para o repositório Git (violação da LGPD).

---

## 2. Decisão

Centralizamos toda a gestão de caminhos de arquivos na classe `MediaStorage` ([backend/src/config/media_paths.py](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/config/media_paths.py)):
1. **Diretório Raiz de Mídias (`MEDIA_ROOT`):**
   - No host, resolve automaticamente para a pasta `data/` na raiz do repositório;
   - No container Docker, é configurado para `/app/data`, que é mapeado como volume montado para `./data` do host;
2. **Isolamento de Segurança e Path Traversal:**
   - Todos os nomes de arquivos e identificadores passam por validação estrita via regex (`_SAFE_NAME = ^[A-Za-z0-9][A-Za-z0-9._-]*$`);
   - O método interno `_within` verifica se o caminho resolvido permanece obrigatoriamente como filho de `MEDIA_ROOT`, lançando exceção caso detecte tentativa de subida de diretório;
3. **Persistência de Metadados Relativos:**
   - No banco de dados e nos JSONs de resultado, são gravados apenas os caminhos **relativos** a `MEDIA_ROOT` (ex.: `outputs/sess-1/pose/annotated.mp4`), permitindo que a base de dados seja transportada e consultada de forma idêntica dentro ou fora do container;
4. **Proteção LGPD:**
   - As pastas `data/inputs/*` e `data/outputs/*` são adicionadas ao `.gitignore`, garantindo que vídeos de pacientes nunca sejam rastreados no Git.

---

## 3. Consequências

### Positivas
- **Desacoplamento e Portabilidade:** O MongoDB guarda apenas metadados leves e referências relativas, mantendo as queries extremamente rápidas;
- **Segurança Reforçada:** Bloqueio garantido contra ataques de path traversal;
- **Compatibilidade Bidirecional Host/Docker:** A resolução absoluta dinâmica permite rodar scripts via CLI no terminal e a aplicação completa no Docker Compose apontando para a mesma estrutura física de arquivos.

### Negativas / Mitigações
- **Gerenciamento de Ciclo de Vida em Disco:** Arquivos de vídeo descartados ou sessões excluídas exigirão rotinas de limpeza periódica de disco no futuro.
