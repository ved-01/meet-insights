"""Google Docs output handler for insights delivery (OAuth-only)."""

import os
from datetime import datetime
from typing import Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..models.insights import CallInsights, WeeklyRollup, Insight
from ..config import get_settings


class GoogleDocsOutput:
    """Create and update Google Docs with extracted insights using OAuth 2.0."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive',  # Full Drive access (more permissive)
    ]
    
    def __init__(
        self,
        folder_id: Optional[str] = None,
        oauth_client_secrets_path: Optional[str] = None,
        oauth_token_path: Optional[str] = "credentials/oauth_token.json",
    ):
        """Initialize Google Docs output handler (OAuth-only).

        Args:
            folder_id: Google Drive folder ID to store docs in
            oauth_client_secrets_path: Path to OAuth client secrets JSON
            oauth_token_path: Path to store OAuth tokens
        """
        settings = get_settings()

        self.oauth_client_secrets_path = (
            oauth_client_secrets_path 
            or os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS")
            or "credentials/oauth_client_secrets.json"
        )
        self.oauth_token_path = oauth_token_path
        
        # Use provided folder_id, or from settings, or env var
        self.folder_id = (
            folder_id 
            or settings.google_doc_folder_id
            or os.getenv("GOOGLE_DOC_FOLDER_ID")
        )
        
        self.docs_service = None
        self.drive_service = None
        self._user_email = None
        
        # Authenticate immediately using OAuth
        self._authenticate()
    
    def get_user_email(self) -> Optional[str]:
        """Get the authenticated user's email (for OAuth)."""
        return self._user_email
    
    def _authenticate(self):
        """Authenticate with Google APIs using OAuth 2.0."""
        credentials = self._authenticate_oauth()

        if credentials:
            self.docs_service = build('docs', 'v1', credentials=credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            # Try to get user email
            if self.drive_service:
                try:
                    about = self.drive_service.about().get(fields="user").execute()
                    self._user_email = about.get("user", {}).get("emailAddress")
                except Exception:
                    pass
    
    def _authenticate_oauth(self) -> Optional[Credentials]:
        """Authenticate using OAuth 2.0 (user consent flow).
        
        This requires an OAuth client secrets file from Google Cloud Console.
        Creates a browser window for user consent on first run.
        """
        credentials = None
        
        # Try to load existing token
        if self.oauth_token_path and Path(self.oauth_token_path).exists():
            try:
                credentials = Credentials.from_authorized_user_file(
                    self.oauth_token_path, self.SCOPES
                )
            except Exception as e:
                print(f"⚠️  Could not load existing OAuth token: {e}")
        
        # Refresh or get new credentials
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                print("✅ Refreshed OAuth token")
            except Exception as e:
                print(f"⚠️  Could not refresh token: {e}")
                credentials = None
        
        if not credentials or not credentials.valid:
            # Need to get new credentials via browser flow
            if not self.oauth_client_secrets_path or not Path(self.oauth_client_secrets_path).exists():
                print(
                    f"""
❌ OAuth client secrets not found at: {self.oauth_client_secrets_path}

To set up OAuth authentication:
1. Go to https://console.cloud.google.com/apis/credentials
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Desktop app" as the application type
4. Download the JSON file and save it as: {self.oauth_client_secrets_path}
5. Run this script again
"""
                )
                return None
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.oauth_client_secrets_path, self.SCOPES
                )
                credentials = flow.run_local_server(port=0)
                print("✅ OAuth authentication successful!")
                
                # Save the token for future use
                if self.oauth_token_path:
                    Path(self.oauth_token_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(self.oauth_token_path, 'w') as token_file:
                        token_file.write(credentials.to_json())
                    print(f"✅ Saved OAuth token to: {self.oauth_token_path}")
                    
            except Exception as e:
                print(f"❌ OAuth authentication failed: {e}")
                return None
        
        return credentials
    
    def create_document(self, title: str) -> str:
        """Create a new Google Doc and return its ID.
        
        If a folder_id is specified, the document is created directly in that folder.
        """
        if not self.docs_service:
            raise ValueError("Google Docs not authenticated. Check credentials.")
        
        # Create the document
        doc = self.docs_service.documents().create(body={'title': title}).execute()
        doc_id = doc.get('documentId')
        
        # Move to specified folder if provided
        if self.folder_id and self.drive_service:
            try:
                # Get current parents to remove them
                file = self.drive_service.files().get(
                    fileId=doc_id, 
                    fields='parents'
                ).execute()
                previous_parents = ",".join(file.get('parents', []))
                
                # Move the file to the new folder
                self.drive_service.files().update(
                    fileId=doc_id,
                    addParents=self.folder_id,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()
                print(f"✅ Document moved to folder: {self.folder_id}")
            except HttpError as e:
                print(f"⚠️  Could not move doc to folder: {e}")
                print(f"   The document was created in your Drive root instead.")
        else:
            print("ℹ️  No folder ID specified. Document created in Drive root.")
            print("   Set GOOGLE_DOC_FOLDER_ID in .env to specify a destination folder.")
        
        return doc_id
    
    def _format_insight_bullet(self, insight: Insight) -> str:
        """Format a single insight as a readable bullet point with clean spacing."""
        confidence_labels = {
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }

        conf_value = insight.confidence.value if hasattr(insight.confidence, "value") else insight.confidence
        conf_label = confidence_labels.get(str(conf_value).lower(), "Medium")

        lines = []
        # Main line
        lines.append(f"• {insight.content}")

        # Optional direct quote
        if insight.direct_quote:
            lines.append(f'    "{insight.direct_quote}"')

        # Source and confidence
        lines.append(f"    Source: {insight.source.format_reference()}")
        lines.append(f"    Confidence: {conf_label}")

        return "\n".join(lines)
    
    def _build_document_requests(self, insights: CallInsights, weekly_rollup: Optional[WeeklyRollup] = None) -> list:
        """Build batch update requests for the document with clean, readable formatting."""
        requests = []
        current_index = 1  # Start after initial empty position
        
        # Document title
        date_str = insights.processed_at.strftime('%B %d, %Y')  # e.g., "December 19, 2024"
        title = f"Meeting Insights Report\n{date_str}\n\n"
        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': title
            }
        })
        current_index += len(title)
        
        # Horizontal divider
        divider = "─" * 50 + "\n\n"
        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': divider
            }
        })
        current_index += len(divider)
        
        # Summary section with clean formatting
        summary = f"""SUMMARY

    Calls Analyzed:     {len(insights.call_ids)}
    Total Insights:     {insights.total_insights}
    Generated:          {insights.processed_at.strftime('%Y-%m-%d at %H:%M')}


"""
        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': summary
            }
        })
        current_index += len(summary)
        
        # Weekly rollup if provided
        if weekly_rollup and weekly_rollup.top_themes:
            rollup_text = "─" * 50 + "\n\n"
            rollup_text += "TOP THEMES THIS WEEK\n\n"
            
            for i, theme in enumerate(weekly_rollup.top_themes[:5], 1):
                rollup_text += f"    {i}. {theme.theme}\n"
                rollup_text += f"       Appeared {theme.occurrence_count} times\n\n"
                
                if theme.example_insights:
                    rollup_text += "       Examples:\n"
                    for example in theme.example_insights[:2]:
                        rollup_text += f"       • {example}\n"
                    rollup_text += "\n"
            
            rollup_text += "\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': rollup_text
                }
            })
            current_index += len(rollup_text)
        
        # Category sections with improved formatting
        categories = [
            ("PRODUCT RECOMMENDATIONS", "🚀", insights.product_recommendations),
            ("POSITIVE FEEDBACK & TESTIMONIALS", "⭐", insights.positive_feedback),
            ("MARKETING & BRAND MESSAGING", "📣", insights.marketing_messaging),
            ("SOCIAL MESSAGING IDEAS", "📱", insights.social_messaging),
            ("FAQ IDEAS", "❓", insights.faq_ideas),
            ("BLOG TOPICS & CONTENT IDEAS", "📝", insights.blog_topics),
        ]

        for category_title, emoji, category in categories:
            # Section header with divider
            section_text = "─" * 50 + "\n\n"
            section_text += f"{emoji}  {category_title}\n\n"

            # Category description
            if getattr(category, "description", None):
                section_text += f"{category.description}\n\n"

            if category.insights:
                for insight in category.insights:
                    section_text += self._format_insight_bullet(insight) + "\n\n\n"
            else:
                section_text += "No insights extracted for this category.\n\n"

            section_text += "\n"

            requests.append(
                {
                    "insertText": {
                        "location": {"index": current_index},
                        "text": section_text,
                    }
                }
            )
            current_index += len(section_text)
        
        # Footer
        footer = "\n" + "─" * 50 + "\n\n"
        footer += "Generated by Meeting Insights\n"
        footer += f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': footer
            }
        })
        
        return requests
    
    def write_insights(
        self, 
        insights: CallInsights,
        doc_id: Optional[str] = None,
        title: Optional[str] = None,
        weekly_rollup: Optional[WeeklyRollup] = None,
    ) -> str:
        """Write insights to a Google Doc.
        
        Args:
            insights: The extracted insights to write
            doc_id: Existing doc ID to update, or None to create new
            title: Title for new document (defaults to "Meeting Insights - {date}")
            weekly_rollup: Optional weekly rollup to include
            
        Returns:
            Document ID
        """
        if not self.docs_service:
            raise ValueError("Google Docs not authenticated. Check credentials.")
        
        # Create new doc if no ID provided
        if not doc_id:
            date_str = datetime.now().strftime('%B %d, %Y')  # e.g., "December 19, 2024"
            doc_title = title or f"Meeting Insights - {date_str}"
            doc_id = self.create_document(doc_title)
        
        # Build and execute requests
        requests = self._build_document_requests(insights, weekly_rollup)
        
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        return doc_id
    
    def get_document_url(self, doc_id: str) -> str:
        """Get the URL for a Google Doc."""
        return f"https://docs.google.com/document/d/{doc_id}/edit"
    
    def append_insights(self, doc_id: str, insights: CallInsights):
        """Append new insights to an existing document."""
        if not self.docs_service:
            raise ValueError("Google Docs not authenticated. Check credentials.")
        
        # Get current document length
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1) - 1
        
        # Build append text
        append_text = f"\n\n{'='*50}\n📥 Additional Insights - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{'='*50}\n\n"
        
        categories = [
            ("🚀 Product Recommendations", insights.product_recommendations),
            ("⭐ Positive Feedback", insights.positive_feedback),
            ("📣 Marketing Messaging", insights.marketing_messaging),
            ("📱 Social Messaging", insights.social_messaging),
            ("❓ FAQ Ideas", insights.faq_ideas),
            ("📝 Blog Topics", insights.blog_topics),
        ]
        
        for category_title, category in categories:
            if category.insights:
                append_text += f"\n{category_title}\n"
                for insight in category.insights:
                    append_text += self._format_insight_bullet(insight) + "\n"
        
        # Append to document
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                'requests': [{
                    'insertText': {
                        'location': {'index': end_index},
                        'text': append_text
                    }
                }]
            }
        ).execute()


class MockGoogleDocsOutput:
    """Mock Google Docs output for testing without credentials."""
    
    def __init__(self):
        self.documents = {}
        self._counter = 0
    
    def create_document(self, title: str) -> str:
        """Create a mock document."""
        self._counter += 1
        doc_id = f"mock-doc-{self._counter}"
        self.documents[doc_id] = {
            "title": title,
            "content": "",
            "created_at": datetime.now(),
        }
        return doc_id
    
    def write_insights(
        self,
        insights: CallInsights,
        doc_id: Optional[str] = None,
        title: Optional[str] = None,
        weekly_rollup: Optional[WeeklyRollup] = None,
    ) -> str:
        """Write insights to mock document."""
        if not doc_id:
            date_str = datetime.now().strftime('%B %d, %Y')
            doc_title = title or f"Meeting Insights - {date_str}"
            doc_id = self.create_document(doc_title)
        
        # Build content string with clean formatting
        content = f"# {self.documents[doc_id]['title']}\n\n"
        content += "---\n\n"
        content += "## Summary\n\n"
        content += f"- **Calls Analyzed:** {len(insights.call_ids)}\n"
        content += f"- **Total Insights:** {insights.total_insights}\n"
        content += f"- **Generated:** {datetime.now().strftime('%Y-%m-%d at %H:%M')}\n\n"
        
        if weekly_rollup and weekly_rollup.top_themes:
            content += "---\n\n"
            content += "## 🔥 Top Themes This Week\n\n"
            for i, theme in enumerate(weekly_rollup.top_themes[:5], 1):
                content += f"{i}. **{theme.theme}** (appeared {theme.occurrence_count} times)\n"
                if theme.example_insights:
                    for example in theme.example_insights[:2]:
                        content += f"   - {example}\n"
                content += "\n"
        
        categories = [
            ("🚀 Product Recommendations", insights.product_recommendations),
            ("⭐ Positive Feedback & Testimonials", insights.positive_feedback),
            ("📣 Marketing & Brand Messaging", insights.marketing_messaging),
            ("📱 Social Messaging Ideas", insights.social_messaging),
            ("❓ FAQ Ideas", insights.faq_ideas),
            ("📝 Blog Topics & Content Ideas", insights.blog_topics),
        ]
        
        for cat_title, category in categories:
            content += "---\n\n"
            content += f"## {cat_title}\n\n"
            
            if category.description:
                content += f"*{category.description}*\n\n"
            
            if category.insights:
                for idx, insight in enumerate(category.insights, 1):
                    content += f"### {idx}. {insight.content}\n\n"
                    
                    if insight.direct_quote:
                        content += f'> 💬 "{insight.direct_quote}"\n\n'
                    
                    content += f"📍 **Source:** {insight.source.format_reference()}\n\n"
                    
                    conf_value = insight.confidence.value if hasattr(insight.confidence, 'value') else insight.confidence
                    content += f"**Confidence:** {conf_value.capitalize()}\n\n"
            else:
                content += "*No insights extracted for this category.*\n\n"
        
        content += "---\n\n"
        content += f"*Generated by Meeting Insights • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        self.documents[doc_id]["content"] = content
        return doc_id
    
    def get_document_url(self, doc_id: str) -> str:
        """Return mock URL."""
        return f"file://mock-docs/{doc_id}"
    
    def get_content(self, doc_id: str) -> str:
        """Get the content of a mock document."""
        return self.documents.get(doc_id, {}).get("content", "")
    
    def save_to_file(self, doc_id: str, output_path: str):
        """Save mock document to a markdown file."""
        content = self.get_content(doc_id)
        with open(output_path, "w") as f:
            f.write(content)
        return output_path

