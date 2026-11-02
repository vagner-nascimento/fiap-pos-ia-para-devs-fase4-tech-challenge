# ADR 0008: Transcodificação H.264 para Streaming Web e Compatibilidade com Navegadores

* **Status:** Aprovado
* **Data:** 2026-11-02
* **Decisores:** Time de Engenharia Fisio Coach (FIAP Fase 4 - Issue #6)
* **Contexto:** Motor de Visão Computacional, Pipeline de Renderização de Vídeo Anotado e Frontend Web

---

## 1. Contexto e Problema

O pipeline de processamento biomecânico anota os frames do paciente com o esqueleto do MediaPipe e o painel HUD translúcido (com ângulos, contagem de repetições e alertas clínicos). Originalmente, a biblioteca OpenCV gravava o arquivo `annotated.mp4` utilizando o FourCC `cv2.VideoWriter_fourcc(*"mp4v")` (MPEG-4 Part 2).

No entanto, navegadores modernos (Google Chrome, Mozilla Firefox, Apple Safari e Microsoft Edge) **não possuem decodificadores nativos para o codec MPEG-4 Part 2 dentro da tag HTML5 `<video>`**, retornando erros de decodificação no console:
```text
Media resource http://localhost:8080/media/.../annotated.mp4 could not be decoded.
```

Além disso, vídeos com grandes taxas de quadros ou resoluções sem otimização de cabeçalho MP4 (`moov atom`) no início do arquivo exigem que o navegador faça o download do arquivo inteiro antes de iniciar o playback, inviabilizando o streaming responsivo.

---

## 2. Decisão

Decidiu-se adotar o **FFmpeg** com o codec **H.264 (`libx264`)** e perfil de cores **`yuv420p`**, com a flag **`+faststart`**, como etapa padrão de pós-processamento imediatamente após o fechamento do writer OpenCV no backend:

1. **Instalação no Container Docker:**
   - Adicionou-se o pacote de sistema `ffmpeg` ao `Dockerfile` do backend FastAPI.
2. **Método de Transcodificação no `VideoProcessor`:**
   - Criou-se o método `_transcode_to_h264_if_available(video_path: Path)` no módulo `services.pose.video_processor`.
   - Executa `ffmpeg -y -i input.mp4 -c:v libx264 -pix_fmt yuv420p -movflags +faststart -an output.h264.mp4` e realiza substituição atômica do arquivo original.
3. **Resiliência e Fallback:**
   - Caso o `ffmpeg` não esteja instalado no ambiente (por exemplo, em execuções de testes unitários locais ultrarrápidos), o pipeline mantém o arquivo gerado pelo OpenCV sem quebrar a execução.

---

## 3. Consequências

### Positivas
* **Compatibilidade Universal:** Reprodução nativa instantânea na tag `<video>` do frontend React em todos os navegadores desktop e mobile.
* **Streaming Imediato (`+faststart`):** O atom `moov` é movido para o início do arquivo MP4, permitindo que o vídeo comece a rodar antes mesmo do download completo.
* **Substituição Transparente:** O caminho do arquivo permanece `annotated.mp4`, mantendo total conformidade com o contrato de rotas de mídia e persistência no MongoDB.

### Negativas / Trade-offs
* **Tempo Adicional de Processamento:** A transcodificação adiciona um overhead de ~1 a 3 segundos na etapa de finalização do vídeo. Como a análise corre em background (`BackgroundTasks`), esse tempo é imperceptível para a experiência do usuário.
* **Tamanho da Imagem Docker:** O pacote `ffmpeg` e suas dependências aumentam o tamanho da imagem do backend em aproximadamente 150MB.

---

## 4. Referências
* [Issue #6 - Processamento dos vídeos e construção de relatório individual](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge/issues/6)
* [FFmpeg H.264 Video Encoding Guide](https://trac.ffmpeg.org/wiki/Encode/H.264)
* [ADR 0005: Renderização de HUD com Pillow e UTF-8](0005-renderizacao-de-hud-com-pillow-utf8.md)
