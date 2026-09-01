# Academix AI — RAG-Powered Quiz Generation Platform

A single-institute academic platform with three roles (Admin, Teacher, Student) centered on a **Retrieval-Augmented Generation (RAG) Quiz Generation Engine**.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript + TailwindCSS |
| Backend | FastAPI (Python) |
| Database | Supabase PostgreSQL + pgvector |
| Auth | Supabase Auth (JWT) |
| Storage | Supabase Storage |
| LLM | Groq API |
| Embeddings | sentence-transformers (local) |

## Prerequisites

- **Python 3.11+** — [Download](https://python.org)
- **Node.js 20+** — [Download](https://nodejs.org)
- **Supabase Account** — [Sign up free](https://supabase.com)
- **Groq API Key** — [Get one free](https://console.groq.com)

## Setup Instructions

### 1. Supabase Project Setup

1. Go to [supabase.com](https://supabase.com) and create a new project
2. In your project dashboard, go to **SQL Editor**
3. Copy the contents of `supabase/migrations/001_initial_schema.sql` and run it
4. Go to **Storage** and create these buckets:
   - `course-materials` (private)
   - `pyq-papers` (private)
   - `submissions` (private)
   - `avatars` (public)
5. Note down your project credentials from **Settings → API**:
   - Project URL
   - Anon/Public Key
   - Service Role Key
   - JWT Secret

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in your keys
cp .env.example .env
# Edit .env with your Supabase and Groq credentials

# Run the server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy env template and fill in your keys
cp .env.example .env
# Edit .env with your Supabase credentials

# Run the dev server
npm run dev
```

The app will be available at `http://localhost:5173`

## Project Structure

```
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py            # App entry point
│   │   ├── config.py          # Settings & env vars
│   │   ├── database.py        # Supabase client
│   │   ├── dependencies.py    # Auth middleware
│   │   ├── models/            # Pydantic schemas
│   │   ├── routers/           # API endpoints
│   │   ├── services/          # Business logic
│   │   └── utils/             # Helpers
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # React Vite app
│   ├── src/
│   │   ├── components/        # Reusable components
│   │   ├── pages/             # Page components
│   │   ├── hooks/             # Custom hooks
│   │   ├── contexts/          # React contexts
│   │   └── lib/               # Utilities
│   └── .env.example
├── supabase/
│   └── migrations/            # Database schema
└── README.md
```

## Demo Accounts

You can log in to the platform using the following demo accounts (Password for all accounts is `password123`):

- **Admin**: `admin@academix.ai`
- **Teacher**: `teacher@academix.ai`
- **Student**: `student@academix.ai`

## Features (Phase 1)

- ✅ Auth/RBAC for 3 roles (Admin, Teacher, Student)
- ✅ Classroom (Google Classroom parity: Stream, Materials, Assignments, Submissions, Grading)
- ✅ Quiz Generation (Student) — RAG-powered practice quizzes
- ✅ Paper Style (Teacher) — RAG-powered exam draft generation with review/approve
- ✅ Scheduler (Google Calendar-style native calendar)
- ✅ Notice Board (in-app notification feed)
- ✅ Admin panel (User management, Course management)
