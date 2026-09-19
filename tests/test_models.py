"""Tests for canonical transcript and evidence models."""

import pytest
from pydantic import ValidationError

from app.models import CanonicalTranscript, EvidenceReference, Utterance


def test_utterance_valid():
    utt = Utterance(
        utterance_id="utt_001",
        speaker="AGENT",
        start_time=12.34,
        end_time=16.82,
        text="This call may be recorded for quality purposes."
    )
    assert utt.utterance_id == "utt_001"
    assert utt.speaker == "AGENT"
    assert utt.start_time == 12.34
    assert utt.end_time == 16.82
    assert utt.text == "This call may be recorded for quality purposes."


def test_utterance_immutability():
    utt = Utterance(
        utterance_id="utt_001",
        speaker="AGENT",
        start_time=1.0,
        end_time=2.0,
        text="Hello"
    )
    with pytest.raises(ValidationError):
        utt.text = "Modified text"  # Frozen model violation


def test_utterance_reversed_timestamps():
    with pytest.raises(ValidationError) as excinfo:
        Utterance(
            utterance_id="utt_001",
            speaker="AGENT",
            start_time=10.0,
            end_time=5.0,
            text="Invalid interval"
        )
    assert "end_time (5.0) cannot be earlier than start_time (10.0)" in str(excinfo.value)


def test_utterance_negative_start_time():
    with pytest.raises(ValidationError):
        Utterance(
            utterance_id="utt_001",
            speaker="AGENT",
            start_time=-1.0,
            end_time=5.0,
            text="Negative start"
        )


def test_evidence_reference_from_utterance():
    utt = Utterance(
        utterance_id="utt_005",
        speaker="CUSTOMER",
        start_time=16.0,
        end_time=19.4,
        text="Yes, it is James Mitchell."
    )
    ref = EvidenceReference.from_utterance(utt)
    assert ref.utterance_id == utt.utterance_id
    assert ref.start_time == utt.start_time
    assert ref.end_time == utt.end_time
    assert ref.speaker == utt.speaker
    assert ref.text == utt.text


def test_canonical_transcript_properties():
    utt1 = Utterance(utterance_id="utt_001", speaker="AGENT", start_time=0.0, end_time=3.5, text="A")
    utt2 = Utterance(utterance_id="utt_002", speaker="CUSTOMER", start_time=3.8, end_time=7.2, text="B")
    transcript = CanonicalTranscript(transcript_id="test_01", utterances=[utt1, utt2])

    assert transcript.transcript_id == "test_01"
    assert transcript.total_utterances == 2
    assert transcript.duration == 7.2
