// ============================================================
// Academix AI — Manage Courses Page (Admin)
// Course CRUD, sections, enrollments
// ============================================================
import { useState, useEffect } from 'react'
import api from '@/lib/api'
import type { Course, User } from '@/lib/types'
import { Plus, Users, BookOpen, Settings } from 'lucide-react'
import toast from 'react-hot-toast'

export default function ManageCoursesPage() {
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showEnroll, setShowEnroll] = useState<string | null>(null)
  const [allUsers, setAllUsers] = useState<User[]>([])

  const [formName, setFormName] = useState('')
  const [formCode, setFormCode] = useState('')
  const [formSemester, setFormSemester] = useState('')
  const [formDesc, setFormDesc] = useState('')

  const [enrollUserId, setEnrollUserId] = useState('')
  const [enrollRole, setEnrollRole] = useState('student')

  useEffect(() => {
    loadCourses()
    api.get('/users/').then(r => setAllUsers(r.data || []))
  }, [])

  const loadCourses = async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/courses/')
      setCourses(data || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  const createCourse = async () => {
    if (!formName || !formCode) { toast.error('Name and code are required'); return }
    try {
      await api.post('/courses/', {
        name: formName, code: formCode,
        semester: formSemester ? Number(formSemester) : null,
        description: formDesc || null,
      })
      toast.success('Course created')
      setShowCreate(false)
      setFormName(''); setFormCode(''); setFormSemester(''); setFormDesc('')
      loadCourses()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create')
    }
  }

  const enrollUser = async () => {
    if (!showEnroll || !enrollUserId) return
    try {
      await api.post(`/courses/${showEnroll}/enroll`, {
        course_id: showEnroll, user_id: enrollUserId, role: enrollRole,
      })
      toast.success('User enrolled')
      setShowEnroll(null); setEnrollUserId(''); setEnrollRole('student')
      loadCourses()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to enroll')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Manage Courses</h1>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} /> New Course
        </button>
      </div>

      {loading ? (
        <div className="grid-3">
          {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 160 }} />)}
        </div>
      ) : courses.length === 0 ? (
        <div className="card flex-center" style={{ padding: 60, flexDirection: 'column', gap: 12 }}>
          <BookOpen size={48} color="var(--color-text-3)" />
          <p className="text-muted">No courses created yet</p>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>Create First Course</button>
        </div>
      ) : (
        <div className="grid-3">
          {courses.map(course => (
            <div key={course.id} className="card" style={{ overflow: 'hidden' }}>
              <div style={{ background: course.banner_color, padding: '16px 20px', color: 'white' }}>
                <h3 style={{ color: 'white', fontSize: 16 }}>{course.name}</h3>
                <p style={{ opacity: 0.8, fontSize: 12, marginTop: 2 }}>{course.code}</p>
              </div>
              <div style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <span className="badge badge-blue">{course.teacher_count || 0} teachers</span>
                  <span className="badge badge-green">{course.student_count || 0} students</span>
                </div>
                {course.semester && (
                  <p className="text-muted text-small">Semester {course.semester}</p>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button className="btn btn-secondary" style={{ flex: 1, justifyContent: 'center' }}
                    onClick={() => setShowEnroll(course.id)}>
                    <Users size={14} /> Enroll
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Course Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Create Course</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="input-group">
                <label className="input-label">Course Name *</label>
                <input className="input" value={formName} onChange={e => setFormName(e.target.value)}
                  placeholder="e.g. Data Structures & Algorithms" />
              </div>
              <div className="grid-2">
                <div className="input-group">
                  <label className="input-label">Course Code *</label>
                  <input className="input" value={formCode} onChange={e => setFormCode(e.target.value)}
                    placeholder="e.g. CS301" />
                </div>
                <div className="input-group">
                  <label className="input-label">Semester</label>
                  <input className="input" type="number" value={formSemester}
                    onChange={e => setFormSemester(e.target.value)} placeholder="e.g. 5" />
                </div>
              </div>
              <div className="input-group">
                <label className="input-label">Description</label>
                <textarea className="input" value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={2} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={createCourse}>Create</button>
            </div>
          </div>
        </div>
      )}

      {/* Enroll User Modal */}
      {showEnroll && (
        <div className="modal-overlay" onClick={() => setShowEnroll(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Enroll User</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowEnroll(null)}>✕</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="input-group">
                <label className="input-label">User</label>
                <select className="input" value={enrollUserId} onChange={e => setEnrollUserId(e.target.value)}>
                  <option value="">Select user...</option>
                  {allUsers.map(u => (
                    <option key={u.id} value={u.id}>{u.full_name} ({u.email}) — {u.role}</option>
                  ))}
                </select>
              </div>
              <div className="input-group">
                <label className="input-label">Enroll as</label>
                <select className="input" value={enrollRole} onChange={e => setEnrollRole(e.target.value)}>
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowEnroll(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={enrollUser}>Enroll</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
