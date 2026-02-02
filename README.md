# TRIAGE v4.2

Email classification and workflow engine powered by AI.

## What It Does

TRIAGE is an intelligent email management system that automatically classifies and organizes emails using AI. It integrates with Microsoft 365 to fetch emails, analyzes them using Claude AI, and provides a modern web interface for managing your inbox workflow.

## Tech Stack

- **Frontend**: Next.js (React-based framework)
- **Backend**: FastAPI (Python web framework)
- **Database**: SQLite
- **AI**: Claude API (Anthropic)
- **Email**: Microsoft Graph API

## How to Run

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Project Status

**Week 1**: Scaffolding complete
- Project structure established
- Microsoft Graph API authentication implemented
- Email fetch functionality integrated
- Development environment configured
