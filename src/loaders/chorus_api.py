"""Chorus API integration for loading transcripts."""

import os
from datetime import datetime, timedelta
from typing import Optional
import httpx
import uuid

from ..models.transcript import (
    Transcript,
    TranscriptCollection,
    CallMetadata,
    TranscriptSegment,
    Speaker,
)


class ChorusAPILoader:
    """Load transcripts from Chorus API.
    
    Note: This is a template implementation. Actual Chorus API
    endpoints and authentication may differ. Update as needed
    based on Chorus API documentation.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("CHORUS_API_KEY")
        self.api_url = api_url or os.getenv("CHORUS_API_URL", "https://api.chorus.ai/v1")
        
        if not self.api_key:
            raise ValueError(
                "Chorus API key required. Set CHORUS_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _fetch(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated request to Chorus API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/{endpoint}",
                headers=self.headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_calls(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        rep_email: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch list of calls from Chorus."""
        params = {"limit": limit}
        
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if rep_email:
            params["rep_email"] = rep_email
        
        # Note: Actual endpoint may differ
        data = await self._fetch("calls", params)
        return data.get("calls", [])
    
    async def get_transcript(self, call_id: str) -> dict:
        """Fetch transcript for a specific call."""
        # Note: Actual endpoint may differ
        return await self._fetch(f"calls/{call_id}/transcript")
    
    def _parse_chorus_call(self, call_data: dict, transcript_data: dict) -> Transcript:
        """Parse Chorus API response into Transcript model."""
        # Parse metadata
        metadata = CallMetadata(
            call_id=call_data.get("id", str(uuid.uuid4())[:8]),
            call_date=datetime.fromisoformat(
                call_data.get("date", datetime.now().isoformat())
            ),
            rep_name=call_data.get("rep_name", "Unknown Rep"),
            rep_email=call_data.get("rep_email"),
            prospect_name=call_data.get("prospect_name"),
            company_name=call_data.get("company_name"),
            call_duration_seconds=call_data.get("duration_seconds"),
            call_type=call_data.get("call_type"),
            deal_stage=call_data.get("deal_stage"),
        )
        
        # Parse segments
        segments = []
        for utterance in transcript_data.get("utterances", []):
            # Determine speaker type
            speaker_role = utterance.get("speaker_role", "").lower()
            if speaker_role in ["rep", "sales", "internal"]:
                speaker = Speaker.REP
            elif speaker_role in ["prospect", "customer", "external"]:
                speaker = Speaker.PROSPECT
            else:
                speaker = Speaker.UNKNOWN
            
            segments.append(TranscriptSegment(
                speaker=speaker,
                speaker_name=utterance.get("speaker_name"),
                text=utterance.get("text", ""),
                start_time=utterance.get("start_time"),
                end_time=utterance.get("end_time"),
            ))
        
        return Transcript(
            metadata=metadata,
            segments=segments,
        )
    
    async def load_recent(self, days: int = 7, limit: int = 50) -> TranscriptCollection:
        """Load transcripts from recent days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        calls = await self.get_calls(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        
        transcripts = []
        for call in calls:
            try:
                transcript_data = await self.get_transcript(call["id"])
                transcript = self._parse_chorus_call(call, transcript_data)
                transcripts.append(transcript)
            except Exception as e:
                print(f"Error loading transcript for call {call.get('id')}: {e}")
        
        return TranscriptCollection(
            transcripts=transcripts,
            date_range_start=start_date,
            date_range_end=end_date,
        )
    
    async def load_by_rep(self, rep_email: str, days: int = 7) -> TranscriptCollection:
        """Load transcripts for a specific rep."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        calls = await self.get_calls(
            start_date=start_date,
            end_date=end_date,
            rep_email=rep_email,
        )
        
        transcripts = []
        for call in calls:
            try:
                transcript_data = await self.get_transcript(call["id"])
                transcript = self._parse_chorus_call(call, transcript_data)
                transcripts.append(transcript)
            except Exception as e:
                print(f"Error loading transcript for call {call.get('id')}: {e}")
        
        return TranscriptCollection(
            transcripts=transcripts,
            date_range_start=start_date,
            date_range_end=end_date,
        )


class MockChorusLoader:
    """Mock loader that returns sample data for testing without API access."""
    
    def __init__(self):
        from .file_loader import FileLoader
        self.file_loader = FileLoader()
    
    async def load_recent(self, days: int = 7, limit: int = 50) -> TranscriptCollection:
        """Load from local sample files instead of API."""
        return self.file_loader.load_all()
    
    async def load_by_rep(self, rep_email: str, days: int = 7) -> TranscriptCollection:
        """Load from local sample files filtered by rep."""
        # Extract name from email for matching
        rep_name = rep_email.split("@")[0].replace(".", " ").title()
        return self.file_loader.load_by_rep(rep_name)

