"""Tests for data loaders."""

import pytest
import json
from pathlib import Path
from datetime import datetime

from src.loaders.file_loader import FileLoader


class TestFileLoader:
    """Test file-based transcript loader."""
    
    def test_load_json_transcript(self, tmp_path):
        """Test loading a JSON transcript file."""
        # Create test file
        transcript_data = {
            "metadata": {
                "call_id": "TEST-001",
                "call_date": "2024-12-18T10:30:00",
                "rep_name": "Test Rep",
                "company_name": "Test Company",
            },
            "segments": [
                {
                    "speaker": "rep",
                    "text": "Hello there",
                    "start_time": 0,
                }
            ]
        }
        
        test_file = tmp_path / "test_call.json"
        test_file.write_text(json.dumps(transcript_data))
        
        loader = FileLoader(data_dir=str(tmp_path))
        transcript = loader.load_json_transcript(test_file)
        
        assert transcript.metadata.call_id == "TEST-001"
        assert transcript.metadata.rep_name == "Test Rep"
        assert len(transcript.segments) == 1
    
    def test_load_all_transcripts(self, tmp_path):
        """Test loading all transcripts from directory."""
        # Create test files
        for i in range(3):
            data = {
                "metadata": {
                    "call_id": f"TEST-{i:03d}",
                    "call_date": "2024-12-18T10:30:00",
                    "rep_name": f"Rep {i}",
                },
                "segments": []
            }
            (tmp_path / f"call_{i}.json").write_text(json.dumps(data))
        
        loader = FileLoader(data_dir=str(tmp_path))
        collection = loader.load_all()
        
        assert collection.total_calls == 3
    
    def test_load_empty_directory(self, tmp_path):
        """Test loading from empty directory."""
        loader = FileLoader(data_dir=str(tmp_path))
        collection = loader.load_all()
        
        assert collection.total_calls == 0
        assert collection.transcripts == []

