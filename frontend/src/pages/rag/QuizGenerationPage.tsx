// ============================================================
// Academix AI — Quiz Generation Page (Student)
// Gemini-style conversational interface + NotebookLM sources panel
// ============================================================
import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/lib/api'
import type { Course, GeneratedSet, GeneratedQuestion } from '@/lib/types'
import { Sparkles, Send, BookOpen, ChevronDown, ChevronUp, RotateCcw, CheckCircle, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'

export default function QuizGenerationPage() {
  const { user } = useAuth()
  const [courses, setCourses] = useState<Course[]>([])
  const [selectedCourse, setSelectedCourse] = useState('')
  const [topicInput, setTopicInput] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [questionCount, setQuestionCount] = useState(10)
  const [questionTypes, setQuestionTypes] = useState(['mcq', 'short_answer'])
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState<GeneratedSet | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({})
  const [attemptId, setAttemptId] = useState<string | null>(null)
  const [score, setScore] = useState<{ score: number; total: number } | null>(null)

  useEffect(() => {
    api.get('/courses/').then(r => setCourses(r.data || []))
  }, [])

  const generate = async () => {
    if (!selectedCourse) { toast.error('Select a course first'); return }
    setGenerating(true)
    setResult(null)
    setSubmitted(false)
    setAnswers({})
    setScore(null)
    try {
      const { data } = await api.post('/rag/generate', {
        course_id: selectedCourse,
        mode: 'quiz_generation',
        topic_tags: topicInput ? topicInput.split(',').map(t => t.trim()) : [],
        difficulty,
        question_count: questionCount,
        question_types: questionTypes,
      })
      setResult(data)
      // Start attempt
      const attempt = await api.post('/rag/attempts', { set_id: data.id })
      setAttemptId(attempt.data.id)
      toast.success(`Generated ${data.questions?.length || 0} questions!`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Generation failed')
    }
    setGenerating(false)
  }

  const submitQuiz = async () => {
    if (!attemptId) return
    try {
      const { data } = await api.post(`/rag/attempts/${attemptId}/submit`, { answers })
      setSubmitted(true)
      setScore({ score: data.score || 0, total: data.total_marks || 0 })
      toast.success('Quiz submitted!')
    } catch { toast.error('Submission failed') }
  }

  return (
    <div className="quiz-container">
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Sparkles size={28} color="#4285F4" /> Quiz Generation
          </h1>
          <p className="text-muted" style={{ marginTop: 4 }}>Practice with AI-generated questions from your course material</p>
        </div>
      </div>

      {/* Generation Prompt Area (Gemini-style) */}
      <div className="rag-prompt-area" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="grid-2" style={{ gap: 12 }}>
            <div className="input-group">
              <label className="input-label">Course</label>
              <select className="input" value={selectedCourse} onChange={e => setSelectedCourse(e.target.value)}>
                <option value="">Select a course...</option>
                {courses.map(c => <option key={c.id} value={c.id}>{c.name} ({c.code})</option>)}
              </select>
            </div>
            <div className="input-group">
              <label className="input-label">Difficulty</label>
              <select className="input" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>
          </div>
          <div className="input-group">
            <label className="input-label">Topics (comma-separated, or leave blank for all)</label>
            <input className="input" placeholder="e.g. Sorting algorithms, Binary trees, Graph traversal"
              value={topicInput} onChange={e => setTopicInput(e.target.value)} />
          </div>
          <div className="flex-between">
            <div style={{ display: 'flex', gap: 8 }}>
              {['mcq', 'short_answer', 'true_false'].map(qt => (
                <label key={qt} className={`badge ${questionTypes.includes(qt) ? 'badge-blue' : 'badge-gray'}`}
                  style={{ cursor: 'pointer', padding: '4px 12px' }}>
                  <input type="checkbox" hidden checked={questionTypes.includes(qt)}
                    onChange={() => {
                      setQuestionTypes(prev =>
                        prev.includes(qt) ? prev.filter(t => t !== qt) : [...prev, qt]
                      )
                    }} />
                  {qt.replace('_', ' ')}
                </label>
              ))}
            </div>
            <button className="btn btn-primary" onClick={generate} disabled={generating || !selectedCourse}>
              {generating ? (
                <><span style={{ animation: 'spin 0.8s linear infinite', display: 'inline-block' }}>⟳</span> Generating...</>
              ) : (
                <><Send size={16} /> Generate Quiz</>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Generating Animation */}
      {generating && (
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div style={{
            width: 48, height: 48, border: '3px solid var(--color-border)',
            borderTopColor: 'var(--color-primary)', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite', margin: '0 auto 16px',
          }} />
          <p className="font-medium">Generating your quiz...</p>
          <p className="text-muted text-small">Retrieving relevant content & creating questions</p>
        </div>
      )}

      {/* Score Card */}
      {score && (
        <div className="card" style={{
          padding: 24, marginBottom: 24, textAlign: 'center',
          background: 'linear-gradient(135deg, #E6F4EA, #E8F0FE)',
        }}>
          <h2 style={{ fontSize: 20, marginBottom: 8 }}>Quiz Complete!</h2>
          <p style={{ fontSize: 36, fontWeight: 700, color: 'var(--color-primary)' }}>
            {score.score} / {score.total}
          </p>
          <p className="text-muted">
            {Math.round((score.score / Math.max(score.total, 1)) * 100)}% correct
          </p>
          <button className="btn btn-secondary" style={{ marginTop: 16 }} onClick={() => {
            setResult(null); setSubmitted(false); setScore(null); setAnswers({})
          }}>
            <RotateCcw size={16} /> Generate Another Quiz
          </button>
        </div>
      )}

      {/* Generated Questions */}
      {result && result.questions && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {result.questions.map((q, idx) => (
            <div key={q.id} className="question-card">
              <div className="flex-between" style={{ marginBottom: 12 }}>
                <span className="font-semibold">Q{idx + 1}. <span className="badge badge-ai">AI Generated</span></span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <span className="badge badge-gray">{q.marks} {q.marks === 1 ? 'mark' : 'marks'}</span>
                  {q.bloom_level && <span className="badge badge-purple">{q.bloom_level}</span>}
                </div>
              </div>

              <p style={{ marginBottom: 12, lineHeight: 1.6 }}>{q.question_text}</p>

              {/* MCQ Options */}
              {q.question_type === 'mcq' && q.options && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {q.options.map((opt, oi) => {
                    const isSelected = answers[q.id] === opt
                    const isCorrect = submitted && opt.toLowerCase().startsWith(q.correct_answer.toLowerCase().charAt(0))
                    return (
                      <label key={oi} style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 14px', borderRadius: 8, cursor: submitted ? 'default' : 'pointer',
                        border: `2px solid ${isSelected ? 'var(--color-primary)' : 'var(--color-border)'}`,
                        background: submitted
                          ? isCorrect ? '#E6F4EA' : isSelected ? '#FCE8E6' : 'white'
                          : isSelected ? 'var(--color-primary-bg)' : 'white',
                        transition: 'all .15s',
                      }}>
                        <input type="radio" name={q.id} value={opt}
                          checked={isSelected} disabled={submitted}
                          onChange={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))} />
                        <span style={{ flex: 1 }}>{opt}</span>
                        {submitted && isCorrect && <CheckCircle size={18} color="#0F9D58" />}
                        {submitted && isSelected && !isCorrect && <XCircle size={18} color="#DB4437" />}
                      </label>
                    )
                  })}
                </div>
              )}

              {/* Short answer */}
              {(q.question_type === 'short_answer' || q.question_type === 'fill_blank') && (
                <input className="input" placeholder="Type your answer..."
                  value={answers[q.id] || ''} disabled={submitted}
                  onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))} />
              )}

              {/* True/False */}
              {q.question_type === 'true_false' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  {['True', 'False'].map(opt => (
                    <button key={opt}
                      className={`btn ${answers[q.id] === opt ? 'btn-primary' : 'btn-secondary'}`}
                      disabled={submitted}
                      onClick={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}>
                      {opt}
                    </button>
                  ))}
                </div>
              )}

              {/* Correct answer + explanation (after submit) */}
              {submitted && (
                <div style={{
                  marginTop: 12, padding: 12, borderRadius: 8,
                  background: 'var(--color-surface-2)', fontSize: 13,
                }}>
                  <p><strong>Correct Answer:</strong> {q.correct_answer}</p>
                  {q.explanation && <p style={{ marginTop: 4 }}><strong>Explanation:</strong> {q.explanation}</p>}
                </div>
              )}

              {/* Sources (NotebookLM-style collapsible) */}
              {q.source_texts && q.source_texts.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <button className="btn btn-ghost text-small"
                    onClick={() => setExpandedSources(prev => ({ ...prev, [q.id]: !prev[q.id] }))}>
                    <BookOpen size={14} /> {expandedSources[q.id] ? 'Hide' : 'View'} Sources
                    {expandedSources[q.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {expandedSources[q.id] && (
                    <div className="sources-panel" style={{ marginTop: 6 }}>
                      {q.source_texts.map((src, si) => (
                        <div key={si} className="source-chunk">{src}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Submit button */}
          {!submitted && result.questions.length > 0 && (
            <button className="btn btn-primary" onClick={submitQuiz}
              style={{ padding: '14px 32px', fontSize: 15, alignSelf: 'center' }}>
              Submit Quiz
            </button>
          )}
        </div>
      )}
    </div>
  )
}
