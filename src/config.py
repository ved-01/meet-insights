"""Configuration management for Meet Insights."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key"
    )
    openai_model: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI model to use"
    )
    
    # Google Docs (OAuth)
    google_doc_folder_id: Optional[str] = Field(
        default=None,
        description="Google Drive folder ID for docs"
    )
    
    # Chorus API
    chorus_api_key: Optional[str] = Field(
        default=None,
        description="Chorus API key"
    )
    chorus_api_url: str = Field(
        default="https://api.chorus.ai/v1",
        description="Chorus API base URL"
    )
    
    # Web Dashboard
    web_host: str = Field(
        default="127.0.0.1",
        description="Web dashboard host"
    )
    web_port: int = Field(
        default=8000,
        description="Web dashboard port"
    )
    
    # Processing
    max_insights_per_category: int = Field(
        default=10,
        description="Maximum insights per category"
    )
    min_insights_per_category: int = Field(
        default=3,
        description="Minimum insights per category"
    )
    enable_deduplication: bool = Field(
        default=True,
        description="Enable insight deduplication"
    )
    confidence_threshold: str = Field(
        default="medium",
        description="Minimum confidence threshold"
    )
    
    # Data
    data_dir: str = Field(
        default="data/sample_transcripts",
        description="Directory containing transcript files"
    )
    
    # LangSmith Tracing
    langchain_tracing_v2: bool = Field(
        default=False,
        description="Enable LangSmith tracing (set LANGCHAIN_TRACING_V2=true)"
    )
    langchain_api_key: Optional[str] = Field(
        default=None,
        description="LangSmith API key"
    )
    langchain_project: str = Field(
        default="meet-insights",
        description="LangSmith project name"
    )
    langchain_verbose: bool = Field(
        default=False,
        description="Enable verbose LangSmith tracing"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()

