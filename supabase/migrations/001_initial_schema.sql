-- ============================================================
-- Academix AI — Phase 1 Database Schema
-- Run this in your Supabase SQL Editor (Dashboard > SQL Editor)
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for embeddings

-- ============================================================
-- 1. PROFILES (extends Supabase auth.users)
-- ============================================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    department TEXT,
    avatar_url TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile on signup via trigger
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'New User'),
        COALESCE(NEW.raw_user_meta_data->>'role', 'student')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ============================================================
-- 2. DEPARTMENTS & COURSES
-- ============================================================
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    semester INTEGER,
    description TEXT,
    banner_color TEXT DEFAULT '#4285F4',
    created_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(course_id, name)
);

-- ============================================================
-- 3. ENROLLMENTS
-- ============================================================
CREATE TABLE enrollments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    section_id UUID REFERENCES sections(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('teacher', 'student')),
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(course_id, user_id)
);

-- ============================================================
-- 4. CLASSROOM — Announcements, Materials, Assignments, Submissions, Grades
-- ============================================================
CREATE TABLE announcements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    posted_by UUID NOT NULL REFERENCES profiles(id),
    text TEXT NOT NULL,
    attachment_urls JSONB DEFAULT '[]'::jsonb,
    posted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE materials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES profiles(id),
    title TEXT NOT NULL,
    description TEXT,
    file_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size BIGINT,
    topic_tag TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES profiles(id),
    title TEXT NOT NULL,
    instructions TEXT,
    attachment_urls JSONB DEFAULT '[]'::jsonb,
    due_at TIMESTAMPTZ,
    max_points INTEGER DEFAULT 100,
    topic_tag TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES profiles(id),
    file_url TEXT,
    text_response TEXT,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('not_submitted', 'submitted', 'late', 'graded')),
    UNIQUE(assignment_id, student_id)
);

CREATE TABLE grades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE UNIQUE,
    points_awarded INTEGER NOT NULL,
    feedback_text TEXT,
    graded_by UUID NOT NULL REFERENCES profiles(id),
    graded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. SCHEDULER — Events
-- ============================================================
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    section_id UUID REFERENCES sections(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES profiles(id),
    title TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('lecture', 'meeting', 'exam', 'assignment_due', 'other')),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    is_all_day BOOLEAN DEFAULT FALSE,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_rule JSONB,
    color TEXT DEFAULT '#4285F4',
    location TEXT,
    reminder_minutes INTEGER DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_time_range CHECK (end_at > start_at)
);

-- ============================================================
-- 6. NOTICE BOARD
-- ============================================================
CREATE TABLE notices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,  -- NULL = institute-wide
    posted_by UUID NOT NULL REFERENCES profiles(id),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    notice_type TEXT NOT NULL
        CHECK (notice_type IN ('announcement', 'assignment', 'grade', 'event', 'system', 'admin')),
    target_roles JSONB DEFAULT '["admin", "teacher", "student"]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE notice_reads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    notice_id UUID NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    read_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(notice_id, user_id)
);

-- ============================================================
-- 7. RAG ENGINE — Content Documents & Chunks
-- ============================================================
CREATE TABLE content_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES profiles(id),
    file_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size BIGINT,
    source_type TEXT NOT NULL CHECK (source_type IN ('notes', 'textbook', 'pyq')),
    exam_type TEXT CHECK (exam_type IN ('internal', 'external')),
    year INTEGER,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'indexed', 'failed')),
    error_message TEXT,
    page_count INTEGER,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE content_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES content_documents(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id),
    text TEXT NOT NULL,
    topic_tag TEXT,
    page_ref TEXT,
    source_type TEXT NOT NULL,
    exam_type TEXT,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER,
    embedding vector(384),  -- 384 dims for all-MiniLM-L6-v2
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 8. RAG ENGINE — PYQ Questions & Style Profiles
-- ============================================================
CREATE TABLE pyq_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES content_documents(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id),
    question_text TEXT NOT NULL,
    marks INTEGER,
    section TEXT,
    question_type TEXT CHECK (question_type IN ('mcq', 'short_answer', 'long_answer', 'numerical', 'essay')),
    bloom_level TEXT CHECK (bloom_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')),
    topic_tag TEXT,
    year INTEGER,
    exam_type TEXT CHECK (exam_type IN ('internal', 'external')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE style_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    exam_type TEXT NOT NULL CHECK (exam_type IN ('internal', 'external')),
    total_marks INTEGER,
    duration_minutes INTEGER,
    section_structure JSONB DEFAULT '[]'::jsonb,
    bloom_distribution JSONB DEFAULT '{}'::jsonb,
    common_patterns JSONB DEFAULT '{}'::jsonb,
    question_count INTEGER,
    confidence_score FLOAT DEFAULT 0.0,
    pyq_count INTEGER DEFAULT 0,
    last_computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(course_id, exam_type)
);

-- ============================================================
-- 9. RAG ENGINE — Generated Sets & Questions
-- ============================================================
CREATE TABLE generated_sets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requested_by UUID NOT NULL REFERENCES profiles(id),
    course_id UUID NOT NULL REFERENCES courses(id),
    mode TEXT NOT NULL CHECK (mode IN ('quiz_generation', 'paper_style')),
    exam_type TEXT CHECK (exam_type IN ('internal', 'external')),
    topic_tags JSONB DEFAULT '[]'::jsonb,
    difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    status TEXT NOT NULL DEFAULT 'generating'
        CHECK (status IN ('generating', 'draft', 'approved', 'rejected')),
    total_marks INTEGER,
    total_questions INTEGER,
    generation_config JSONB DEFAULT '{}'::jsonb,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE generated_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    set_id UUID NOT NULL REFERENCES generated_sets(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL
        CHECK (question_type IN ('mcq', 'short_answer', 'long_answer', 'true_false', 'fill_blank')),
    options JSONB,  -- For MCQ: ["Option A", "Option B", "Option C", "Option D"]
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    marks INTEGER DEFAULT 1,
    bloom_level TEXT CHECK (bloom_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')),
    source_chunk_ids JSONB DEFAULT '[]'::jsonb,
    source_texts JSONB DEFAULT '[]'::jsonb,  -- Denormalized source text for display
    faithfulness_score FLOAT,
    teacher_edited BOOLEAN DEFAULT FALSE,
    question_order INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 10. STUDENT QUIZ ATTEMPTS
-- ============================================================
CREATE TABLE student_quiz_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES profiles(id),
    set_id UUID NOT NULL REFERENCES generated_sets(id),
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    score FLOAT,
    total_marks INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    time_spent_seconds INTEGER,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'submitted'))
);

-- ============================================================
-- 11. INDEXES
-- ============================================================

-- Vector similarity search index (HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_content_chunks_embedding
    ON content_chunks USING hnsw (embedding vector_cosine_ops);

-- Relational indexes for common queries
CREATE INDEX idx_enrollments_user ON enrollments(user_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
CREATE INDEX idx_content_chunks_course ON content_chunks(course_id);
CREATE INDEX idx_content_chunks_document ON content_chunks(document_id);
CREATE INDEX idx_content_chunks_source ON content_chunks(source_type);
CREATE INDEX idx_content_documents_course ON content_documents(course_id);
CREATE INDEX idx_content_documents_status ON content_documents(status);
CREATE INDEX idx_events_course ON events(course_id);
CREATE INDEX idx_events_dates ON events(start_at, end_at);
CREATE INDEX idx_events_creator ON events(created_by);
CREATE INDEX idx_notices_course ON notices(course_id);
CREATE INDEX idx_notices_type ON notices(notice_type);
CREATE INDEX idx_assignments_course ON assignments(course_id);
CREATE INDEX idx_assignments_due ON assignments(due_at);
CREATE INDEX idx_submissions_assignment ON submissions(assignment_id);
CREATE INDEX idx_submissions_student ON submissions(student_id);
CREATE INDEX idx_generated_sets_course ON generated_sets(course_id);
CREATE INDEX idx_generated_sets_user ON generated_sets(requested_by);
CREATE INDEX idx_generated_questions_set ON generated_questions(set_id);
CREATE INDEX idx_quiz_attempts_student ON student_quiz_attempts(student_id);
CREATE INDEX idx_quiz_attempts_set ON student_quiz_attempts(set_id);
CREATE INDEX idx_pyq_questions_course ON pyq_questions(course_id);
CREATE INDEX idx_notice_reads_user ON notice_reads(user_id);
CREATE INDEX idx_materials_course ON materials(course_id);
CREATE INDEX idx_announcements_course ON announcements(course_id);

-- ============================================================
-- 12. VECTOR SEARCH RPC FUNCTION
-- ============================================================
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(384),
    p_course_id UUID,
    p_source_type TEXT DEFAULT NULL,
    p_exam_type TEXT DEFAULT NULL,
    p_topic_tag TEXT DEFAULT NULL,
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    text TEXT,
    topic_tag TEXT,
    page_ref TEXT,
    source_type TEXT,
    exam_type TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cc.id,
        cc.document_id,
        cc.text,
        cc.topic_tag,
        cc.page_ref,
        cc.source_type,
        cc.exam_type,
        (1 - (cc.embedding <=> query_embedding))::FLOAT AS similarity
    FROM content_chunks cc
    WHERE cc.course_id = p_course_id
        AND (p_source_type IS NULL OR cc.source_type = p_source_type)
        AND (p_exam_type IS NULL OR cc.exam_type = p_exam_type)
        AND (p_topic_tag IS NULL OR cc.topic_tag = p_topic_tag)
        AND cc.embedding IS NOT NULL
        AND (1 - (cc.embedding <=> query_embedding)) > match_threshold
    ORDER BY cc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================
-- 13. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE announcements ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE notice_reads ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE pyq_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE style_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_quiz_attempts ENABLE ROW LEVEL SECURITY;

-- --------------------------------------------------------
-- Profiles: users can read all profiles, update only their own
-- --------------------------------------------------------
CREATE POLICY "profiles_select_all" ON profiles FOR SELECT USING (true);
CREATE POLICY "profiles_update_own" ON profiles FOR UPDATE USING (auth.uid() = id);

-- --------------------------------------------------------
-- Departments & Courses: everyone can read; admins can write
-- --------------------------------------------------------
CREATE POLICY "departments_select" ON departments FOR SELECT USING (true);
CREATE POLICY "departments_admin_insert" ON departments FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "departments_admin_update" ON departments FOR UPDATE
    USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));

CREATE POLICY "courses_select" ON courses FOR SELECT USING (true);
CREATE POLICY "courses_admin_insert" ON courses FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "courses_admin_update" ON courses FOR UPDATE
    USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));

CREATE POLICY "sections_select" ON sections FOR SELECT USING (true);
CREATE POLICY "sections_admin_insert" ON sections FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));

-- --------------------------------------------------------
-- Enrollments: users see their own; admins/teachers see course enrollments
-- --------------------------------------------------------
CREATE POLICY "enrollments_select" ON enrollments FOR SELECT
    USING (
        user_id = auth.uid()
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
        OR EXISTS (
            SELECT 1 FROM enrollments e
            WHERE e.course_id = enrollments.course_id
            AND e.user_id = auth.uid()
            AND e.role = 'teacher'
        )
    );
CREATE POLICY "enrollments_admin_insert" ON enrollments FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin', 'teacher')));
CREATE POLICY "enrollments_admin_delete" ON enrollments FOR DELETE
    USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));

-- --------------------------------------------------------
-- Classroom: announcements, materials, assignments visible to enrolled users
-- --------------------------------------------------------
CREATE POLICY "announcements_select" ON announcements FOR SELECT
    USING (EXISTS (SELECT 1 FROM enrollments WHERE course_id = announcements.course_id AND user_id = auth.uid()));
CREATE POLICY "announcements_teacher_insert" ON announcements FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM enrollments
        WHERE course_id = announcements.course_id AND user_id = auth.uid() AND role = 'teacher'
    ));

CREATE POLICY "materials_select" ON materials FOR SELECT
    USING (EXISTS (SELECT 1 FROM enrollments WHERE course_id = materials.course_id AND user_id = auth.uid()));
CREATE POLICY "materials_teacher_insert" ON materials FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM enrollments
        WHERE course_id = materials.course_id AND user_id = auth.uid() AND role = 'teacher'
    ));

CREATE POLICY "assignments_select" ON assignments FOR SELECT
    USING (EXISTS (SELECT 1 FROM enrollments WHERE course_id = assignments.course_id AND user_id = auth.uid()));
CREATE POLICY "assignments_teacher_insert" ON assignments FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM enrollments
        WHERE course_id = assignments.course_id AND user_id = auth.uid() AND role = 'teacher'
    ));
CREATE POLICY "assignments_teacher_update" ON assignments FOR UPDATE
    USING (created_by = auth.uid());

-- --------------------------------------------------------
-- Submissions: students see own; teachers see all for their courses
-- --------------------------------------------------------
CREATE POLICY "submissions_select" ON submissions FOR SELECT
    USING (
        student_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM assignments a
            JOIN enrollments e ON e.course_id = a.course_id
            WHERE a.id = submissions.assignment_id
            AND e.user_id = auth.uid()
            AND e.role = 'teacher'
        )
    );
CREATE POLICY "submissions_student_insert" ON submissions FOR INSERT
    WITH CHECK (student_id = auth.uid());
CREATE POLICY "submissions_student_update" ON submissions FOR UPDATE
    USING (student_id = auth.uid());

-- --------------------------------------------------------
-- Grades: students see own; teachers can insert/update
-- --------------------------------------------------------
CREATE POLICY "grades_select" ON grades FOR SELECT
    USING (
        EXISTS (SELECT 1 FROM submissions s WHERE s.id = grades.submission_id AND s.student_id = auth.uid())
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin', 'teacher'))
    );
CREATE POLICY "grades_teacher_insert" ON grades FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'teacher'));
CREATE POLICY "grades_teacher_update" ON grades FOR UPDATE
    USING (graded_by = auth.uid());

-- --------------------------------------------------------
-- Events: visible to enrolled users and admins
-- --------------------------------------------------------
CREATE POLICY "events_select" ON events FOR SELECT
    USING (
        course_id IS NULL  -- institute-wide events
        OR EXISTS (SELECT 1 FROM enrollments WHERE course_id = events.course_id AND user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );
CREATE POLICY "events_teacher_insert" ON events FOR INSERT
    WITH CHECK (
        EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin', 'teacher'))
    );
CREATE POLICY "events_teacher_update" ON events FOR UPDATE
    USING (created_by = auth.uid() OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "events_teacher_delete" ON events FOR DELETE
    USING (created_by = auth.uid() OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));

-- --------------------------------------------------------
-- Notices: visible based on target roles and course enrollment
-- --------------------------------------------------------
CREATE POLICY "notices_select" ON notices FOR SELECT
    USING (
        (course_id IS NULL AND target_roles ? (SELECT role FROM profiles WHERE id = auth.uid()))
        OR EXISTS (SELECT 1 FROM enrollments WHERE course_id = notices.course_id AND user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );
CREATE POLICY "notices_insert" ON notices FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin', 'teacher')));

CREATE POLICY "notice_reads_select" ON notice_reads FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "notice_reads_insert" ON notice_reads FOR INSERT WITH CHECK (user_id = auth.uid());

-- --------------------------------------------------------
-- RAG Content: visible to enrolled users; teachers/admins can upload
-- --------------------------------------------------------
CREATE POLICY "content_documents_select" ON content_documents FOR SELECT
    USING (EXISTS (SELECT 1 FROM enrollments WHERE course_id = content_documents.course_id AND user_id = auth.uid()));
CREATE POLICY "content_documents_insert" ON content_documents FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin', 'teacher')));
CREATE POLICY "content_documents_update" ON content_documents FOR UPDATE
    USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('admin', 'teacher')));

CREATE POLICY "content_chunks_select" ON content_chunks FOR SELECT
    USING (EXISTS (SELECT 1 FROM enrollments WHERE course_id = content_chunks.course_id AND user_id = auth.uid()));

CREATE POLICY "pyq_questions_select" ON pyq_questions FOR SELECT
    USING (
        -- Students should NOT see raw PYQ questions (security requirement §14)
        EXISTS (
            SELECT 1 FROM enrollments
            WHERE course_id = pyq_questions.course_id AND user_id = auth.uid() AND role = 'teacher'
        )
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "style_profiles_select" ON style_profiles FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM enrollments
            WHERE course_id = style_profiles.course_id AND user_id = auth.uid() AND role = 'teacher'
        )
        OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
    );

-- --------------------------------------------------------
-- Generated Sets & Questions: users see their own
-- --------------------------------------------------------
CREATE POLICY "generated_sets_select" ON generated_sets FOR SELECT
    USING (requested_by = auth.uid() OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "generated_sets_insert" ON generated_sets FOR INSERT
    WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "generated_sets_update" ON generated_sets FOR UPDATE
    USING (requested_by = auth.uid());

CREATE POLICY "generated_questions_select" ON generated_questions FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM generated_sets gs WHERE gs.id = generated_questions.set_id AND gs.requested_by = auth.uid()
    ));

CREATE POLICY "student_quiz_attempts_select" ON student_quiz_attempts FOR SELECT
    USING (student_id = auth.uid());
CREATE POLICY "student_quiz_attempts_insert" ON student_quiz_attempts FOR INSERT
    WITH CHECK (student_id = auth.uid());
CREATE POLICY "student_quiz_attempts_update" ON student_quiz_attempts FOR UPDATE
    USING (student_id = auth.uid());

-- ============================================================
-- 14. STORAGE BUCKETS (run these separately in Supabase Dashboard > Storage)
-- ============================================================
-- You need to create these buckets manually in Supabase Dashboard:
--   1. "course-materials" — for lecture notes, slides, textbooks
--   2. "pyq-papers"      — for previous year question papers
--   3. "submissions"     — for student assignment submissions
--   4. "avatars"         — for user profile pictures
--
-- Set each bucket's privacy:
--   - course-materials: private (RLS via signed URLs)
--   - pyq-papers: private
--   - submissions: private
--   - avatars: public

-- ============================================================
-- 15. HELPER FUNCTIONS
-- ============================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER set_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON assignments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON content_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON generated_sets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
