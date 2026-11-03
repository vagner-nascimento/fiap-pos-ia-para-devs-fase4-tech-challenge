from pathlib import Path

import mongomock

from config.media_paths import MediaStorage
from infra.database.repositories.event_repository import EventRepository
from infra.database.repositories.session_repository import SessionRepository
from services.audio_transcription import (
    SpeechSegment,
    _decode_options,
    _is_transcription_prompt_echo,
    _split_segment_by_silence,
    classify_pain,
    correct_domain_transcription,
    relevant_speech_segments,
)
from services.pose.models import ExerciseAnalysisResult, SessionSummary
from services.pose.sinks import MongoResultSink


def test_classify_pain_distinguishes_active_and_absent_pain():
    assert classify_pain("Estou com dor") == ("dor", 2)
    assert classify_pain("Está doendo bastante") == ("muita_dor", 3)
    assert classify_pain("Sinto um incômodo") == ("desconforto", 1)
    assert classify_pain("Não sinto mais dor") == ("pouca_ou_nenhuma_dor", 0)
    assert classify_pain("Agora sim, está bem melhor") == ("pouca_ou_nenhuma_dor", 0)
    assert classify_pain("Tá tudo bem") == ("pouca_ou_nenhuma_dor", 0)
    assert classify_pain("Vamos começar o exercício") == ("indeterminado", None)
    assert classify_pain("Ainda assim um pouco de droga") == ("dor", 2)


def test_correct_domain_transcription_repairs_whisper_pain_confusion():
    assert correct_domain_transcription("Ainda assim um pouco de droga.") == "Ainda assim um pouco de dor."
    assert correct_domain_transcription("Uso uma droga") == "Uso uma droga"


def test_transcription_vad_uses_small_speech_padding():
    assert _decode_options()["vad_parameters"]["speech_pad_ms"] == 100
    assert _decode_options()["word_timestamps"] is True
    assert _is_transcription_prompt_echo("Português brasileiro.") is True
    assert _is_transcription_prompt_echo("Ai, meu cotovelo dói.") is False


def test_transcription_splits_whisper_segment_at_word_silence():
    class Word:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.word = text

    class Segment:
        start = 1.0
        end = 5.0
        text = " Estou com dor  Não sinto mais dor"
        words = [
            Word(1.0, 1.4, " Estou"),
            Word(1.5, 1.7, " com"),
            Word(1.8, 2.1, " dor"),
            Word(3.0, 3.4, " Não"),
            Word(3.5, 3.8, " sinto"),
            Word(3.9, 4.2, " mais"),
            Word(4.3, 4.6, " dor"),
        ]

    chunks = _split_segment_by_silence(Segment())

    assert chunks == [
        (1.0, 2.1, "Estou com dor"),
        (3.0, 4.6, "Não sinto mais dor"),
    ]


def test_relevant_speech_segments_keeps_absent_pain_and_drops_unknown():
    segments = [
        SpeechSegment(0.0, 1.0, "0:00", "dor", 2, "Estou com dor"),
        SpeechSegment(2.0, 3.0, "0:02", "pouca_ou_nenhuma_dor", 0, "Não sinto mais dor"),
        SpeechSegment(4.0, 5.0, "0:04", "indeterminado", None, "Vamos começar"),
    ]

    relevant = relevant_speech_segments(segments)

    assert [segment.nivel for segment in relevant] == ["dor", "pouca_ou_nenhuma_dor"]


def test_mongo_sink_persists_speech_events_without_changing_biomechanics(tmp_path: Path):
    mongo = mongomock.MongoClient()["test_db"]
    session_repo = SessionRepository(collection=mongo["sessoes"])
    event_repo = EventRepository(collection=mongo["eventos"])
    sink = MongoResultSink(
        session_repository=session_repo,
        event_repository=event_repo,
        media_storage=MediaStorage(tmp_path),
    )
    result = ExerciseAnalysisResult(
        session_summary=SessionSummary(
            exercise_id="FISIO-001",
            case_id="FISIO-001",
            side_evaluated="direito",
            completed_repetitions=0,
            valid_repetitions=0,
            invalid_repetitions=0,
            duration_seconds=5,
            fps=30,
            total_frames=150,
            frames_without_pose=0,
            compliance_score=100,
        ),
        repetitions=[],
        deviations=[],
        telemetry=[],
    )
    speech = [
        SpeechSegment(1.0, 2.0, "0:01", "dor", 2, "Estou com dor"),
        SpeechSegment(3.0, 4.0, "0:03", "pouca_ou_nenhuma_dor", 0, "Não sinto mais dor"),
    ]

    output = sink.save(result, "run_speech", speech_segments=speech)
    events = event_repo.list_events_by_session("run_speech")

    assert output["events_saved"] == 2
    assert [event.tipo.value for event in events] == ["fala_dor", "fala_dor"]
    assert events[0].descricao == "Estou com dor"
    assert events[1].valores["nivel"] == "pouca_ou_nenhuma_dor"
