# ADR 0005: Renderização de HUD com Pillow e Suporte a UTF-8

- **Status:** Aprovado
- **Data:** Outubro de 2026
- **Decisores:** Time de Engenharia Fisio Coach

---

## 1. Contexto

Para que o vídeo anotado (`annotated.mp4`) sirva como instrumento clínico e comprobatório para o fisioterapeuta, ele deve exibir em tempo real um Head-Up Display (HUD) contendo:
- O nome e a fase atual do movimento (`repouso`, `concêntrica`, `pico`, `excêntrica`);
- A contagem de repetições concluídas e prescritas (ex.: `3 / 5`);
- A medição angular atual da articulação com o símbolo de graus (ex.: `85.2°`);
- Banners de alerta destacados em vermelho para desvios detectados (ex.: `⚠️ Amplitude Reduzida: 82.5° < 85°`).

Ao utilizar a função padrão `cv2.putText` da biblioteca OpenCV, deparamo-nos com limitações críticas:
1. **Incompatibilidade com UTF-8 / ASCII 7-bit:** O OpenCV suporta nativamente apenas o conjunto de fontes Hershey (ASCII básico). Qualquer caractere acentuado da língua portuguesa (`ã`, `ó`, `é`, `ê`) ou símbolo técnico (`°`, `≥`, `⚠️`) era renderizado como ponto de interrogação (`?`), prejudicando a legibilidade e a qualidade acadêmica da entrega;
2. **Falta de Responsividade a Vídeos Verticais:** Muitas gravações de fisioterapia são feitas pelo próprio paciente utilizando a câmera do smartphone na vertical (ex.: resolução $478 \times 850$). Desenhos com coordenadas fixas em pixels resultavam em textos cortados ou sobrepostos fora da área visível do vídeo.

---

## 2. Decisão

Desenvolvemos o componente especializado `HudRenderer` ([backend/src/services/pose/hud_renderer.py](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase4-tech-challenge/backend/src/services/pose/hud_renderer.py)) integrando o **Pillow (PIL)** ao pipeline de frames do OpenCV:
1. **Renderização com Fontes TrueType:**
   - O frame BGR do OpenCV é convertido temporariamente para RGB e encapsulado em um objeto `PIL.Image`;
   - O texto é renderizado utilizando `ImageDraw.Draw` com fontes TrueType disponíveis no sistema operacional Linux/Docker (`LiberationSans-Bold.ttf`, `DejaVuSans.ttf` ou `NotoSans.ttf`);
   - Suporte nativo completo a acentuação em pt-BR e símbolos biomédicos (`°`, `≥`, `≤`);
2. **Layout Responsivo e Word-Wrapping:**
   - As dimensões dos cartões e dos banners de aviso são calculadas proporcionalmente à largura e altura do vídeo (`width * 0.03`, `height * 0.02`);
   - Mensagens de desvio longas passam por quebra de linha dinâmica (*word-wrap*), garantindo que caibam perfeitamente na largura do vídeo sem estourar as margens laterais;
3. **Alto Contraste Visual:**
   - Caixas de fundo translúcidas com cantos arredondados para garantir legibilidade do texto independente da cor da roupa do paciente ou da iluminação da sala.

---

## 3. Consequências

### Positivas
- **Aparência Profissional e Elegante:** Eliminação total de caracteres corrompidos (`?`) e textos truncados;
- **Compatibilidade com qualquer proporção de vídeo:** Suporta vídeos verticais (smartphone 9:16), widescreen (16:9) e formatos quadrados;
- **Alta performance:** A conversão de frame via ponte NumPy/PIL é altamente otimizada, consumindo menos de 5 milissegundos por quadro renderizado.

### Negativas / Mitigações
- **Dependência de pacotes de fontes no container:** O container Docker precisa ter fontes TrueType instaladas.  
  *Mitigação:* O `HudRenderer` implementa uma busca em cascata pelas fontes padrão presentes em distros Debian/Ubuntu (`fonts-liberation`, `fonts-dejavu-core`) com fallback seguro para `ImageFont.load_default()`.
