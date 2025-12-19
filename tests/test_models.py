"""Tests for Pydantic models."""

import pytest
from datetime import datetime

from src.models.transcript import (
    Speaker,
    TranscriptSegment,
    CallMetadata,
    Transcript,
    TranscriptCollection,
)
from src.models.insights import (
    ConfidenceLevel,
    SourceReference,
    Insight,
    CallInsights,
)


class TestTranscriptModels:
    """Test transcript data models."""
    
    def test_transcript_segment_creation(self):
        """Test creating a transcript segment."""
        segment = TranscriptSegment(
            speaker=Speaker.REP,
            speaker_name="John",
            text="Hello, how are you?",
            start_time=0,
            end_time=5,
        )
        
        assert segment.speaker == Speaker.REP
        assert segment.text == "Hello, how are you?"
        assert segment.timestamp == "00:00"
    
    def test_call_metadata_formatting(self):
        """Test call metadata formatting."""
        metadata = CallMetadata(
            call_id="TEST-001",
            call_date=datetime(2024, 12, 18, 10, 30),
            rep_name="Sarah Johnson",
            company_name="Acme Corp",
            call_duration_seconds=1800,
        )
        
        assert metadata.call_date_formatted == "2024-12-18"
        assert metadata.duration_formatted == "30m 0s"
    
    def test_transcript_full_text(self):
        """Test getting full transcript text."""
        metadata = CallMetadata(
            call_id="TEST-001",
            call_date=datetime.now(),
            rep_name="Test Rep",
        )
        
        segments = [
            TranscriptSegment(speaker=Speaker.REP, text="Hello"),
            TranscriptSegment(speaker=Speaker.PROSPECT, text="Hi there"),
        ]
        
        transcript = Transcript(metadata=metadata, segments=segments)
        
        assert "Hello" in transcript.full_text
        assert "Hi there" in transcript.full_text
    
    def test_transcript_collection_properties(self):
        """Test transcript collection properties."""
        metadata1 = CallMetadata(
            call_id="TEST-001",
            call_date=datetime.now(),
            rep_name="Rep 1",
            company_name="Company A",
        )
        metadata2 = CallMetadata(
            call_id="TEST-002",
            call_date=datetime.now(),
            rep_name="Rep 2",
            company_name="Company B",
        )
        
        collection = TranscriptCollection(
            transcripts=[
                Transcript(metadata=metadata1, segments=[]),
                Transcript(metadata=metadata2, segments=[]),
            ]
        )
        
        assert collection.total_calls == 2
        assert set(collection.reps) == {"Rep 1", "Rep 2"}
        assert set(collection.companies) == {"Company A", "Company B"}


class TestInsightModels:
    """Test insight data models."""
    
    def test_source_reference_formatting(self):
        """Test source reference formatting."""
        source = SourceReference(
            call_id="CALL-001",
            call_date=datetime(2024, 12, 18),
            rep_name="Sarah Johnson",
            company_name="Acme Corp",
            timestamp="05:30",
        )
        
        ref = source.format_reference()
        
        assert "2024-12-18" in ref
        assert "Sarah Johnson" in ref
        assert "Acme Corp" in ref
        assert "@05:30" in ref
    
    def test_insight_creation(self):
        """Test creating an insight."""
        source = SourceReference(
            call_id="CALL-001",
            call_date=datetime.now(),
            rep_name="Test Rep",
        )
        
        insight = Insight(
            content="We need HubSpot integration",
            confidence=ConfidenceLevel.HIGH,
            source=source,
            direct_quote="Can you integrate with HubSpot?",
        )
        
        assert insight.content == "We need HubSpot integration"
        assert insight.confidence == ConfidenceLevel.HIGH
        assert insight.direct_quote is not None
    
    def test_call_insights_total_count(self):
        """Test counting total insights."""
        source = SourceReference(
            call_id="CALL-001",
            call_date=datetime.now(),
            rep_name="Test Rep",
        )
        
        insights = CallInsights(call_ids=["CALL-001"])
        
        # Add some insights
        insights.product_recommendations.insights.append(
            Insight(content="Test 1", source=source)
        )
        insights.positive_feedback.insights.append(
            Insight(content="Test 2", source=source)
        )
        
        assert insights.total_insights == 2

