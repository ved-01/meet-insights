"""Deduplication utilities for insights."""

from difflib import SequenceMatcher
from typing import Optional

from ..models.insights import Insight, ConfidenceLevel


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two texts."""
    # Normalize texts
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    
    return SequenceMatcher(None, t1, t2).ratio()


def deduplicate_insights(
    insights: list[Insight],
    similarity_threshold: float = 0.75,
    prefer_higher_confidence: bool = True,
) -> list[Insight]:
    """
    Remove duplicate or very similar insights.
    
    When duplicates are found:
    - If prefer_higher_confidence=True, keep the one with higher confidence
    - Otherwise, keep the first occurrence
    
    Args:
        insights: List of insights to deduplicate
        similarity_threshold: Minimum similarity ratio to consider as duplicate (0-1)
        prefer_higher_confidence: Whether to prefer higher confidence insights
    
    Returns:
        Deduplicated list of insights
    """
    if not insights:
        return []
    
    # Track which insights to keep
    unique_insights: list[Insight] = []
    
    confidence_order = {
        ConfidenceLevel.HIGH: 3,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.LOW: 1,
        "high": 3,
        "medium": 2,
        "low": 1,
    }
    
    for insight in insights:
        is_duplicate = False
        duplicate_index: Optional[int] = None
        
        for idx, existing in enumerate(unique_insights):
            similarity = calculate_similarity(insight.content, existing.content)
            
            if similarity >= similarity_threshold:
                is_duplicate = True
                duplicate_index = idx
                break
        
        if is_duplicate and duplicate_index is not None:
            if prefer_higher_confidence:
                existing = unique_insights[duplicate_index]
                existing_conf = confidence_order.get(existing.confidence, 2)
                new_conf = confidence_order.get(insight.confidence, 2)
                
                if new_conf > existing_conf:
                    # Replace with higher confidence insight
                    unique_insights[duplicate_index] = insight
        else:
            unique_insights.append(insight)
    
    return unique_insights


def merge_similar_insights(
    insights: list[Insight],
    similarity_threshold: float = 0.6,
) -> list[Insight]:
    """
    Merge similar insights into combined insights.
    
    This is more aggressive than deduplication - it combines
    related insights into single comprehensive insights.
    """
    if len(insights) <= 1:
        return insights
    
    # Group similar insights
    groups: list[list[Insight]] = []
    used = set()
    
    for i, insight in enumerate(insights):
        if i in used:
            continue
        
        group = [insight]
        used.add(i)
        
        for j, other in enumerate(insights[i+1:], start=i+1):
            if j in used:
                continue
            
            similarity = calculate_similarity(insight.content, other.content)
            if similarity >= similarity_threshold:
                group.append(other)
                used.add(j)
        
        groups.append(group)
    
    # Merge each group
    merged = []
    for group in groups:
        if len(group) == 1:
            merged.append(group[0])
        else:
            # Combine into single insight
            # Use the longest content as base
            base = max(group, key=lambda x: len(x.content))
            
            # Find highest confidence
            best_confidence = max(
                group, 
                key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(
                    x.confidence.value if hasattr(x.confidence, 'value') else x.confidence, 2
                )
            ).confidence
            
            # Collect all sources
            all_calls = list(set(g.source.call_id for g in group))
            
            merged_insight = Insight(
                id=base.id,
                content=base.content,
                confidence=best_confidence,
                source=base.source,
                tags=list(set(tag for g in group for tag in g.tags)),
                direct_quote=base.direct_quote or next(
                    (g.direct_quote for g in group if g.direct_quote), None
                ),
            )
            merged.append(merged_insight)
    
    return merged

