import os

import moviepy.editor as mp
import noisereduce as nr
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

TARGET_SAMPLE_RATE = 16_000
WHISPER_MODEL_SIZE = "medium"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHANGED_AUDIO_DIR = os.path.join(SCRIPT_DIR, "audios", "changed")
TRANSCRIPTION_PROMPT = (
    "Português brasileiro. Contexto de fisioterapia e dor. "
    "Termos possíveis: ombro, cotovelo, dor, dói, incômodo, "
    "melhorou, bastante."
)
_whisper_model = None


def prepare_audio_for_transcription(audio_path, prepared_audio_path):
    audio, sample_rate = sf.read(audio_path, always_2d=False)

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    audio = audio.astype(np.float32, copy=False)
    if sample_rate != TARGET_SAMPLE_RATE:
        audio = resample_poly(audio, TARGET_SAMPLE_RATE, sample_rate)

    audio = nr.reduce_noise(
        y=audio,
        sr=TARGET_SAMPLE_RATE,
        stationary=True,
    )

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    sf.write(
        prepared_audio_path,
        audio,
        TARGET_SAMPLE_RATE,
        subtype="PCM_16",
        format="WAV",
    )

def extract_audio_from_video(video_path, audio_path):
    video = mp.VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, verbose=False, logger=None)


def get_whisper_model():
    global _whisper_model

    if _whisper_model is None:
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )

    return _whisper_model


def transcribe_audio_to_text(audio_path, text_output_path):
    '''
    NOTA: Copiei os videos desejados do repositorio de datasets para a pasta videos 
        e altere os nomes dos arquivos de vídeo e áudio para que o código funcione corretamente.
    '''
    model = get_whisper_model()
    os.makedirs(CHANGED_AUDIO_DIR, exist_ok=True)
    prepared_audio_path = os.path.join(
        CHANGED_AUDIO_DIR,
        os.path.basename(audio_path),
    )
    prepare_audio_for_transcription(audio_path, prepared_audio_path)

    decode_options = {
        "language": "pt",
        "initial_prompt": TRANSCRIPTION_PROMPT,
        "temperature": 0.0,
        "beam_size": 5,
        "vad_filter": True,
        "vad_parameters": {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 400,
            "min_speech_duration_ms": 100,
        },
        "condition_on_previous_text": False,
    }
    segments, _ = model.transcribe(prepared_audio_path, **decode_options)
    segments = list(segments)
    text = " ".join(segment.text.strip() for segment in segments).strip()

    if text.lower().startswith("contexto de fisioterapia"):
        decode_options["vad_filter"] = False
        segments, _ = model.transcribe(prepared_audio_path, **decode_options)
        text = " ".join(segment.text.strip() for segment in segments).strip()

    print(f"Transcrição de {os.path.basename(audio_path)}: {text}")

    with open(text_output_path, "w", encoding="utf-8") as file:
        file.write(text)

# Definindo os caminhos dos arquivos de vídeo, áudio e texto
script_dir = SCRIPT_DIR
PATH_VIDEOS = os.path.join(script_dir, "videos/")
PATH_AUDIOS = os.path.join(script_dir, "audios/")
PATH_TEXT = os.path.join(script_dir, "texts/")

# Definindo os caminhos dos arquivos de vídeo cada vídeo FISIO-006
PATH_VIDEO_FISIO_006_C1 = os.path.join(PATH_VIDEOS, "FISIO-006-C01.mp4")
PATH_VIDEO_FISIO_006_C2 = os.path.join(PATH_VIDEOS, "FISIO-006-C02.mp4")
PATH_VIDEO_FISIO_006_C3 = os.path.join(PATH_VIDEOS, "FISIO-006-C03.mp4")
PATH_VIDEO_FISIO_006_C4 = os.path.join(PATH_VIDEOS, "FISIO-006-C04.mp4")

# Definindo os caminhos dos arquivos de áudio cada vídeo FISIO-006
PATH_AUDIO_FISIO_006_C1 = os.path.join(PATH_AUDIOS, "FISIO-006-C01.wav")
PATH_AUDIO_FISIO_006_C2 = os.path.join(PATH_AUDIOS, "FISIO-006-C02.wav")
PATH_AUDIO_FISIO_006_C3 = os.path.join(PATH_AUDIOS, "FISIO-006-C03.wav")
PATH_AUDIO_FISIO_006_C4 = os.path.join(PATH_AUDIOS, "FISIO-006-C04.wav")

# Definindo os caminhos dos arquivos de texto cada audio FISIO-006
PATH_TEXT_FISIO_006_C1 = os.path.join(PATH_TEXT, "FISIO-006-C01.txt")
PATH_TEXT_FISIO_006_C2 = os.path.join(PATH_TEXT, "FISIO-006-C02.txt")
PATH_TEXT_FISIO_006_C3 = os.path.join(PATH_TEXT, "FISIO-006-C03.txt")
PATH_TEXT_FISIO_006_C4 = os.path.join(PATH_TEXT, "FISIO-006-C04.txt")

# Definindo os caminhos dos arquivos de vídeo cada vídeo FISIO-007
PATH_VIDEO_FISIO_007_C1 = os.path.join(PATH_VIDEOS, "FISIO-007-C01.mp4")
PATH_VIDEO_FISIO_007_C2 = os.path.join(PATH_VIDEOS, "FISIO-007-C02.mp4")
PATH_VIDEO_FISIO_007_C3 = os.path.join(PATH_VIDEOS, "FISIO-007-C03.mp4")
PATH_VIDEO_FISIO_007_C4 = os.path.join(PATH_VIDEOS, "FISIO-007-C04.mp4")

# Definindo os caminhos dos arquivos de áudio cada vídeo FISIO-007
PATH_AUDIO_FISIO_007_C1 = os.path.join(PATH_AUDIOS, "FISIO-007-C01.wav")
PATH_AUDIO_FISIO_007_C2 = os.path.join(PATH_AUDIOS, "FISIO-007-C02.wav")
PATH_AUDIO_FISIO_007_C3 = os.path.join(PATH_AUDIOS, "FISIO-007-C03.wav")
PATH_AUDIO_FISIO_007_C4 = os.path.join(PATH_AUDIOS, "FISIO-007-C04.wav")

# Definindo os caminhos dos arquivos de texto cada audio FISIO-007
PATH_TEXT_FISIO_007_C1 = os.path.join(PATH_TEXT, "FISIO-007-C01.txt")
PATH_TEXT_FISIO_007_C2 = os.path.join(PATH_TEXT, "FISIO-007-C02.txt")
PATH_TEXT_FISIO_007_C3 = os.path.join(PATH_TEXT, "FISIO-007-C03.txt")
PATH_TEXT_FISIO_007_C4 = os.path.join(PATH_TEXT, "FISIO-007-C04.txt")

def execute_fisio_006():
    extract_audio_from_video(PATH_VIDEO_FISIO_006_C1, PATH_AUDIO_FISIO_006_C1)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C1, PATH_TEXT_FISIO_006_C1)

    extract_audio_from_video(PATH_VIDEO_FISIO_006_C2, PATH_AUDIO_FISIO_006_C2)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C2, PATH_TEXT_FISIO_006_C2)

    extract_audio_from_video(PATH_VIDEO_FISIO_006_C3, PATH_AUDIO_FISIO_006_C3)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C3, PATH_TEXT_FISIO_006_C3)

    extract_audio_from_video(PATH_VIDEO_FISIO_006_C4, PATH_AUDIO_FISIO_006_C4)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C4, PATH_TEXT_FISIO_006_C4)

def execute_fisio_007():
    extract_audio_from_video(PATH_VIDEO_FISIO_007_C1, PATH_AUDIO_FISIO_007_C1)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C1, PATH_TEXT_FISIO_007_C1)

    extract_audio_from_video(PATH_VIDEO_FISIO_007_C2, PATH_AUDIO_FISIO_007_C2)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C2, PATH_TEXT_FISIO_007_C2)

    extract_audio_from_video(PATH_VIDEO_FISIO_007_C3, PATH_AUDIO_FISIO_007_C3)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C3, PATH_TEXT_FISIO_007_C3)

    extract_audio_from_video(PATH_VIDEO_FISIO_007_C4, PATH_AUDIO_FISIO_007_C4)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C4, PATH_TEXT_FISIO_007_C4)

if __name__ == "__main__":
   execute_fisio_006()
   execute_fisio_007()
