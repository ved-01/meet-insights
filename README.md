# 📊 Meet Insights

Transform Chorus call transcripts into categorized, actionable insights for Marketing, Product, and Sales teams.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![LangChain](https://img.shields.io/badge/LangChain-0.3.x-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-red.svg)

## 🎯 What It Does

This pipeline analyzes sales call transcripts and extracts insights into **6 categories**:

| Category | Description |
|----------|-------------|
| 🚀 **Product Recommendations** | Feature requests, integrations, "you should build X" |
| ⭐ **Positive Feedback & Testimonials** | Quotes, outcomes, value statements |
| 📣 **Marketing & Brand Messaging** | Website feedback, positioning, clarity issues |
| 📱 **Social Messaging** | Punchy quotes, hooks for LinkedIn/Twitter |
| ❓ **FAQ Ideas** | Common questions, objections, confusion points |
| 📝 **Blog Topics** | Pain points, "how do I...", content ideas |

### Bonus Features
- 🔥 **Top 5 Themes** rollup across all calls
- 🔄 **Deduplication** to avoid repeating similar insights
- 💬 **Direct Quotes** extracted for testimonials and social

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Clone and enter the project
cd meet-insights

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here

# Optional: Enable LangSmith tracing for observability
# Get your API key from https://smith.langchain.com/
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=your-langsmith-api-key
# LANGCHAIN_PROJECT=meet-insights
```

### 3. Run the Pipeline

```bash
# Process sample transcripts and launch web dashboard
python run.py

# Or output to markdown file
python run.py --output markdown

# Or output to Google Docs (requires setup - see below)
python run.py --output docs
```

**That's it!** Open http://localhost:8000 to see your insights dashboard.

## 📁 Project Structure

```
meet-insights/
├── src/
│   ├── models/           # Pydantic data models
│   │   ├── transcript.py # Transcript & call metadata
│   │   └── insights.py   # Insight categories & structures
│   ├── loaders/          # Data loading
│   │   ├── file_loader.py    # Load from JSON/TXT/PDF files
│   │   └── chorus_api.py     # Chorus API integration
│   ├── extractors/       # AI-powered extraction
│   │   └── insight_extractor.py  # LangChain + GPT
│   ├── outputs/          # Output handlers
│   │   ├── google_docs.py    # Google Docs integration
│   │   └── web_dashboard.py  # FastAPI dashboard
│   └── utils/            # Utilities
│       └── deduplication.py  # Insight deduplication
├── data/
│   └── sample_transcripts/   # Sample call transcripts
├── web/
│   └── templates/        # Dashboard HTML templates
├── output/               # Generated markdown files
├── run.py               # Main CLI entry point
├── requirements.txt
└── .env.example
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | ✅ Yes |
| `OPENAI_MODEL` | Model to use (default: `gpt-4.1-mini`) | No |
| `GOOGLE_DOC_FOLDER_ID` | Google Drive folder ID for docs (optional) | For Docs |
| `GOOGLE_OAUTH_CLIENT_SECRETS` | Path to OAuth client JSON (optional, defaults to `credentials/oauth_client_secrets.json`) | For Docs |
| `WEB_HOST` | Dashboard host (default: `127.0.0.1`) | No |
| `WEB_PORT` | Dashboard port (default: `8000`) | No |

### Supported Models

- `gpt-4.1-mini` (default, recommended)
- `gpt-4o-mini`
- `gpt-4o`
- `gpt-4-turbo`

## 📥 Input Options

The pipeline supports multiple ways to provide transcripts:

### Option A: Batch Directory (Default)

Process all transcript files in a directory:

```bash
python run.py                          # Uses default data/sample_transcripts/
python run.py -d /path/to/transcripts  # Custom directory
```

Supported file types: `.json`, `.txt`, `.pdf`

### Option B: Single File (CLI)

Process a single transcript file:

```bash
python run.py --file transcript.pdf
python run.py -f call.txt --rep "Sarah Johnson" --company "Acme Corp"
```

### Option C: Web Upload/Paste

Open the web dashboard and use the upload interface:

1. Start the dashboard: `python run.py`
2. Open http://localhost:8000
3. Either:
   - **Paste** transcript text directly into the textarea
   - **Upload** a PDF or TXT file
4. Click "Analyze" to extract insights

---

## 📝 Input Formats

### JSON Transcript Format (Structured)

```json
{
  "metadata": {
    "call_id": "CALL-001",
    "call_date": "2024-12-18T10:30:00",
    "rep_name": "Sarah Johnson",
    "company_name": "Acme Corp",
    "call_type": "Discovery Call"
  },
  "segments": [
    {
      "speaker": "rep",
      "speaker_name": "Sarah Johnson",
      "text": "Hi, thanks for joining today...",
      "start_time": 0,
      "end_time": 8
    },
    {
      "speaker": "prospect",
      "speaker_name": "Michael Chen",
      "text": "Happy to be here...",
      "start_time": 9,
      "end_time": 15
    }
  ]
}
```

### Plain Text Format (.txt)

```text
Sarah: Hi, thanks for joining today...
Michael: Happy to be here...
```

### PDF Format

PDF transcripts are automatically converted to text. The text is extracted page-by-page and parsed for speaker labels.

**Supported sources:**
- Chorus exports
- Gong transcripts
- Zoom meeting transcripts
- Any PDF with readable text

## 🖥️ Output Options

### Option A: Web Dashboard (Default)

```bash
python run.py --output web
```

Beautiful, responsive dashboard showing all insights with:
- Real-time filtering by rep and date
- Confidence indicators (🟢 high, 🟡 medium, 🔴 low)
- Direct quote highlighting
- Auto-refresh when data updates

### Option B: Google Docs (OAuth)

```bash
python run.py --output docs
```

**Setup Required (OAuth 2.0):**

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable APIs:**
   - Navigate to "APIs & Services" > "Library"
   - Enable "Google Docs API"
   - Enable "Google Drive API"

3. **Create OAuth Client ID (Desktop App):**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: **Desktop app**
   - Download the client JSON

4. **Save the client JSON:**
   - Save it as `credentials/oauth_client_secrets.json`
   - Or set `GOOGLE_OAUTH_CLIENT_SECRETS` in `.env` to that path

5. **(Optional) Set a Drive folder:**
   - Get the folder ID from a Google Drive folder URL
   - Set `GOOGLE_DOC_FOLDER_ID` in `.env` if you want docs in that folder

For more detail, follow the same steps in the Google Cloud Console: enable Docs/Drive APIs, create an OAuth Client ID (Desktop), download the client JSON, and point `GOOGLE_OAUTH_CLIENT_SECRETS` to it if you don't use the default path.*** End Patch```} >> README.md)"} ***!

### Option C: Local Markdown

```bash
python run.py --output markdown
```

Saves insights to `output/insights.md` - useful for version control or sharing.

### Option D: Both Docs and Web

```bash
python run.py --output both
```

## 🔌 Using Your Own Transcripts

### From Files

1. Add your JSON or TXT files to `data/sample_transcripts/`
2. Run: `python run.py`

### From Chorus API (Coming Soon)

```python
from src.loaders.chorus_api import ChorusAPILoader

loader = ChorusAPILoader(api_key="your-key")
transcripts = await loader.load_recent(days=7)
```

## 🧪 CLI Commands

```bash
# Main pipeline with options
python run.py [OPTIONS]

Options:
  -o, --output [web|docs|markdown|both]  Output destination
  -d, --data PATH                        Transcript directory
  -f, --file PATH                        Process single file (PDF/TXT/JSON)
  --rep TEXT                             Rep name (for single file)
  --company TEXT                         Company name (for single file)
  --no-dedupe                            Disable deduplication
  --serve / --no-serve                   Start web server

# Process a single PDF transcript
python run.py --file transcript.pdf --rep "Sarah Johnson"

# List available transcripts
python run.py list-transcripts

# Start web dashboard without processing
python run.py serve-only
```

## 📊 Sample Output

```
╔══════════════════════════════════════════════════════════════╗
║   📊  MEET INSIGHTS                                          ║
╚══════════════════════════════════════════════════════════════╝

✓ Found 3 transcripts
  Reps: Sarah Johnson, James Wilson
  Companies: Acme Corp, TechStart Inc, GlobalFin Solutions

✓ Processed in 12.3 seconds

📈 Extraction Complete
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Category                   ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ 🚀 Product Recommendations │     8 │
│ ⭐ Positive Feedback       │     6 │
│ 📣 Marketing Messaging     │     4 │
│ 📱 Social Messaging        │     5 │
│ ❓ FAQ Ideas               │     7 │
│ 📝 Blog Topics             │     6 │
├───────────────────────────┼───────┤
│ Total Insights            │    36 │
└───────────────────────────┴───────┘

🔥 Top Themes:
   1. CRM Integration & Automation (5x)
   2. Time Savings & Productivity (4x)
   3. Forecasting Accuracy (3x)
   4. Implementation Concerns (3x)
   5. Pricing Clarity (2x)
```

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Loader   │────▶│   Extractor     │────▶│    Outputs      │
│  (File/API)     │     │  (LangChain)    │     │ (Docs/Web/MD)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ TranscriptModel │     │ CallInsights    │     │ GoogleDocsOutput│
│ CallMetadata    │     │ WeeklyRollup    │     │ WebDashboard    │
│ Segments        │     │ ThemeSummary    │     │ MarkdownOutput  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 📊 LangSmith Tracing (Optional)

Enable observability and debugging with LangSmith:

1. **Get your API key:**
   - Sign up at https://smith.langchain.com/
   - Go to Settings → API Keys
   - Copy your API key

2. **Enable in .env:**
   ```bash
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your-api-key-here
   LANGCHAIN_PROJECT=meet-insights
   ```

3. **View traces:**
   - All LLM calls will be automatically traced
   - Visit https://smith.langchain.com/ to see:
     - Token usage and costs
     - Latency metrics
     - Input/output pairs
     - Error tracking
     - Chain execution flow

Traces include metadata like call IDs, rep names, and company names for easy filtering.

## 🔮 Next Steps & Improvements

- [ ] Real-time Chorus API integration
- [ ] Slack/Teams notifications for new insights
- [ ] Scheduled processing (daily/weekly)
- [ ] Custom insight categories
- [ ] Export to Notion, Airtable
- [ ] Multi-language transcript support
- [ ] Sentiment analysis overlay
- [ ] CRM integration (Salesforce, HubSpot)
