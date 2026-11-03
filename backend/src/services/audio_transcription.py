"""Extração, transcrição e classificação de fala relacionada à dor."""

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import unicodedata
from typing import Any


TARGET_SAMPLE_RATE = 16_000
TRANSCRIPTION_PROMPT = (
    "Português brasileiro. Contexto de fisioterapia e dor. "
    "Termos possíveis: ombro, cotovelo, dor, dói, incômodo, "
    "melhorou, bastante."
)
RELEVANT_PAIN_LEVELS = frozenset({
    "dor",
    "desconforto",
    "muita_dor",
    "pouca_ou_nenhuma_dor",
})
DEFAULT_SPEECH_SPLIT_GAP_SECONDS = 0.45
_whisper_model: Any = None


@dataclass(frozen=True)
class SpeechSegment:
    """Segmento transcrito e classificado, preservando também falas neutras."""

    start_seconds: float
    end_seconds: float
    timestamp: str
    nivel: str
    score: int | None
    texto: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_text(text: str) -> str:
    """Remove acentos e normaliza o texto para classificação determinística."""
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def correct_domain_transcription(text: str) -> str:
    """Corrige uma confusão recorrente do Whisper em frases de dor."""
    return re.sub(
        r"\b(um pouco de|pouco de)\s+droga\b",
        lambda match: f"{match.group(1)} dor",
        text,
        flags=re.IGNORECASE,
    )


def classify_pain(text: str) -> tuple[str, int | None]:
    """Classifica uma fala de acordo com os sinais de dor do domínio."""
    normalized = normalize_text(correct_domain_transcription(text))
    no_current_pain = bool(
        re.search(r"\b(nao sinto mais dor|sem mais dor|sem dor|nao doi)\b", normalized)
    )
    has_current_pain = bool(re.search(r"\b(dor|doi|doendo)\b", normalized)) and not no_current_pain
    has_discomfort = bool(re.search(r"\b(desconforto|incomodo|incomodando)\b", normalized))

    if no_current_pain and not has_discomfort:
        return "pouca_ou_nenhuma_dor", 0

    if (
        re.search(r"\b(muito|muita|bastante|forte|demais)\b.*\b(dor|doi|doendo)\b", normalized)
        or re.search(r"\b(dor|doi|doendo)\b.*\b(muito|muita|bastante|forte|demais)\b", normalized)
    ):
        return "muita_dor", 3

    if has_current_pain:
        return "dor", 2
    if has_discomfort:
        return "desconforto", 1
    if re.search(
        r"\b(melhorou|melhor|tranquilo|tranquila|tudo bem|ta tudo bem|esta tudo bem)\b",
        normalized,
    ):
        return "pouca_ou_nenhuma_dor", 0
    return "indeterminado", None


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def _decode_options() -> dict[str, Any]:
    return {
        "language": "pt",
        "initial_prompt": TRANSCRIPTION_PROMPT,
        "temperature": 0.0,
        "beam_size": 5,
        "vad_filter": True,
        "vad_parameters": {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 100,
            "min_speech_duration_ms": 100,
        },
        "condition_on_previous_text": False,
        "word_timestamps": True,
    }


def _speech_split_gap_seconds() -> float:
    configured = os.getenv("WHISPER_SPEECH_SPLIT_GAP_SECONDS")
    if not configured:
        return DEFAULT_SPEECH_SPLIT_GAP_SECONDS
    try:
        return max(0.0, float(configured))
    except ValueError:
        return DEFAULT_SPEECH_SPLIT_GAP_SECONDS


def _is_transcription_prompt_echo(text: str) -> bool:
    """Identifica quando o Whisper devolve partes do prompt como fala."""
    normalized = normalize_text(text)
    return bool(
        re.search(r"\b(portugues brasileiro|contexto de fisioterapia e dor|termos possiveis)\b", normalized)
    )


def _split_segment_by_silence(segment: Any) -> list[tuple[float, float, str]]:
    """Divide um segmento do Whisper nas pausas entre palavras."""
    words = getattr(segment, "words", None) or []
    valid_words = [
        word for word in words
        if getattr(word, "word", "").strip()
        and getattr(word, "start", None) is not None
        and getattr(word, "end", None) is not None
    ]
    if not valid_words:
        return [(
            float(segment.start),
            float(segment.end),
            segment.text.strip(),
        )]

    chunks: list[list[Any]] = [[valid_words[0]]]
    split_gap = _speech_split_gap_seconds()
    for word in valid_words[1:]:
        previous = chunks[-1][-1]
        if float(word.start) - float(previous.end) >= split_gap:
            chunks.append([])
        chunks[-1].append(word)

    return [
        (
            float(chunk[0].start),
            float(chunk[-1].end),
            "".join(word.word for word in chunk).strip(),
        )
        for chunk in chunks
    ]


def prepare_audio_for_transcription(audio_path: Path, prepared_audio_path: Path) -> None:
    """Converte o áudio para mono/16 kHz, reduz ruído e normaliza o pico."""
    import noisereduce as nr
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    audio, sample_rate = sf.read(str(audio_path), always_2d=False)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float32, copy=False)
    if sample_rate != TARGET_SAMPLE_RATE:
        audio = resample_poly(audio, TARGET_SAMPLE_RATE, sample_rate)
    audio = nr.reduce_noise(y=audio, sr=TARGET_SAMPLE_RATE, stationary=True)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak
    prepared_audio_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(prepared_audio_path), audio, TARGET_SAMPLE_RATE, subtype="PCM_16", format="WAV")


def extract_audio_from_video(video_path: Path, audio_path: Path) -> None:
    """Extrai a trilha de áudio de um vídeo usando MoviePy."""
    import moviepy.editor as mp

    clip = mp.VideoFileClip(str(video_path))
    try:
        if clip.audio is None:
            raise RuntimeError(f"O vídeo '{video_path}' não contém trilha de áudio.")
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        clip.audio.write_audiofile(str(audio_path), verbose=False, logger=None)
    finally:
        if clip.audio is not None:
            clip.audio.close()
        clip.close()


def get_whisper_model() -> Any:
    """Carrega o modelo Whisper uma única vez, sob demanda."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        model_size = os.getenv("WHISPER_MODEL_SIZE", "medium")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _whisper_model


def transcribe_audio_with_timestamps(audio_path: Path) -> list[SpeechSegment]:
    """Transcreve todos os segmentos de fala e classifica cada um."""
    model = get_whisper_model()
    prepared_audio_path = audio_path.with_name(f"{audio_path.stem}.prepared.wav")
    prepare_audio_for_transcription(audio_path, prepared_audio_path)
    try:
        options = _decode_options()
        segments, _ = model.transcribe(str(prepared_audio_path), **options)
        segments = list(segments)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if _is_transcription_prompt_echo(text):
            options["vad_filter"] = False
            options["initial_prompt"] = None
            segments, _ = model.transcribe(str(prepared_audio_path), **options)
            segments = list(segments)

        import soundfile as sf

        audio_duration = float(sf.info(str(prepared_audio_path)).duration)
        last_end = max((float(segment.end) for segment in segments), default=0.0)
        if not segments or audio_duration - last_end >= 0.8:
            tail_options = _decode_options()
            tail_options["vad_filter"] = False
            tail_options["initial_prompt"] = None
            tail_segments, _ = model.transcribe(
                str(prepared_audio_path),
                **tail_options,
            )
            tail_segments = list(tail_segments)
            if not segments:
                segments = tail_segments
            else:
                segments.extend(
                    segment
                    for segment in tail_segments
                    if float(segment.start) > last_end + 0.2
                )

        result: list[SpeechSegment] = []
        for segment in segments:
            for start_seconds, end_seconds, chunk_text in _split_segment_by_silence(segment):
                if not chunk_text:
                    continue
                chunk_text = correct_domain_transcription(chunk_text)
                level, score = classify_pain(chunk_text)
                result.append(
                    SpeechSegment(
                        start_seconds=round(start_seconds, 2),
                        end_seconds=round(end_seconds, 2),
                        timestamp=format_timestamp(start_seconds),
                        nivel=level,
                        score=score,
                        texto=chunk_text,
                    )
                )
        return result
    finally:
        prepared_audio_path.unlink(missing_ok=True)


def transcribe_video(video_path: Path, audio_path: Path) -> list[SpeechSegment]:
    """Extrai e transcreve o áudio, removendo o arquivo intermediário depois."""
    extract_audio_from_video(video_path, audio_path)
    try:
        return transcribe_audio_with_timestamps(audio_path)
    finally:
        audio_path.unlink(missing_ok=True)


def relevant_speech_segments(segments: list[SpeechSegment]) -> list[SpeechSegment]:
    """Seleciona estados que devem ser exibidos na faixa Fala de dor."""
    return [segment for segment in segments if segment.nivel in RELEVANT_PAIN_LEVELS]
