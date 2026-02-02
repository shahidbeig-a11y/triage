# Email Triage Backend

FastAPI backend for intelligent email triage and classification using Claude AI and Microsoft Graph API.

## Features

- **Email Management**: Fetch, classify, and manage emails via Microsoft Graph API
- **AI Classification**: Use Claude AI to automatically categorize emails into 11 system categories
- **Urgency Scoring**: Multi-factor urgency analysis to prioritize emails
- **User Settings**: Customizable thresholds and preferences
- **RESTful API**: Clean API design with automatic OpenAPI documentation

## Project Structure

```
backend/
├─ app/
│  ├─ main.py          # FastAPI application entry point
│  ├─ database.py      # SQLite database configuration
│  ├─ models/          # SQLAlchemy models
│  │  ├─ email.py      # Email model
│  │  ├─ category.py   # Category model
│  │  └─ settings.py   # User settings model
│  ├─ routes/          # API endpoints
│  │  ├─ auth.py       # Authentication endpoints
│  │  ├─ emails.py     # Email management endpoints
│  │  └─ settings.py   # Settings endpoints
│  └─ services/        # Business logic
│     ├─ graph.py      # Microsoft Graph API client
│     ├─ claude.py     # Claude AI client
│     └─ scoring.py    # Urgency scoring engine
├─ requirements.txt    # Python dependencies
├─ .env.example        # Environment variables template
└─ README.md          # This file
```

## Setup

### Prerequisites

- Python 3.12+
- pip

### Installation

1. **Create virtual environment:**

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
MICROSOFT_CLIENT_ID=your_microsoft_client_id_here
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret_here
DATABASE_URL=sqlite:///./triage.db
```

### Running the Application

Start the development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

## API Endpoints

### Health Check

```
GET /api/health
```

Returns server status and category count.

### Authentication

```
GET /api/auth/login       # Initiate Microsoft OAuth login
GET /api/auth/callback    # OAuth callback handler
```

### Emails

```
GET  /api/emails/                    # List emails
POST /api/emails/{id}/classify       # Classify email with AI
POST /api/emails/{id}/score          # Calculate urgency score
```

### Settings

```
GET /api/settings/       # Get user settings
PUT /api/settings/       # Update user settings
```

## System Categories

The database is pre-populated with 11 system categories:

| # | Label | Tab | Description |
|---|-------|-----|-------------|
| 1 | Blocking | P1 | Critical blockers requiring immediate action |
| 2 | Action Required | P1 | Important tasks that need completion |
| 3 | Waiting On | P2 | Pending response from others |
| 4 | Time-Sensitive | P2 | Has a deadline or time constraint |
| 5 | FYI | Action | Informational, no action needed |
| 6 | Discuss | Action | Needs discussion or clarification |
| 7 | Decide | Action | Requires a decision to be made |
| 8 | Delegate | Action | Should be assigned to someone else |
| 9 | Read/Review | Action | Documents or content to review |
| 10 | Low Priority | P3 | Can be addressed later |
| 11 | Archive | P3 | Completed or no longer relevant |

## Database Schema

### Email

- `id`: Primary key
- `message_id`: Unique message identifier from Graph API
- `from_address`, `from_name`: Sender information
- `subject`, `body_preview`: Email content
- `received_at`: Timestamp
- `importance`: Email importance flag
- `conversation_id`: Thread identifier
- `has_attachments`: Boolean flag
- `category_id`: Foreign key to Category
- `confidence`: AI classification confidence (0.0-1.0)
- `urgency_score`: Calculated urgency (0.0-1.0)
- `due_date`: Extracted deadline
- `folder`: inbox, archive, deleted
- `status`: unread, read, flagged, archived

### Category

- `id`: Primary key
- `number`: Category number (1-11)
- `label`: Display name
- `tab`: Tab grouping (P1, P2, P3, Action)
- `description`: Category description
- `is_system`: Boolean flag
- `icon`: Emoji or icon name
- `color`: Hex color code

### UserSettings

- `id`: Primary key
- `task_limit`: Max tasks to show (default: 5)
- `urgency_floor`: Min urgency threshold (default: 0.3)
- `ai_threshold`: Auto-classification confidence (default: 0.7)
- `tone_exclusions`: JSON string of excluded keywords

## Development

### Database Migrations

The database is automatically initialized on first run. To reset:

```bash
rm triage.db
# Restart the server to recreate
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests (when implemented)
pytest
```

### Code Style

```bash
# Install formatting tools
pip install black isort

# Format code
black app/
isort app/
```

## TODO

The following service integrations are placeholders and need implementation:

- [ ] **Microsoft Graph API**: Implement OAuth flow and email fetching
- [ ] **Claude AI Integration**: Implement email classification and analysis
- [ ] **Urgency Scoring**: Complete multi-factor scoring algorithm
- [ ] **Action Item Extraction**: Parse deadlines and tasks from emails
- [ ] **Batch Processing**: Optimize bulk email classification
- [ ] **Caching**: Add Redis for API response caching
- [ ] **Testing**: Add unit and integration tests
- [ ] **Logging**: Implement structured logging
- [ ] **Error Handling**: Add global exception handlers
- [ ] **Rate Limiting**: Protect API endpoints

## License

MIT
