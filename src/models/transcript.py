"""Pydantic models for transcript data structures."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Speaker(str, Enum):
    """Speaker types in a call transcript."""
    REP = "rep"
    PROSPECT = "prospect"
    UNKNOWN = "unknown"


class TranscriptSegment(BaseModel):
    """A single segment of a transcript with speaker and timing info."""
    
    model_config = {"use_enum_values": True}
    
    speaker: Speaker = Field(
        description="Who is speaking in this segment"
    )
    speaker_name: Optional[str] = Field(
        default=None,
        description="Name of the speaker if known"
    )
    text: str = Field(
        description="The spoken text content"
    )
    start_time: Optional[float] = Field(
        default=None,
        description="Start time in seconds from call beginning"
    )
    end_time: Optional[float] = Field(
        default=None,
        description="End time in seconds from call beginning"
    )
    timestamp_str: Optional[str] = Field(
        default=None,
        description="Original timestamp string if available (e.g. HH:MM:SS)"
    )
    
    @property
    def timestamp(self) -> Optional[str]:
        """Format timestamp for display (MM:SS by default)."""
        if self.start_time is None:
            return None
        minutes = int(self.start_time // 60)
        seconds = int(self.start_time % 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def timestamp_display(self) -> Optional[str]:
        """Best-effort timestamp for display (prefer original HH:MM:SS if present)."""
        return self.timestamp_str or self.timestamp


class CallMetadata(BaseModel):
    """Metadata about a sales call."""
    
    call_id: str = Field(
        description="Unique identifier for the call"
    )
    call_date: datetime = Field(
        description="Date and time when the call occurred"
    )
    rep_name: str = Field(
        description="Name of the sales representative"
    )
    rep_email: Optional[str] = Field(
        default=None,
        description="Email of the sales representative"
    )
    prospect_name: Optional[str] = Field(
        default=None,
        description="Name of the prospect/customer"
    )
    company_name: Optional[str] = Field(
        default=None,
        description="Company name of the prospect"
    )
    call_duration_seconds: Optional[int] = Field(
        default=None,
        description="Total duration of the call in seconds"
    )
    call_type: Optional[str] = Field(
        default=None,
        description="Type of call (discovery, demo, follow-up, etc.)"
    )
    deal_stage: Optional[str] = Field(
        default=None,
        description="Current deal stage if available"
    )
    
    @property
    def call_date_formatted(self) -> str:
        """Format call date for display."""
        return self.call_date.strftime("%Y-%m-%d")
    
    @property
    def duration_formatted(self) -> Optional[str]:
        """Format duration for display."""
        if self.call_duration_seconds is None:
            return None
        minutes = self.call_duration_seconds // 60
        seconds = self.call_duration_seconds % 60
        return f"{minutes}m {seconds}s"


class Transcript(BaseModel):
    """Complete transcript with metadata and segments."""
    
    metadata: CallMetadata = Field(
        description="Call metadata information"
    )
    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="List of transcript segments"
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Raw transcript text if segments not available"
    )
    
    @property
    def full_text(self) -> str:
        """Get the complete transcript as text."""
        if self.raw_text:
            return self.raw_text
        
        lines = []
        for segment in self.segments:
            speaker_label = segment.speaker_name or segment.speaker.upper()
            ts = segment.timestamp_display
            timestamp = f"[{ts}] " if ts else ""
            lines.append(f"{timestamp}{speaker_label}: {segment.text}")
        
        return "\n".join(lines)
    
    @property
    def word_count(self) -> int:
        """Count total words in transcript."""
        return len(self.full_text.split())


class TranscriptCollection(BaseModel):
    """Collection of transcripts for batch processing."""
    
    transcripts: list[Transcript] = Field(
        default_factory=list,
        description="List of transcripts to process"
    )
    date_range_start: Optional[datetime] = Field(
        default=None,
        description="Start of date range for this collection"
    )
    date_range_end: Optional[datetime] = Field(
        default=None,
        description="End of date range for this collection"
    )
    
    @property
    def total_calls(self) -> int:
        """Total number of calls in collection."""
        return len(self.transcripts)
    
    @property
    def reps(self) -> list[str]:
        """Unique rep names in collection."""
        return list(set(t.metadata.rep_name for t in self.transcripts))
    
    @property
    def companies(self) -> list[str]:
        """Unique company names in collection."""
        return list(set(
            t.metadata.company_name 
            for t in self.transcripts 
            if t.metadata.company_name
        ))

