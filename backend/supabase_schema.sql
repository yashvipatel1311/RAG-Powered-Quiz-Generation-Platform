-- ==============================================================================
-- Academix AI — Supabase Database Schema
-- Run this in the Supabase SQL Editor
-- ==============================================================================

-- 1. Enable pgvector extension for RAG embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Core Tables

-- PROFILES (Users)
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    department TEXT,
    phone TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- COURSES
CREATE TABLE public.courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    department_name TEXT,
    semester INTEGER,
    banner_color TEXT DEFAULT '#4285F4',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- ENROLLMENTS
CREATE TABLE public.enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('teacher', 'student')),
    enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    UNIQUE(user_id, course_id)
);

-- RAG DOCUMENTS (Source files for RAG)
CREATE TABLE public.rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    file_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    source_type TEXT NOT NULL, -- 'notes', 'textbook', 'pyq'
    exam_type TEXT,
    year INTEGER,
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'indexed', 'failed'
    error_message TEXT,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- RAG CHUNKS (Vector store)
CREATE TABLE public.rag_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES public.rag_documents(id) ON DELETE CASCADE,
    course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384), -- Using all-MiniLM-L6-v2 (384 dimensions)
    metadata JSONB DEFAULT '{}'::jsonb
);

-- RAG SETS (Generated quizzes or paper drafts)
CREATE TABLE public.rag_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
    mode TEXT NOT NULL, -- 'quiz_generation' or 'paper_style'
    exam_type TEXT,
    topic_tags TEXT[],
    difficulty TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'draft', -- 'generating', 'draft', 'approved', 'rejected'
    total_marks INTEGER,
    total_questions INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    approved_at TIMESTAMP WITH TIME ZONE
);

-- RAG QUESTIONS (Individual generated questions)
CREATE TABLE public.rag_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    set_id UUID REFERENCES public.rag_sets(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL, -- 'mcq', 'short_answer', 'long_answer', etc
    options TEXT[], -- JSON array for MCQ options
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    marks INTEGER DEFAULT 1,
    bloom_level TEXT,
    source_chunk_ids UUID[],
    faithfulness_score FLOAT,
    teacher_edited BOOLEAN DEFAULT FALSE,
    question_order INTEGER DEFAULT 0
);

-- QUIZ ATTEMPTS (Student taking a quiz)
CREATE TABLE public.quiz_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    set_id UUID REFERENCES public.rag_sets(id) ON DELETE CASCADE,
    answers JSONB DEFAULT '{}'::jsonb, -- map of question_id to selected answer
    score FLOAT,
    total_marks INTEGER,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    submitted_at TIMESTAMP WITH TIME ZONE,
    time_spent_seconds INTEGER,
    status TEXT DEFAULT 'in_progress'
);

-- SCHEDULER EVENTS
CREATE TABLE public.calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL, -- 'lecture', 'meeting', 'exam', 'other'
    start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    end_at TIMESTAMP WITH TIME ZONE NOT NULL,
    course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
    location TEXT,
    creator_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    color TEXT DEFAULT '#4285F4',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- NOTICES (Notice Board)
CREATE TABLE public.notices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    notice_type TEXT DEFAULT 'announcement', -- 'announcement', 'assignment', 'grade', 'event'
    course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
    author_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- NOTICE READS (Track unread notifications)
CREATE TABLE public.notice_reads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notice_id UUID REFERENCES public.notices(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    read_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    UNIQUE(notice_id, user_id)
);


-- ==============================================================================
-- 3. Storage Buckets Setup
-- ==============================================================================
INSERT INTO storage.buckets (id, name, public) VALUES ('materials', 'materials', false) ON CONFLICT DO NOTHING;


-- ==============================================================================
-- 4. Auth Triggers
-- ==============================================================================

-- Function to handle new user signups and create a profile automatically
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, role, department)
  VALUES (
    NEW.id, 
    NEW.email, 
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)), 
    COALESCE(NEW.raw_user_meta_data->>'role', 'student'),
    NEW.raw_user_meta_data->>'department'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to execute the function on auth.users insert
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();


-- ==============================================================================
-- 5. pgvector Search RPC
-- ==============================================================================

-- RPC function for semantic search across chunks
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(384),
    filter_course_id UUID,
    match_threshold FLOAT,
    match_count INT
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    document_id UUID,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rag_chunks.id,
        rag_chunks.content,
        rag_chunks.document_id,
        1 - (rag_chunks.embedding <=> query_embedding) AS similarity
    FROM rag_chunks
    WHERE rag_chunks.course_id = filter_course_id
      AND 1 - (rag_chunks.embedding <=> query_embedding) > match_threshold
    ORDER BY rag_chunks.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
