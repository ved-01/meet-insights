"""File-based transcript loader for JSON/text/PDF files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
import uuid
import io
import re

from ..models.transcript import (
    Transcript,
    TranscriptCollection,
    CallMetadata,
    TranscriptSegment,
    Speaker,
)


def extract_text_from_pdf(file_path_or_bytes: Union[Path, bytes]) -> str:
    """Extract text content from a PDF file.
    
    Args:
        file_path_or_bytes: Either a Path to a PDF file or raw PDF bytes
        
    Returns:
        Extracted text from all pages
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF support. Install it with: pip install pypdf"
        )
    
    if isinstance(file_path_or_bytes, bytes):
        reader = PdfReader(io.BytesIO(file_path_or_bytes))
    else:
        reader = PdfReader(file_path_or_bytes)
    
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    
    return "\n\n".join(text_parts)


class FileLoader:
    """Load transcripts from local files (JSON, plain text, or PDF)."""
    
    SUPPORTED_EXTENSIONS = {".json", ".txt", ".pdf"}
    
    def __init__(self, data_dir: str = "data/sample_transcripts"):
        self.data_dir = Path(data_dir)
    
    def load_single_file(
        self,
        file_path: Union[str, Path],
        rep_name: str = "Unknown Rep",
        call_date: Optional[datetime] = None,
        company_name: Optional[str] = None,
    ) -> Transcript:
        """Load a single transcript file (auto-detects format by extension).
        
        Supports: .json, .txt, .pdf
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        ext = file_path.suffix.lower()
        
        if ext == ".json":
            return self.load_json_transcript(file_path)
        elif ext == ".txt":
            return self.load_text_transcript(
                file_path, rep_name=rep_name, call_date=call_date, company_name=company_name
            )
        elif ext == ".pdf":
            return self.load_pdf_transcript(
                file_path, rep_name=rep_name, call_date=call_date, company_name=company_name
            )
        else:
            raise ValueError(
                f"Unsupported file type: {ext}. Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )
    
    def load_json_transcript(self, file_path: Path) -> Transcript:
        """Load a transcript from a JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)
        
        # Parse metadata
        metadata_data = data.get("metadata", {})
        metadata = CallMetadata(
            call_id=metadata_data.get("call_id", str(uuid.uuid4())[:8]),
            call_date=datetime.fromisoformat(metadata_data.get("call_date", datetime.now().isoformat())),
            rep_name=metadata_data.get("rep_name", "Unknown Rep"),
            rep_email=metadata_data.get("rep_email"),
            prospect_name=metadata_data.get("prospect_name"),
            company_name=metadata_data.get("company_name"),
            call_duration_seconds=metadata_data.get("call_duration_seconds"),
            call_type=metadata_data.get("call_type"),
            deal_stage=metadata_data.get("deal_stage"),
        )
        
        # Parse segments
        segments = []
        for seg_data in data.get("segments", []):
            speaker_val = seg_data.get("speaker", "unknown").lower()
            speaker = Speaker(speaker_val) if speaker_val in [s.value for s in Speaker] else Speaker.UNKNOWN
            
            segment = TranscriptSegment(
                speaker=speaker,
                speaker_name=seg_data.get("speaker_name"),
                text=seg_data.get("text", ""),
                start_time=seg_data.get("start_time"),
                end_time=seg_data.get("end_time"),
            )
            segments.append(segment)
        
        return Transcript(
            metadata=metadata,
            segments=segments,
            raw_text=data.get("raw_text"),
        )
    
    def load_text_transcript(
        self, 
        file_path: Path,
        rep_name: str = "Unknown Rep",
        call_date: Optional[datetime] = None,
        company_name: Optional[str] = None,
    ) -> Transcript:
        """Load a transcript from a plain text file."""
        with open(file_path, "r") as f:
            raw_text = f.read()
        
        return self._create_transcript_from_text(
            raw_text=raw_text,
            rep_name=rep_name,
            call_date=call_date,
            company_name=company_name,
            source_file=file_path.name,
        )
    
    def load_pdf_transcript(
        self,
        file_path: Path,
        rep_name: str = "Unknown Rep",
        call_date: Optional[datetime] = None,
        company_name: Optional[str] = None,
    ) -> Transcript:
        """Load a transcript from a PDF file."""
        raw_text = extract_text_from_pdf(file_path)
        
        return self._create_transcript_from_text(
            raw_text=raw_text,
            rep_name=rep_name,
            call_date=call_date,
            company_name=company_name,
            source_file=file_path.name,
        )
    
    def load_from_text(
        self,
        text: str,
        rep_name: str = "Unknown Rep",
        call_date: Optional[datetime] = None,
        company_name: Optional[str] = None,
    ) -> Transcript:
        """Create a transcript from raw text (for paste/upload use case)."""
        return self._create_transcript_from_text(
            raw_text=text,
            rep_name=rep_name,
            call_date=call_date,
            company_name=company_name,
            source_file="pasted_text",
        )
    
    def load_from_pdf_bytes(
        self,
        pdf_bytes: bytes,
        rep_name: str = "Unknown Rep",
        call_date: Optional[datetime] = None,
        company_name: Optional[str] = None,
        filename: str = "uploaded.pdf",
    ) -> Transcript:
        """Create a transcript from PDF bytes (for upload use case)."""
        raw_text = extract_text_from_pdf(pdf_bytes)
        
        return self._create_transcript_from_text(
            raw_text=raw_text,
            rep_name=rep_name,
            call_date=call_date,
            company_name=company_name,
            source_file=filename,
        )
    
    def _create_transcript_from_text(
        self,
        raw_text: str,
        rep_name: str = "Unknown Rep",
        call_date: Optional[datetime] = None,
        company_name: Optional[str] = None,
        source_file: Optional[str] = None,
    ) -> Transcript:
        """Create a Transcript object from raw text."""
        # Generate call_id from filename or random
        call_id = source_file.replace(".", "_")[:20] if source_file else str(uuid.uuid4())[:8]

        def _is_placeholder_rep(name: Optional[str]) -> bool:
            if not name:
                return True
            n = name.strip().lower()
            if n in {"unknown rep", "unknown", "n/a", "na", "none", "meeting", "call"}:
                return True
            # People often type "Meeting" / "Sales Call" etc.
            if "meeting" in n and len(n.split()) <= 2:
                return True
            return False

        rep_name_input = rep_name
        rep_name_for_parsing = "Unknown Rep" if _is_placeholder_rep(rep_name_input) else rep_name_input

        # First, try to parse speaker labels from text
        segments = self._parse_text_segments(raw_text, rep_name_for_parsing)

        inferred_company_name = company_name
        if not inferred_company_name:
            inferred_company_name = self._infer_company_from_text(raw_text)

        # If rep_name wasn't provided, try to infer it from the conversation
        inferred_rep_name = rep_name_for_parsing
        if _is_placeholder_rep(rep_name_input):
            # Prefer a segment explicitly marked as REP
            rep_segments = [s for s in segments if s.speaker == Speaker.REP and s.speaker_name]
            if rep_segments:
                inferred_rep_name = rep_segments[0].speaker_name
            else:
                # Try to infer from participant list (PDF-like transcripts)
                inferred_from_participants = self._infer_rep_from_participants(raw_text)
                if inferred_from_participants:
                    inferred_rep_name = inferred_from_participants
                else:
                    # Fallback: first named speaker in the transcript
                    named_segments = [s for s in segments if s.speaker_name]
                    if named_segments:
                        inferred_rep_name = named_segments[0].speaker_name

        # If we inferred a rep name, mark matching segments as REP for downstream use.
        if inferred_rep_name and segments:
            for seg in segments:
                if seg.speaker_name and seg.speaker_name.strip().lower() == inferred_rep_name.strip().lower():
                    seg.speaker = Speaker.REP

        metadata = CallMetadata(
            call_id=call_id,
            call_date=call_date or datetime.now(),
            rep_name=inferred_rep_name or "Unknown Rep",
            company_name=inferred_company_name,
        )

        return Transcript(
            metadata=metadata,
            segments=segments,
            raw_text=raw_text if not segments else None,
        )

    def _infer_company_from_text(self, text: str) -> Optional[str]:
        """Best-effort company inference from common transcript headers."""
        # Example from sample PDFs: "Meeting: CloudShield Inc - Security Platform Demo"
        m = re.search(r"(?im)^\s*Meeting:\s*(.+?)\s*$", text)
        if not m:
            return None
        meeting_line = m.group(1).strip()
        # Take the part before " - " as company-ish.
        if " - " in meeting_line:
            return meeting_line.split(" - ", 1)[0].strip() or None
        return meeting_line or None

    def _infer_rep_from_participants(self, text: str) -> Optional[str]:
        """Best-effort rep inference from a Participants section (common in Meet/Teams exports)."""
        # We prefer internal participants with role hints.
        role_keywords = (
            "account executive",
            "sales",
            "ae",
            "customer success",
            "csm",
            "solutions engineer",
            "product manager",
        )
        in_participants = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"(?im)^participants\s*:\s*$", line):
                in_participants = True
                continue
            if in_participants and re.match(r"(?im)^transcript\s*$", line):
                break
            if not in_participants:
                continue

            # Example: "- Rachel Martinez (Account Executive) - rachel.martinez@ourcompany.com"
            m = re.match(r"^\s*[-•]\s*(?P<name>.+?)(?:\s*\((?P<role>.+?)\))?\s*-\s*(?P<email>\S+@\S+)\s*$", line)
            if not m:
                continue
            name = (m.group("name") or "").strip()
            role = (m.group("role") or "").strip().lower()
            email = (m.group("email") or "").strip().lower()

            if not name:
                continue
            if "@ourcompany.com" in email:
                if any(k in role for k in role_keywords) or not role:
                    return name
        return None
    
    def _parse_text_segments(self, text: str, rep_name: str) -> list[TranscriptSegment]:
        """Attempt to parse speaker-labeled text into segments."""
        segments: list[TranscriptSegment] = []
        lines = [ln.rstrip() for ln in text.strip().split("\n")]

        # First: try to parse Meet/Teams style timestamps + speaker blocks (common in PDFs)
        timestamp_re = re.compile(r"^\s*(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})(?:\s+(?P<speaker>.+?))?\s*$")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            m = timestamp_re.match(line)
            if not m:
                break  # Not a timestamped transcript

            hh = int(m.group("h"))
            mm = int(m.group("m"))
            ss = int(m.group("s"))
            seconds = hh * 3600 + mm * 60 + ss
            timestamp_str = f"{hh:02d}:{mm:02d}:{ss:02d}"

            speaker_name = (m.group("speaker") or "").strip() or None
            # Sometimes timestamp is on its own line; speaker follows.
            if speaker_name is None:
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    speaker_name = lines[j].strip()
                    i = j  # advance to speaker line

            # Collect message lines until next timestamp
            message_lines: list[str] = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                if timestamp_re.match(next_line):
                    break
                # Skip obvious section headers sometimes present in exports
                if re.match(r"(?im)^(meeting transcript|participants\s*:|transcript)$", next_line):
                    i += 1
                    continue
                message_lines.append(next_line)
                i += 1

            message = " ".join(message_lines).strip()
            if message and speaker_name:
                speaker = Speaker.UNKNOWN
                if rep_name and rep_name != "Unknown Rep" and speaker_name.lower() == rep_name.lower():
                    speaker = Speaker.REP
                segments.append(
                    TranscriptSegment(
                        speaker=speaker,
                        speaker_name=speaker_name,
                        text=message,
                        start_time=float(seconds),
                        timestamp_str=timestamp_str,
                    )
                )

        if segments:
            return segments

        # Fallback: line-based "Name: text" parsing (plain text transcripts)
        segments = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to detect speaker label patterns like "John:" or "[Rep]:" or "PROSPECT:"
            speaker = Speaker.UNKNOWN
            speaker_name = None
            content = line
            
            if ":" in line:
                potential_label, rest = line.split(":", 1)
                potential_label = potential_label.strip().lower()
                
                # Check for common speaker indicators
                if any(word in potential_label for word in ["rep", "sales", "ae", rep_name.lower()]):
                    speaker = Speaker.REP
                    speaker_name = potential_label.title()
                    content = rest.strip()
                elif any(word in potential_label for word in ["prospect", "customer", "client", "buyer"]):
                    speaker = Speaker.PROSPECT
                    speaker_name = potential_label.title()
                    content = rest.strip()
                elif len(potential_label.split()) <= 3:  # Likely a name
                    speaker_name = potential_label.title()
                    content = rest.strip()
            
            if content:
                segments.append(TranscriptSegment(
                    speaker=speaker,
                    speaker_name=speaker_name,
                    text=content,
                ))
        
        return segments
    
    def load_all(self) -> TranscriptCollection:
        """Load all transcripts from the data directory (JSON, TXT, PDF)."""
        transcripts = []
        
        if not self.data_dir.exists():
            return TranscriptCollection(transcripts=[])
        
        # Load JSON files
        for json_file in self.data_dir.glob("*.json"):
            try:
                transcript = self.load_json_transcript(json_file)
                transcripts.append(transcript)
            except Exception as e:
                print(f"Error loading {json_file}: {e}")
        
        # Load text files
        for txt_file in self.data_dir.glob("*.txt"):
            try:
                transcript = self.load_text_transcript(txt_file)
                transcripts.append(transcript)
            except Exception as e:
                print(f"Error loading {txt_file}: {e}")
        
        # Load PDF files
        for pdf_file in self.data_dir.glob("*.pdf"):
            try:
                transcript = self.load_pdf_transcript(pdf_file)
                transcripts.append(transcript)
            except Exception as e:
                print(f"Error loading {pdf_file}: {e}")
        
        # Sort by date
        transcripts.sort(key=lambda t: t.metadata.call_date, reverse=True)
        
        # Set date range
        date_start = None
        date_end = None
        if transcripts:
            dates = [t.metadata.call_date for t in transcripts]
            date_start = min(dates)
            date_end = max(dates)
        
        return TranscriptCollection(
            transcripts=transcripts,
            date_range_start=date_start,
            date_range_end=date_end,
        )
    
    def load_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> TranscriptCollection:
        """Load transcripts within a specific date range."""
        all_transcripts = self.load_all()
        
        filtered = [
            t for t in all_transcripts.transcripts
            if start_date <= t.metadata.call_date <= end_date
        ]
        
        return TranscriptCollection(
            transcripts=filtered,
            date_range_start=start_date,
            date_range_end=end_date,
        )
    
    def load_by_rep(self, rep_name: str) -> TranscriptCollection:
        """Load transcripts for a specific rep."""
        all_transcripts = self.load_all()
        
        filtered = [
            t for t in all_transcripts.transcripts
            if t.metadata.rep_name.lower() == rep_name.lower()
        ]
        
        return TranscriptCollection(transcripts=filtered)

