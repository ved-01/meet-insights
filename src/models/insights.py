"""Pydantic models for insight data structures."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence level for extracted insights."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceReference(BaseModel):
    """Reference to the source of an insight."""
    
    call_id: str = Field(
        description="ID of the call this insight came from"
    )
    call_date: datetime = Field(
        description="Date of the call"
    )
    rep_name: str = Field(
        description="Name of the rep on the call"
    )
    speaker_name: Optional[str] = Field(
        default=None,
        description="Name of the person who said the quote/insight, if known"
    )
    company_name: Optional[str] = Field(
        default=None,
        description="Company name if available"
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="Timestamp in the call (MM:SS format)"
    )
    quote_snippet: Optional[str] = Field(
        default=None,
        description="Direct quote or snippet from transcript"
    )
    
    def format_reference(self) -> str:
        """Format source reference for display."""
        parts = [f"Call: {self.call_date.strftime('%Y-%m-%d')}"]
        if self.speaker_name:
            parts.append(f"Speaker: {self.speaker_name}")
        parts.append(f"Rep: {self.rep_name}")
        if self.company_name:
            parts.append(f"Company: {self.company_name}")
        if self.timestamp:
            parts.append(f"@{self.timestamp}")
        return " | ".join(parts)


class Insight(BaseModel):
    """A single extracted insight."""
    
    model_config = {"use_enum_values": True}
    
    id: Optional[str] = Field(
        default=None,
        description="Unique identifier for deduplication"
    )
    content: str = Field(
        description="The insight content/text"
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="Confidence level of this insight"
    )
    source: SourceReference = Field(
        description="Source reference for this insight"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for categorization"
    )
    direct_quote: Optional[str] = Field(
        default=None,
        description="Direct quote from the transcript if applicable"
    )


class InsightCategory(str, Enum):
    """Categories for insights extraction."""
    PRODUCT_RECOMMENDATIONS = "product_recommendations"
    POSITIVE_FEEDBACK = "positive_feedback"
    MARKETING_MESSAGING = "marketing_messaging"
    SOCIAL_MESSAGING = "social_messaging"
    FAQ_IDEAS = "faq_ideas"
    BLOG_TOPICS = "blog_topics"


class ProductRecommendations(BaseModel):
    """Product recommendations and feature requests."""
    
    category: str = Field(
        default="Product Recommendations",
        description="Category name"
    )
    description: str = Field(
        default="Feature requests, missing capabilities, integrations requested, 'you should build X'",
        description="Category description"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="List of product recommendation insights"
    )


class PositiveFeedback(BaseModel):
    """Positive feedback and testimonials."""
    
    category: str = Field(
        default="Positive Feedback & Testimonials",
        description="Category name"
    )
    description: str = Field(
        default="Quotes, outcomes, 'love this', value statements",
        description="Category description"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="List of positive feedback insights"
    )


class MarketingMessaging(BaseModel):
    """Marketing and brand messaging feedback."""
    
    category: str = Field(
        default="Marketing & Brand Messaging",
        description="Category name"
    )
    description: str = Field(
        default="Feedback on website, emails, nurtures, positioning, clarity",
        description="Category description"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="List of marketing messaging insights"
    )


class SocialMessaging(BaseModel):
    """Social media messaging ideas."""
    
    category: str = Field(
        default="Social Messaging",
        description="Category name"
    )
    description: str = Field(
        default="Hooks, punchy phrases, what resonates, short quotes suitable for social",
        description="Category description"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="List of social messaging insights"
    )


class FAQIdeas(BaseModel):
    """FAQ section ideas."""
    
    category: str = Field(
        default="FAQs Section Ideas",
        description="Category name"
    )
    description: str = Field(
        default="Repeated questions, confusion points, objections that can be answered publicly",
        description="Category description"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="List of FAQ ideas"
    )


class BlogTopics(BaseModel):
    """Blog topics and content ideas."""
    
    category: str = Field(
        default="Blog Topics & Ideas",
        description="Category name"
    )
    description: str = Field(
        default="Pain points, trends, 'how do I...', 'what's the best way to...', repeated themes",
        description="Category description"
    )
    insights: list[Insight] = Field(
        default_factory=list,
        description="List of blog topic ideas"
    )


class CallInsights(BaseModel):
    """Complete insights extracted from a single call or batch."""
    
    call_ids: list[str] = Field(
        description="IDs of calls processed"
    )
    processed_at: datetime = Field(
        default_factory=datetime.now,
        description="When insights were extracted"
    )
    product_recommendations: ProductRecommendations = Field(
        default_factory=ProductRecommendations,
        description="Product recommendation insights"
    )
    positive_feedback: PositiveFeedback = Field(
        default_factory=PositiveFeedback,
        description="Positive feedback insights"
    )
    marketing_messaging: MarketingMessaging = Field(
        default_factory=MarketingMessaging,
        description="Marketing messaging insights"
    )
    social_messaging: SocialMessaging = Field(
        default_factory=SocialMessaging,
        description="Social messaging insights"
    )
    faq_ideas: FAQIdeas = Field(
        default_factory=FAQIdeas,
        description="FAQ ideas"
    )
    blog_topics: BlogTopics = Field(
        default_factory=BlogTopics,
        description="Blog topic ideas"
    )
    
    @property
    def total_insights(self) -> int:
        """Count total insights across all categories."""
        return (
            len(self.product_recommendations.insights) +
            len(self.positive_feedback.insights) +
            len(self.marketing_messaging.insights) +
            len(self.social_messaging.insights) +
            len(self.faq_ideas.insights) +
            len(self.blog_topics.insights)
        )
    
    def get_category(self, category: InsightCategory):
        """Get insights by category enum."""
        mapping = {
            InsightCategory.PRODUCT_RECOMMENDATIONS: self.product_recommendations,
            InsightCategory.POSITIVE_FEEDBACK: self.positive_feedback,
            InsightCategory.MARKETING_MESSAGING: self.marketing_messaging,
            InsightCategory.SOCIAL_MESSAGING: self.social_messaging,
            InsightCategory.FAQ_IDEAS: self.faq_ideas,
            InsightCategory.BLOG_TOPICS: self.blog_topics,
        }
        return mapping[category]


class ThemeSummary(BaseModel):
    """Summary of a recurring theme across calls."""
    
    theme: str = Field(
        description="The theme/topic"
    )
    occurrence_count: int = Field(
        description="Number of times this theme appeared"
    )
    categories: list[str] = Field(
        description="Categories where this theme appeared"
    )
    example_insights: list[str] = Field(
        description="Example insight content for this theme"
    )
    related_calls: list[str] = Field(
        description="Call IDs where this theme appeared"
    )


class WeeklyRollup(BaseModel):
    """Weekly rollup with top themes and summary."""
    
    week_start: datetime = Field(
        description="Start of the week"
    )
    week_end: datetime = Field(
        description="End of the week"
    )
    total_calls_processed: int = Field(
        description="Total calls analyzed"
    )
    total_insights_extracted: int = Field(
        description="Total insights extracted"
    )
    top_themes: list[ThemeSummary] = Field(
        default_factory=list,
        description="Top 5 themes across all calls"
    )
    insights_by_category: dict[str, int] = Field(
        default_factory=dict,
        description="Count of insights per category"
    )
    reps_analyzed: list[str] = Field(
        default_factory=list,
        description="Reps whose calls were analyzed"
    )

