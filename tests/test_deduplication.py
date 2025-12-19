"""Tests for deduplication utilities."""

import pytest
from datetime import datetime

from src.utils.deduplication import (
    calculate_similarity,
    deduplicate_insights,
)
from src.models.insights import Insight, SourceReference, ConfidenceLevel


class TestDeduplication:
    """Test insight deduplication."""
    
    def test_calculate_similarity_identical(self):
        """Test similarity of identical strings."""
        similarity = calculate_similarity(
            "Add HubSpot integration",
            "Add HubSpot integration"
        )
        assert similarity == 1.0
    
    def test_calculate_similarity_similar(self):
        """Test similarity of similar strings."""
        similarity = calculate_similarity(
            "Add HubSpot integration",
            "Add HubSpot Integration feature"
        )
        assert similarity > 0.7
    
    def test_calculate_similarity_different(self):
        """Test similarity of different strings."""
        similarity = calculate_similarity(
            "Add HubSpot integration",
            "The pricing page is confusing"
        )
        assert similarity < 0.3
    
    def test_deduplicate_removes_duplicates(self):
        """Test that deduplication removes similar insights."""
        source = SourceReference(
            call_id="CALL-001",
            call_date=datetime.now(),
            rep_name="Test Rep",
        )
        
        insights = [
            Insight(content="Add HubSpot integration", source=source),
            Insight(content="Add HubSpot Integration feature", source=source),
            Insight(content="The pricing page is confusing", source=source),
        ]
        
        deduplicated = deduplicate_insights(insights, similarity_threshold=0.7)
        
        # Should have 2 unique insights
        assert len(deduplicated) == 2
    
    def test_deduplicate_keeps_higher_confidence(self):
        """Test that deduplication keeps higher confidence insights."""
        source = SourceReference(
            call_id="CALL-001",
            call_date=datetime.now(),
            rep_name="Test Rep",
        )
        
        insights = [
            Insight(
                content="Add HubSpot integration", 
                source=source,
                confidence=ConfidenceLevel.LOW
            ),
            Insight(
                content="Add HubSpot Integration", 
                source=source,
                confidence=ConfidenceLevel.HIGH
            ),
        ]
        
        deduplicated = deduplicate_insights(
            insights, 
            similarity_threshold=0.8,
            prefer_higher_confidence=True
        )
        
        assert len(deduplicated) == 1
        assert deduplicated[0].confidence == ConfidenceLevel.HIGH
    
    def test_deduplicate_empty_list(self):
        """Test deduplication of empty list."""
        result = deduplicate_insights([])
        assert result == []

