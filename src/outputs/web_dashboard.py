"""FastAPI web dashboard for insights visualization."""

import os
import asyncio
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Request, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..models.insights import CallInsights, WeeklyRollup, InsightCategory
from ..models.transcript import TranscriptCollection


class WebDashboard:
    """Web dashboard state manager."""
    
    def __init__(self):
        self.current_insights: Optional[CallInsights] = None
        self.weekly_rollup: Optional[WeeklyRollup] = None
        self.last_updated: Optional[datetime] = None
        # History of individual runs/uploads (not aggregated)
        self.history: list[CallInsights] = []
    
    def update(self, insights: CallInsights, rollup: Optional[WeeklyRollup] = None):
        """Update dashboard with new insights."""
        self.current_insights = insights
        self.weekly_rollup = rollup
        self.last_updated = datetime.now()
        self.history.append(insights)
        # Keep last 10 runs
        if len(self.history) > 10:
            self.history = self.history[-10:]


# Global dashboard instance
dashboard = WebDashboard()


def _merge_call_insights(base: CallInsights, new: CallInsights) -> CallInsights:
    """Merge insights from a new run into an existing CallInsights object."""
    # Extend call IDs
    merged_call_ids = list({*base.call_ids, *new.call_ids})

    def _merge_category(cat_name: InsightCategory):
        base_cat = base.get_category(cat_name)
        new_cat = new.get_category(cat_name)
        base_cat.insights.extend(new_cat.insights)

    for cat in InsightCategory:
        _merge_category(cat)

    base.call_ids = merged_call_ids
    base.processed_at = datetime.now()
    return base


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Meet Insights Dashboard",
        description="Chorus call transcript insights visualization",
        version="1.0.0",
    )
    
    # Setup templates
    templates_dir = Path(__file__).parent.parent.parent / "web" / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    
    # Setup static files
    static_dir = Path(__file__).parent.parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Main dashboard page (aggregated insights)."""
        # Build session list metadata for navigation
        sessions = []
        for idx, ci in enumerate(dashboard.history):
            sessions.append(
                {
                    "index": idx,
                    "label": f"Session {idx + 1}",
                    "calls": len(ci.call_ids),
                    "total_insights": ci.total_insights,
                    "processed_at": ci.processed_at,
                }
            )

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "insights": dashboard.current_insights,
                "rollup": dashboard.weekly_rollup,
                "last_updated": dashboard.last_updated,
                "session_index": None,
                "sessions": sessions,
            }
        )

    @app.get("/sessions/{index}", response_class=HTMLResponse)
    async def session_view(request: Request, index: int):
        """View insights from a specific upload/run without aggregation."""
        if index < 0 or index >= len(dashboard.history):
            raise HTTPException(status_code=404, detail="Session not found")

        insights = dashboard.history[index]

        # Build session list metadata for navigation
        sessions = []
        for idx, ci in enumerate(dashboard.history):
            sessions.append(
                {
                    "index": idx,
                    "label": f"Session {idx + 1}",
                    "calls": len(ci.call_ids),
                    "total_insights": ci.total_insights,
                    "processed_at": ci.processed_at,
                }
            )

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "insights": insights,
                "rollup": None,
                "last_updated": dashboard.last_updated,
                "session_index": index,
                "sessions": sessions,
            }
        )
    
    @app.get("/api/insights")
    async def get_insights():
        """API endpoint for insights data."""
        if not dashboard.current_insights:
            return {"status": "no_data", "message": "No insights available. Run the pipeline first."}
        
        insights = dashboard.current_insights
        return {
            "status": "ok",
            "last_updated": dashboard.last_updated.isoformat() if dashboard.last_updated else None,
            "total_calls": len(insights.call_ids),
            "total_insights": insights.total_insights,
            "categories": {
                "product_recommendations": [
                    {"content": i.content, "confidence": i.confidence, "source": i.source.format_reference()}
                    for i in insights.product_recommendations.insights
                ],
                "positive_feedback": [
                    {"content": i.content, "confidence": i.confidence, "source": i.source.format_reference(), "quote": i.direct_quote}
                    for i in insights.positive_feedback.insights
                ],
                "marketing_messaging": [
                    {"content": i.content, "confidence": i.confidence, "source": i.source.format_reference()}
                    for i in insights.marketing_messaging.insights
                ],
                "social_messaging": [
                    {"content": i.content, "confidence": i.confidence, "source": i.source.format_reference(), "quote": i.direct_quote}
                    for i in insights.social_messaging.insights
                ],
                "faq_ideas": [
                    {"content": i.content, "confidence": i.confidence, "source": i.source.format_reference()}
                    for i in insights.faq_ideas.insights
                ],
                "blog_topics": [
                    {"content": i.content, "confidence": i.confidence, "source": i.source.format_reference()}
                    for i in insights.blog_topics.insights
                ],
            }
        }
    
    @app.get("/api/rollup")
    async def get_rollup():
        """API endpoint for weekly rollup."""
        if not dashboard.weekly_rollup:
            return {"status": "no_data", "message": "No rollup available."}
        
        rollup = dashboard.weekly_rollup
        return {
            "status": "ok",
            "week_start": rollup.week_start.isoformat(),
            "week_end": rollup.week_end.isoformat(),
            "total_calls": rollup.total_calls_processed,
            "total_insights": rollup.total_insights_extracted,
            "top_themes": [
                {
                    "theme": t.theme,
                    "count": t.occurrence_count,
                    "categories": t.categories,
                    "examples": t.example_insights,
                }
                for t in rollup.top_themes
            ],
            "insights_by_category": rollup.insights_by_category,
            "reps": rollup.reps_analyzed,
        }
    
    @app.get("/api/filter")
    async def filter_insights(
        rep: Optional[str] = Query(None, description="Filter by rep name"),
        date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
        category: Optional[str] = Query(None, description="Filter by category"),
    ):
        """Filter insights by various criteria."""
        if not dashboard.current_insights:
            return {"status": "no_data"}
        
        insights = dashboard.current_insights
        result = {}
        
        category_map = {
            "product": insights.product_recommendations,
            "feedback": insights.positive_feedback,
            "marketing": insights.marketing_messaging,
            "social": insights.social_messaging,
            "faq": insights.faq_ideas,
            "blog": insights.blog_topics,
        }
        
        for cat_name, cat_data in category_map.items():
            if category and cat_name != category:
                continue
            
            filtered = []
            for insight in cat_data.insights:
                # Filter by rep
                if rep and rep.lower() not in insight.source.rep_name.lower():
                    continue
                # Filter by date
                if date:
                    insight_date = insight.source.call_date.strftime("%Y-%m-%d")
                    if insight_date != date:
                        continue
                
                filtered.append({
                    "content": insight.content,
                    "confidence": insight.confidence,
                    "source": insight.source.format_reference(),
                    "quote": insight.direct_quote,
                })
            
            result[cat_name] = filtered
        
        return {"status": "ok", "results": result}
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "has_data": dashboard.current_insights is not None,
            "last_updated": dashboard.last_updated.isoformat() if dashboard.last_updated else None,
        }
    
    @app.post("/api/analyze/text")
    async def analyze_text(
        text: str = Form(..., description="Raw transcript text to analyze"),
        rep_name: str = Form("Unknown Rep", description="Sales rep name"),
        company_name: Optional[str] = Form(None, description="Company name"),
    ):
        """Analyze pasted transcript text and extract insights."""
        if not text or len(text.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="Transcript text is too short. Please provide at least 50 characters."
            )
        
        try:
            from ..loaders.file_loader import FileLoader
            from ..extractors.insight_extractor import InsightExtractor
            from ..config import get_settings
            
            settings = get_settings()
            
            # Create transcript from pasted text
            loader = FileLoader()
            transcript = loader.load_from_text(
                text=text,
                rep_name=rep_name,
                company_name=company_name,
            )
            
            # Extract insights
            extractor = InsightExtractor(model_name=settings.openai_model)
            result = await extractor.extract_from_transcript(transcript)

            # Record this run in history
            dashboard.history.append(result.insights)
            if len(dashboard.history) > 20:
                dashboard.history = dashboard.history[-20:]

            # Merge into aggregated insights (current_insights)
            if dashboard.current_insights:
                dashboard.current_insights = _merge_call_insights(
                    dashboard.current_insights, result.insights
                )
            else:
                dashboard.current_insights = result.insights

            dashboard.last_updated = datetime.now()
            session_index = len(dashboard.history) - 1

            return JSONResponse({
                "status": "success",
                "message": "Transcript analyzed successfully",
                "total_insights": result.insights.total_insights,
                "processing_time": result.processing_time_seconds,
                "redirect": f"/sessions/{session_index}",
                "session_index": session_index,
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    @app.post("/api/analyze/file")
    async def analyze_file(
        file: UploadFile = File(..., description="Transcript file (PDF or TXT)"),
        rep_name: str = Form("Unknown Rep", description="Sales rep name"),
        company_name: Optional[str] = Form(None, description="Company name"),
    ):
        """Analyze uploaded transcript file (PDF or TXT) and extract insights."""
        # Validate file type
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        
        if ext not in {".pdf", ".txt", ".json"}:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: .pdf, .txt, .json"
            )
        
        try:
            from ..loaders.file_loader import FileLoader
            from ..extractors.insight_extractor import InsightExtractor
            from ..config import get_settings
            
            settings = get_settings()
            
            # Read file content
            content = await file.read()
            
            loader = FileLoader()
            
            if ext == ".pdf":
                transcript = loader.load_from_pdf_bytes(
                    pdf_bytes=content,
                    rep_name=rep_name,
                    company_name=company_name,
                    filename=filename,
                )
            elif ext == ".txt":
                text = content.decode("utf-8")
                transcript = loader.load_from_text(
                    text=text,
                    rep_name=rep_name,
                    company_name=company_name,
                )
            elif ext == ".json":
                import json
                import tempfile
                # Write to temp file for JSON loader
                with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = Path(tmp.name)
                try:
                    transcript = loader.load_json_transcript(tmp_path)
                finally:
                    tmp_path.unlink()
            
            # Extract insights
            extractor = InsightExtractor(model_name=settings.openai_model)
            result = await extractor.extract_from_transcript(transcript)

            # Record this run in history
            dashboard.history.append(result.insights)
            if len(dashboard.history) > 20:
                dashboard.history = dashboard.history[-20:]

            # Merge into aggregated insights (current_insights)
            if dashboard.current_insights:
                dashboard.current_insights = _merge_call_insights(
                    dashboard.current_insights, result.insights
                )
            else:
                dashboard.current_insights = result.insights

            dashboard.last_updated = datetime.now()
            session_index = len(dashboard.history) - 1

            return JSONResponse({
                "status": "success",
                "message": f"File '{filename}' analyzed successfully",
                "total_insights": result.insights.total_insights,
                "processing_time": result.processing_time_seconds,
                "redirect": f"/sessions/{session_index}",
                "session_index": session_index,
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    return app


def update_dashboard(insights: CallInsights, rollup: Optional[WeeklyRollup] = None):
    """Update the global dashboard with new insights."""
    dashboard.update(insights, rollup)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the dashboard server."""
    import uvicorn
    
    host = os.getenv("WEB_HOST", host)
    port = int(os.getenv("WEB_PORT", port))
    
    app = create_app()
    uvicorn.run(app, host=host, port=port)

