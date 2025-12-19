"""LangChain-based insight extractor with structured output."""

import os
from datetime import datetime
from typing import Optional
import hashlib
import re
from difflib import SequenceMatcher

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from ..models.transcript import Transcript, TranscriptCollection
from ..models.insights import (
    CallInsights,
    Insight,
    SourceReference,
    ConfidenceLevel,
    ProductRecommendations,
    PositiveFeedback,
    MarketingMessaging,
    SocialMessaging,
    FAQIdeas,
    BlogTopics,
    WeeklyRollup,
    ThemeSummary,
)


class ExtractedInsightItem(BaseModel):
    """Single insight item extracted by LLM."""
    content: str = Field(description="The insight content - be specific and actionable")
    confidence: str = Field(description="Confidence level: low, medium, or high")
    direct_quote: Optional[str] = Field(default=None, description="Direct quote from transcript if applicable")
    timestamp_hint: Optional[str] = Field(default=None, description="Approximate timestamp or context")


class CategoryInsights(BaseModel):
    """Insights for a single category."""
    insights: list[ExtractedInsightItem] = Field(
        default_factory=list,
        description="List of 3-10 insights for this category"
    )


class AllCategoryInsights(BaseModel):
    """All insights across all categories."""
    product_recommendations: CategoryInsights = Field(
        description="Feature requests, missing capabilities, integrations requested"
    )
    positive_feedback: CategoryInsights = Field(
        description="Testimonials, quotes, outcomes, value statements"
    )
    marketing_messaging: CategoryInsights = Field(
        description="Feedback on website, emails, positioning, clarity"
    )
    social_messaging: CategoryInsights = Field(
        description="Hooks, punchy phrases, short quotes for social media"
    )
    faq_ideas: CategoryInsights = Field(
        description="Repeated questions, confusion points, common objections"
    )
    blog_topics: CategoryInsights = Field(
        description="Pain points, trends, how-to topics, repeated themes"
    )


class InsightExtractionResult(BaseModel):
    """Result of insight extraction."""
    insights: CallInsights
    processing_time_seconds: float
    tokens_used: Optional[int] = None


class InsightExtractor:
    """Extract categorized insights from transcripts using LangChain."""
    
    EXTRACTION_PROMPT = """You are an expert analyst extracting actionable insights from sales call transcripts.

Analyze the following transcript and extract insights into exactly 6 categories.
For each category, provide 3-10 specific, actionable insights based on what was discussed.

TRANSCRIPT METADATA:
- Call Date: {call_date}
- Sales Rep: {rep_name}
- Company: {company_name}
- Call Type: {call_type}

TRANSCRIPT:
{transcript_text}

INSTRUCTIONS:
1. Be specific - don't give generic insights, extract actual content from the call
2. Include direct quotes when possible (in quotes)
3. Rate confidence: high (explicitly stated), medium (strongly implied), low (inferred)
4. For social messaging, extract punchy 1-2 sentence quotes that would work on LinkedIn/Twitter
5. For testimonials, capture genuine positive statements with attribution context
6. For product recommendations, note specific features or integrations mentioned
7. For FAQs, frame as questions a prospect might ask
8. For blog topics, suggest specific article titles based on pain points discussed

Return structured data with insights organized by category.
"""

    ROLLUP_PROMPT = """Analyze these insights from multiple sales calls and identify the top 5 recurring themes.

INSIGHTS FROM {num_calls} CALLS:
{all_insights}

For each theme:
1. Identify the core theme/pattern
2. Count how many times it appeared
3. Note which insight categories it spans
4. Provide 2-3 example insights that demonstrate this theme
5. List the call IDs where it appeared

Return a structured analysis of the top 5 most important/frequent themes.
"""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        project_name: Optional[str] = None,
    ):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Setup LangSmith tracing if enabled
        self._setup_langsmith(project_name)
        
        # Create LLM with structured output support
        self.llm_base = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        # Use with_structured_output for reliable structured parsing
        # This uses OpenAI's native structured output when available
        self.llm = self.llm_base.with_structured_output(AllCategoryInsights)
    
    def _setup_langsmith(self, project_name: Optional[str] = None):
        """Setup LangSmith tracing if enabled via environment variables."""
        # LangSmith is automatically enabled if LANGCHAIN_TRACING_V2=true
        # and LANGCHAIN_API_KEY is set in environment
        tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        
        if tracing_enabled:
            api_key = os.getenv("LANGCHAIN_API_KEY")
            if not api_key:
                print("⚠️  LangSmith tracing enabled but LANGCHAIN_API_KEY not set")
                return
            
            # Set project name if provided
            if project_name:
                os.environ["LANGCHAIN_PROJECT"] = project_name
            elif not os.getenv("LANGCHAIN_PROJECT"):
                # Default project name
                os.environ["LANGCHAIN_PROJECT"] = "meet-insights"
            
            print(f"✅ LangSmith tracing enabled (project: {os.getenv('LANGCHAIN_PROJECT')})")
    
    def _generate_insight_id(self, content: str, call_id: str) -> str:
        """Generate unique ID for an insight for deduplication."""
        hash_input = f"{content[:50]}:{call_id}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _normalize_for_match(self, s: str) -> str:
        """Normalize text for fuzzy matching."""
        s = s.lower()
        s = re.sub(r"[\u2018\u2019\u201c\u201d]", '"', s)  # curly quotes to straight-ish
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _best_segment_for_quote(self, transcript: Transcript, quote: str):
        """Find the best matching transcript segment for a quote."""
        if not quote or not transcript.segments:
            return None

        qn = self._normalize_for_match(quote)
        if not qn:
            return None

        best = None
        best_score = 0.0

        for seg in transcript.segments:
            if not seg.text:
                continue
            sn = self._normalize_for_match(seg.text)
            if not sn:
                continue

            # Prefer direct containment (high confidence)
            if qn in sn or sn in qn:
                score = 1.0
            else:
                score = SequenceMatcher(None, qn, sn).ratio()

            if score > best_score:
                best_score = score
                best = seg

        # Heuristic threshold: only accept decent matches
        if best_score >= 0.55:
            return best
        return None

    def _map_confidence(self, conf_str: str) -> ConfidenceLevel:
        """Map string confidence to enum."""
        conf_lower = conf_str.lower()
        if "high" in conf_lower:
            return ConfidenceLevel.HIGH
        elif "low" in conf_lower:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.MEDIUM
    
    def _convert_to_insights(
        self,
        extracted: list[ExtractedInsightItem],
        transcript: Transcript,
    ) -> list[Insight]:
        """Convert extracted items to Insight models."""
        insights = []
        for item in extracted:
            matched_segment = None
            if item.direct_quote:
                matched_segment = self._best_segment_for_quote(transcript, item.direct_quote)

            speaker_name = matched_segment.speaker_name if matched_segment else None
            timestamp = None
            if matched_segment:
                timestamp = matched_segment.timestamp_display
            else:
                timestamp = item.timestamp_hint

            source = SourceReference(
                call_id=transcript.metadata.call_id,
                call_date=transcript.metadata.call_date,
                rep_name=transcript.metadata.rep_name,
                speaker_name=speaker_name,
                company_name=transcript.metadata.company_name,
                timestamp=timestamp,
                quote_snippet=item.direct_quote,
            )
            
            insight = Insight(
                id=self._generate_insight_id(item.content, transcript.metadata.call_id),
                content=item.content,
                confidence=self._map_confidence(item.confidence),
                source=source,
                direct_quote=item.direct_quote,
            )
            insights.append(insight)
        
        return insights
    
    async def extract_from_transcript(self, transcript: Transcript) -> InsightExtractionResult:
        """Extract insights from a single transcript using structured output."""
        import time
        start_time = time.time()
        
        prompt = ChatPromptTemplate.from_template(self.EXTRACTION_PROMPT)
        
        # Chain with structured output - LLM returns Pydantic model directly
        chain = prompt | self.llm
        
        # Create config with metadata for LangSmith tracing
        config = RunnableConfig(
            metadata={
                "call_id": transcript.metadata.call_id,
                "rep_name": transcript.metadata.rep_name,
                "company_name": transcript.metadata.company_name or "Unknown",
                "call_date": transcript.metadata.call_date_formatted,
                "call_type": transcript.metadata.call_type or "Sales Call",
            },
            tags=["insight-extraction", "transcript-analysis"],
        )
        
        result = await chain.ainvoke(
            {
                "call_date": transcript.metadata.call_date_formatted,
                "rep_name": transcript.metadata.rep_name,
                "company_name": transcript.metadata.company_name or "Unknown",
                "call_type": transcript.metadata.call_type or "Sales Call",
                "transcript_text": transcript.full_text[:15000],  # Limit for token constraints
            },
            config=config,
        )
        
        # Convert to CallInsights
        call_insights = CallInsights(
            call_ids=[transcript.metadata.call_id],
            processed_at=datetime.now(),
            product_recommendations=ProductRecommendations(
                insights=self._convert_to_insights(
                    result.product_recommendations.insights, transcript
                )
            ),
            positive_feedback=PositiveFeedback(
                insights=self._convert_to_insights(
                    result.positive_feedback.insights, transcript
                )
            ),
            marketing_messaging=MarketingMessaging(
                insights=self._convert_to_insights(
                    result.marketing_messaging.insights, transcript
                )
            ),
            social_messaging=SocialMessaging(
                insights=self._convert_to_insights(
                    result.social_messaging.insights, transcript
                )
            ),
            faq_ideas=FAQIdeas(
                insights=self._convert_to_insights(
                    result.faq_ideas.insights, transcript
                )
            ),
            blog_topics=BlogTopics(
                insights=self._convert_to_insights(
                    result.blog_topics.insights, transcript
                )
            ),
        )
        
        processing_time = time.time() - start_time
        
        return InsightExtractionResult(
            insights=call_insights,
            processing_time_seconds=processing_time,
        )
    
    def extract_from_transcript_sync(self, transcript: Transcript) -> InsightExtractionResult:
        """Synchronous version of extract_from_transcript."""
        import asyncio
        return asyncio.run(self.extract_from_transcript(transcript))
    
    async def extract_from_collection(
        self, 
        collection: TranscriptCollection,
        deduplicate: bool = True,
    ) -> InsightExtractionResult:
        """Extract and merge insights from multiple transcripts."""
        import time
        start_time = time.time()
        
        all_call_ids = []
        all_product = []
        all_positive = []
        all_marketing = []
        all_social = []
        all_faq = []
        all_blog = []
        
        for transcript in collection.transcripts:
            result = await self.extract_from_transcript(transcript)
            insights = result.insights
            
            all_call_ids.extend(insights.call_ids)
            all_product.extend(insights.product_recommendations.insights)
            all_positive.extend(insights.positive_feedback.insights)
            all_marketing.extend(insights.marketing_messaging.insights)
            all_social.extend(insights.social_messaging.insights)
            all_faq.extend(insights.faq_ideas.insights)
            all_blog.extend(insights.blog_topics.insights)
        
        # Deduplicate if requested
        if deduplicate:
            from ..utils.deduplication import deduplicate_insights
            all_product = deduplicate_insights(all_product)
            all_positive = deduplicate_insights(all_positive)
            all_marketing = deduplicate_insights(all_marketing)
            all_social = deduplicate_insights(all_social)
            all_faq = deduplicate_insights(all_faq)
            all_blog = deduplicate_insights(all_blog)
        
        merged_insights = CallInsights(
            call_ids=all_call_ids,
            processed_at=datetime.now(),
            product_recommendations=ProductRecommendations(insights=all_product),
            positive_feedback=PositiveFeedback(insights=all_positive),
            marketing_messaging=MarketingMessaging(insights=all_marketing),
            social_messaging=SocialMessaging(insights=all_social),
            faq_ideas=FAQIdeas(insights=all_faq),
            blog_topics=BlogTopics(insights=all_blog),
        )
        
        processing_time = time.time() - start_time
        
        return InsightExtractionResult(
            insights=merged_insights,
            processing_time_seconds=processing_time,
        )
    
    async def generate_weekly_rollup(
        self,
        insights: CallInsights,
        week_start: datetime,
        week_end: datetime,
    ) -> WeeklyRollup:
        """Generate a weekly rollup with top themes."""
        
        # Prepare insights summary for LLM
        all_insights_text = []
        for category_name in [
            "product_recommendations", "positive_feedback", "marketing_messaging",
            "social_messaging", "faq_ideas", "blog_topics"
        ]:
            category = getattr(insights, category_name)
            for insight in category.insights:
                all_insights_text.append(
                    f"[{category_name}] {insight.content} (Call: {insight.source.call_id})"
                )
        
        # Use LLM to identify themes with structured output
        class ThemeAnalysis(BaseModel):
            themes: list[ThemeSummary] = Field(description="Top 5 recurring themes")
        
        # Create a separate LLM instance with structured output for theme analysis
        theme_llm = self.llm_base.with_structured_output(ThemeAnalysis)
        prompt = ChatPromptTemplate.from_template(self.ROLLUP_PROMPT)
        chain = prompt | theme_llm
        
        # Config for theme analysis tracing
        config = RunnableConfig(
            metadata={
                "num_calls": len(insights.call_ids),
                "total_insights": insights.total_insights,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
            },
            tags=["weekly-rollup", "theme-analysis"],
        )
        
        result = await chain.ainvoke(
            {
                "num_calls": len(insights.call_ids),
                "all_insights": "\n".join(all_insights_text[:100]),  # Limit
            },
            config=config,
        )
        
        return WeeklyRollup(
            week_start=week_start,
            week_end=week_end,
            total_calls_processed=len(insights.call_ids),
            total_insights_extracted=insights.total_insights,
            top_themes=result.themes[:5],
            insights_by_category={
                "Product Recommendations": len(insights.product_recommendations.insights),
                "Positive Feedback": len(insights.positive_feedback.insights),
                "Marketing Messaging": len(insights.marketing_messaging.insights),
                "Social Messaging": len(insights.social_messaging.insights),
                "FAQ Ideas": len(insights.faq_ideas.insights),
                "Blog Topics": len(insights.blog_topics.insights),
            },
            reps_analyzed=list(set(
                insight.source.rep_name 
                for insight in insights.product_recommendations.insights
            )),
        )

