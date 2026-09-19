"""Unit tests for EvidenceIndex."""

import pytest

from app.evidence.index import EvidenceIndex
from app.models import CanonicalTranscript, EvidenceReference, Utterance


@pytest.fixture
def sample_transcript():
    utterances = [
        Utterance(
            utterance_id="utt_001",
            speaker="AGENT",
            start_time=0.0,
            end_time=4.0,
            text="Thank you for calling."
        ),
        Utterance(
            utterance_id="utt_002",
            speaker="AGENT",
            start_time=4.2,
            end_time=8.5,
            text="This call may be recorded for quality purposes."
        ),
        Utterance(
            utterance_id="utt_003",
            speaker="CUSTOMER",
            start_time=9.0,
            end_time=12.0,
            text="Hi, I need assistance with my bill."
        ),
        Utterance(
            utterance_id="utt_004",
            speaker="AGENT",
            start_time=12.5,
            end_time=18.0,
            text="Certainly, your rate is 28 cents per kWh."
        )
    ]
    return CanonicalTranscript(transcript_id="call_test_01", utterances=utterances)


@pytest.fixture
def evidence_index(sample_transcript):
    return EvidenceIndex(sample_transcript)


def test_evidence_lookup_by_id(evidence_index):
    # Lookup existing utterance
    utt = evidence_index.get_utterance("utt_002")
    assert utt is not None
    assert utt.utterance_id == "utt_002"
    assert utt.speaker == "AGENT"
    assert utt.text == "This call may be recorded for quality purposes."

    # Lookup as EvidenceReference
    ev = evidence_index.get_evidence("utt_002")
    assert isinstance(ev, EvidenceReference)
    assert ev.utterance_id == "utt_002"
    assert ev.start_time == 4.2
    assert ev.end_time == 8.5
    assert ev.speaker == "AGENT"
    assert ev.text == "This call may be recorded for quality purposes."


def test_missing_utterance_id_lookup(evidence_index):
    # Lookup non-existent utterance ID should return None
    assert evidence_index.get_utterance("utt_nonexistent") is None
    assert evidence_index.get_evidence("utt_nonexistent") is None


def test_evidence_lookup_by_time_range_overlapping(evidence_index):
    # Query window [4.0, 9.5] should hit utt_001 (ends at 4.0), utt_002 (4.2-8.5), utt_003 (9.0-12.0)
    matches = evidence_index.find_by_time(4.0, 9.5)
    matched_ids = [ev.utterance_id for ev in matches]
    assert matched_ids == ["utt_001", "utt_002", "utt_003"]
    assert all(isinstance(ev, EvidenceReference) for ev in matches)


def test_evidence_lookup_by_time_range_enclosed_only(evidence_index):
    # Query window strictly [4.0, 8.8] with enclosed_only=True should only return utt_002 (4.2-8.5)
    matches = evidence_index.find_by_time(4.0, 8.8, enclosed_only=True)
    assert len(matches) == 1
    assert matches[0].utterance_id == "utt_002"


def test_evidence_lookup_by_time_range_empty(evidence_index):
    # Query window out of range [50.0, 60.0]
    matches = evidence_index.find_by_time(50.0, 60.0)
    assert matches == []


def test_evidence_lookup_by_time_range_invalid_window(evidence_index):
    with pytest.raises(ValueError):
        evidence_index.find_by_time(10.0, 5.0)


def test_evidence_lookup_by_speaker(evidence_index):
    agent_evs = evidence_index.find_by_speaker("AGENT")
    assert len(agent_evs) == 3
    assert [e.utterance_id for e in agent_evs] == ["utt_001", "utt_002", "utt_004"]

    customer_evs = evidence_index.find_by_speaker("CUSTOMER")
    assert len(customer_evs) == 1
    assert customer_evs[0].utterance_id == "utt_003"


def test_duplicate_utterance_id_rejection():
    # Ensuring EvidenceIndex rejects transcripts with duplicate utterance IDs
    u1 = Utterance(utterance_id="dup_01", speaker="AGENT", start_time=0.0, end_time=1.0, text="A")
    u2 = Utterance(utterance_id="dup_01", speaker="CUSTOMER", start_time=1.0, end_time=2.0, text="B")
    t = CanonicalTranscript(utterances=[u1, u2])

    with pytest.raises(ValueError) as excinfo:
        EvidenceIndex(t)
    assert "Duplicate utterance_id found in transcript" in str(excinfo.value)
