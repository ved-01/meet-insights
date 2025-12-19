#!/usr/bin/env python3
"""
Meet Insights - Main CLI Entry Point

Convert Chorus call transcripts into categorized, actionable insights.

Usage:
    python run.py                              # Process all transcripts in data dir
    python run.py --file transcript.pdf        # Process a single file (PDF/TXT/JSON)
    python run.py --output docs                # Output to Google Docs
    python run.py --output web                 # Output to web dashboard
    python run.py --output both                # Output to both
    python run.py --output markdown            # Output to local markdown file
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_settings
from src.loaders.file_loader import FileLoader
from src.extractors.insight_extractor import InsightExtractor
from src.outputs.google_docs import GoogleDocsOutput, MockGoogleDocsOutput
from src.outputs.web_dashboard import update_dashboard, run_server, create_app

# Initialize CLI
app = typer.Typer(
    name="meet-insights",
    help="Convert Chorus call transcripts into categorized insights",
    add_completion=False,
    no_args_is_help=False,  # Allow running without args
)
console = Console()


def print_banner():
    """Print application banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   📊  MEET INSIGHTS                                          ║
║   ─────────────────────────────────────────────────────────  ║
║   Transform call transcripts into actionable insights        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def print_insights_summary(insights, title: str = "Extraction Complete"):
    """Print a summary table of extracted insights."""
    table = Table(title=f"📈 {title}", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    table.add_row("🚀 Product Recommendations", str(len(insights.product_recommendations.insights)))
    table.add_row("⭐ Positive Feedback", str(len(insights.positive_feedback.insights)))
    table.add_row("📣 Marketing Messaging", str(len(insights.marketing_messaging.insights)))
    table.add_row("📱 Social Messaging", str(len(insights.social_messaging.insights)))
    table.add_row("❓ FAQ Ideas", str(len(insights.faq_ideas.insights)))
    table.add_row("📝 Blog Topics", str(len(insights.blog_topics.insights)))
    table.add_row("─" * 25, "─" * 5)
    table.add_row("Total Insights", str(insights.total_insights), style="bold")
    
    console.print(table)


async def process_transcripts(
    data_dir: str,
    deduplicate: bool = True,
) -> tuple:
    """Load and process transcripts."""
    settings = get_settings()
    
    # Load transcripts
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading transcripts...", total=None)
        
        loader = FileLoader(data_dir=data_dir)
        collection = loader.load_all()
        
        progress.update(task, description=f"Loaded {collection.total_calls} transcripts")
    
    if collection.total_calls == 0:
        console.print("[yellow]⚠️  No transcripts found in data directory[/yellow]")
        console.print(f"   Looking in: {data_dir}")
        console.print("   Add JSON, TXT, or PDF transcript files to process.")
        return None, None
    
    console.print(f"\n[green]✓[/green] Found {collection.total_calls} transcripts")
    console.print(f"  Reps: {', '.join(collection.reps)}")
    if collection.companies:
        console.print(f"  Companies: {', '.join(collection.companies)}")
    
        # Extract insights
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting insights with AI...", total=None)
            
            # Setup project name for LangSmith tracing
            project_name = None
            if settings.langchain_tracing_v2:
                project_name = settings.langchain_project or "meet-insights"
            
            extractor = InsightExtractor(
                model_name=settings.openai_model,
                project_name=project_name,
            )
            result = await extractor.extract_from_collection(
                collection, 
                deduplicate=deduplicate
            )
            
            progress.update(task, description="Extraction complete!")
    
    console.print(f"\n[green]✓[/green] Processed in {result.processing_time_seconds:.1f} seconds")
    
    # Generate weekly rollup if multiple calls
    rollup = None
    if len(result.insights.call_ids) > 1:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating weekly rollup...", total=None)
            
            week_end = datetime.now()
            week_start = week_end - timedelta(days=7)
            
            try:
                rollup = await extractor.generate_weekly_rollup(
                    result.insights,
                    week_start,
                    week_end,
                )
                progress.update(task, description="Rollup generated!")
            except Exception as e:
                console.print(f"[yellow]⚠️  Could not generate rollup: {e}[/yellow]")
    
    return result.insights, rollup


async def process_single_file(
    file_path: str,
    rep_name: str = "Unknown Rep",
    company_name: Optional[str] = None,
) -> tuple:
    """Load and process a single transcript file (PDF, TXT, or JSON)."""
    settings = get_settings()
    
    file_path_obj = Path(file_path)
    
    # Load single file
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Loading {file_path_obj.name}...", total=None)
        
        loader = FileLoader()
        try:
            transcript = loader.load_single_file(
                file_path_obj,
                rep_name=rep_name,
                company_name=company_name,
            )
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to load file: {e}")
            return None, None
        
        # Wrap in a collection for consistent processing
        from src.models.transcript import TranscriptCollection
        collection = TranscriptCollection(transcripts=[transcript])
        
        progress.update(task, description=f"Loaded: {file_path_obj.name}")
    
    console.print(f"\n[green]✓[/green] Loaded transcript: {file_path_obj.name}")
    console.print(f"  Rep: {transcript.metadata.rep_name}")
    if transcript.metadata.company_name:
        console.print(f"  Company: {transcript.metadata.company_name}")
    console.print(f"  Text length: {len(transcript.full_text):,} characters")
    
    # Extract insights
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting insights with AI...", total=None)
        
        # Setup project name for LangSmith tracing
        project_name = None
        if settings.langchain_tracing_v2:
            project_name = settings.langchain_project or "meet-insights"
        
        extractor = InsightExtractor(
            model_name=settings.openai_model,
            project_name=project_name,
        )
        result = await extractor.extract_from_transcript(transcript)
        
        progress.update(task, description="Extraction complete!")
    
    console.print(f"\n[green]✓[/green] Processed in {result.processing_time_seconds:.1f} seconds")
    
    return result.insights, None  # No rollup for single file


def output_to_markdown(insights, rollup, output_path: str = "output/insights.md"):
    """Output insights to a markdown file."""
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    mock_docs = MockGoogleDocsOutput()
    doc_id = mock_docs.write_insights(insights, weekly_rollup=rollup)
    mock_docs.save_to_file(doc_id, output_path)
    
    console.print(f"\n[green]✓[/green] Saved to: {output_path}")
    return output_path


def output_to_google_docs(insights, rollup) -> Optional[str]:
    """Output insights to Google Docs using OAuth 2.0."""
    settings = get_settings()

    try:
        docs_output = GoogleDocsOutput(
            folder_id=settings.google_doc_folder_id,
        )
        
        # Check if authentication succeeded
        if not docs_output.docs_service:
            console.print("[yellow]⚠️  Google authentication failed[/yellow]")
            console.print("   Make sure Docs & Drive APIs are enabled and your OAuth client JSON is valid.")
            console.print("\n   Falling back to local markdown output...")
            return output_to_markdown(insights, rollup)
        
        doc_id = docs_output.write_insights(insights, weekly_rollup=rollup)
        doc_url = docs_output.get_document_url(doc_id)
        
        console.print(f"\n[green]✓[/green] Created Google Doc")
        console.print(f"   URL: {doc_url}")

        if docs_output.get_user_email():
            console.print(f"   Created by: {docs_output.get_user_email()}")
        
        return doc_url
    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]✗[/red] Google Docs error: {e}")
        
        # Provide helpful guidance for 403 errors
        if "403" in error_msg or "permission" in error_msg.lower():
            console.print("\n[yellow]💡 This is a permission error. Common fixes:[/yellow]")

            console.print("   1. Enable Google Docs API and Google Drive API for your project")
            console.print("      → https://console.cloud.google.com/apis/library/docs.googleapis.com")
            console.print("      → https://console.cloud.google.com/apis/library/drive.googleapis.com")

            console.print("\n   2. Make sure the folder (if configured) is shared with your account")
            console.print("      → Check GOOGLE_DOC_FOLDER_ID in your .env")

        console.print("\n   Falling back to local markdown output...")
        return output_to_markdown(insights, rollup)


def start_web_dashboard(insights, rollup):
    """Start the web dashboard."""
    settings = get_settings()
    
    # Update dashboard with insights
    update_dashboard(insights, rollup)
    
    console.print(f"\n[green]✓[/green] Starting web dashboard...")
    console.print(f"   URL: http://{settings.web_host}:{settings.web_port}")
    console.print("\n   Press Ctrl+C to stop\n")
    
    run_server(host=settings.web_host, port=settings.web_port)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    output: str = typer.Option(
        "web",
        "--output", "-o",
        help="Output destination: web, docs, markdown, or both"
    ),
    data_dir: str = typer.Option(
        "data/sample_transcripts",
        "--data", "-d",
        help="Directory containing transcript files"
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file", "-f",
        help="Process a single transcript file (PDF, TXT, or JSON)"
    ),
    rep_name: str = typer.Option(
        "Unknown Rep",
        "--rep",
        help="Rep name for single file input (used with --file)"
    ),
    company_name: Optional[str] = typer.Option(
        None,
        "--company",
        help="Company name for single file input (used with --file)"
    ),
    no_dedupe: bool = typer.Option(
        False,
        "--no-dedupe",
        help="Disable insight deduplication"
    ),
    serve: bool = typer.Option(
        True,
        "--serve/--no-serve",
        help="Start web server after processing (for web output)"
    ),
):
    """
    Process call transcripts and extract categorized insights.
    
    Examples:
    
        python run.py                          # Process all files in data dir
        
        python run.py --file transcript.pdf    # Process a single PDF file
        
        python run.py -f call.txt --rep "Sarah Johnson" --company "Acme Corp"
        
        python run.py -o docs                  # Output to Google Docs (OAuth)
        
        python run.py -o markdown              # Output to local markdown
        
        python run.py -o both                  # Output to both docs and web
        
        python run.py -d /path/to/calls        # Use custom data directory
    """
    # If a subcommand was invoked, don't run main processing
    if ctx.invoked_subcommand is not None:
        return
    print_banner()
    
    # Check for API key
    settings = get_settings()
    if not settings.openai_api_key:
        console.print("[red]✗[/red] OPENAI_API_KEY not set!")
        console.print("   Copy .env.example to .env and add your API key")
        raise typer.Exit(1)
    
    # Process transcripts - either single file or directory
    try:
        if file:
            # Single file mode
            console.print(f"[cyan]📄 Single file mode:[/cyan] {file}")
            insights, rollup = asyncio.run(process_single_file(
                file_path=file,
                rep_name=rep_name,
                company_name=company_name,
            ))
        else:
            # Directory mode (default)
            insights, rollup = asyncio.run(process_transcripts(
                data_dir=data_dir,
                deduplicate=not no_dedupe,
            ))
    except Exception as e:
        console.print(f"[red]✗[/red] Processing error: {e}")
        raise typer.Exit(1)
    
    if insights is None:
        raise typer.Exit(1)
    
    # Print summary
    print_insights_summary(insights)
    
    # Print top themes if rollup available
    if rollup and rollup.top_themes:
        console.print("\n[bold]🔥 Top Themes:[/bold]")
        for i, theme in enumerate(rollup.top_themes[:5], 1):
            console.print(f"   {i}. {theme.theme} ({theme.occurrence_count}x)")
    
    # Output based on selection
    output = output.lower()
    
    if output in ("docs", "both"):
        output_to_google_docs(insights, rollup)
    
    if output in ("markdown",):
        output_to_markdown(insights, rollup)
    
    if output in ("web", "both"):
        if serve:
            start_web_dashboard(insights, rollup)
        else:
            update_dashboard(insights, rollup)
            console.print("\n[green]✓[/green] Dashboard updated")
            console.print("   Run with --serve to start the web server")


@app.command()
def serve_only():
    """Start the web dashboard without processing (show existing data)."""
    print_banner()
    settings = get_settings()
    
    console.print(f"[green]✓[/green] Starting web dashboard...")
    console.print(f"   URL: http://{settings.web_host}:{settings.web_port}")
    console.print("\n   Press Ctrl+C to stop\n")
    
    run_server(host=settings.web_host, port=settings.web_port)


@app.command()
def list_transcripts(
    data_dir: str = typer.Option(
        "data/sample_transcripts",
        "--data", "-d",
        help="Directory containing transcript files"
    ),
):
    """List available transcripts in the data directory."""
    print_banner()
    
    loader = FileLoader(data_dir=data_dir)
    collection = loader.load_all()
    
    if collection.total_calls == 0:
        console.print(f"[yellow]No transcripts found in {data_dir}[/yellow]")
        return
    
    table = Table(title="📞 Available Transcripts", show_header=True)
    table.add_column("Call ID", style="cyan")
    table.add_column("Date", style="green")
    table.add_column("Rep", style="yellow")
    table.add_column("Company", style="magenta")
    table.add_column("Type", style="blue")
    
    for t in collection.transcripts:
        table.add_row(
            t.metadata.call_id,
            t.metadata.call_date_formatted,
            t.metadata.rep_name,
            t.metadata.company_name or "—",
            t.metadata.call_type or "—",
        )
    
    console.print(table)


if __name__ == "__main__":
    app()

