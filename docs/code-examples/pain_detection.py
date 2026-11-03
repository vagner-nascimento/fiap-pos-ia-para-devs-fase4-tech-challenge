import argparse
import json
import re
import unicodedata
from pathlib import Path

from audio_to_text import (
    CHANGED_AUDIO_DIR,
    TRANSCRIPTION_PROMPT,
    get_whisper_model,
    prepare_audio_for_transcription,
)


def normalize_text(text):
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(
        char
        for char in normalized
        if unicodedata.category(char) != "Mn"
    )


def classify_pain(text):
    normalized = normalize_text(text)
    no_current_pain = bool(
        re.search(
            r"\b(nao sinto mais dor|sem mais dor|sem dor|nao doi)\b",
            normalized,
        )
    )

    has_current_pain = bool(
        re.search(r"\b(dor|doi|doendo)\b", normalized)
    ) and not no_current_pain
    has_discomfort = bool(
        re.search(r"\b(desconforto|incomodo|incomodando)\b", normalized)
    )

    if no_current_pain and not has_discomfort:
        return "pouca_ou_nenhuma_dor", 0

    if re.search(
        r"\b(muito|muita|bastante|forte|demais)\b.*\b(dor|doi|doendo)\b",
        normalized,
    ) or re.search(
        r"\b(dor|doi|doendo)\b.*\b(muito|muita|bastante|forte|demais)\b",
        normalized,
    ):
        return "muita_dor", 3

    if has_current_pain:
        return "dor", 2

    if has_discomfort:
        return "desconforto", 1

    if re.search(r"\b(melhorou|tranquilo|tranquila)\b", normalized):
        return "pouca_ou_nenhuma_dor", 0

    if re.search(r"\b(melhorou|sem dor|nao doi)\b", normalized):
        return "pouca_ou_nenhuma_dor", 0

    return "indeterminado", None


def format_timestamp(seconds):
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def transcribe_with_timestamps(audio_path):
    model = get_whisper_model()
    audio_path = Path(audio_path)
    changed_audio_path = Path(CHANGED_AUDIO_DIR) / audio_path.name
    changed_audio_path.parent.mkdir(parents=True, exist_ok=True)

    prepare_audio_for_transcription(
        str(audio_path),
        str(changed_audio_path),
    )

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

    segments, _ = model.transcribe(
        str(changed_audio_path),
        **decode_options,
    )
    segments = list(segments)
    text = " ".join(segment.text.strip() for segment in segments).strip()

    if text.lower().startswith("contexto de fisioterapia"):
        decode_options["vad_filter"] = False
        segments, _ = model.transcribe(
            str(changed_audio_path),
            **decode_options,
        )
        segments = list(segments)

    timeline = []
    for segment in segments:
        segment_text = segment.text.strip()
        if not segment_text:
            continue

        level, score = classify_pain(segment_text)
        timeline.append(
            {
                "start_seconds": round(segment.start, 2),
                "end_seconds": round(segment.end, 2),
                "timestamp": format_timestamp(segment.start),
                "nivel": level,
                "score": score,
                "texto": segment_text,
            }
        )

    return timeline


def save_timeline(audio_path, output_path):
    timeline = transcribe_with_timestamps(audio_path)
    result = {
        "audio": str(audio_path),
        "timeline": timeline,
    }

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    return timeline


def main():
    parser = argparse.ArgumentParser(
        description="Gera uma timeline de dor a partir de um áudio."
    )
    parser.add_argument("audio", help="Caminho do arquivo WAV")
    parser.add_argument(
        "--output",
        help="Arquivo JSON de saída",
    )
    args = parser.parse_args()

    output_path = args.output or f"{args.audio}.pain.json"
    timeline = save_timeline(args.audio, output_path)

    for event in timeline:
        print(
            f"{event['timestamp']}: "
            f"{event['nivel']} - {event['texto']}"
        )

    print(f"\nTimeline salva em: {output_path}")


if __name__ == "__main__":
    main()
