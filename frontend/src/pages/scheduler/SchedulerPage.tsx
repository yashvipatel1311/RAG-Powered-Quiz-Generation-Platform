// ============================================================
// Academix AI — Scheduler Page
// Google Calendar-style month grid with color-coded events
// ============================================================
import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import api from '@/lib/api'
import type { CalendarEvent } from '@/lib/types'
import { ChevronLeft, ChevronRight, Plus, X } from 'lucide-react'
import {
  format, startOfMonth, endOfMonth, startOfWeek, endOfWeek,
  eachDayOfInterval, isSameMonth, isToday, isSameDay,
  addMonths, subMonths,
} from 'date-fns'
import toast from 'react-hot-toast'

export default function SchedulerPage() {
  const { user } = useAuth()
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)

  // Form state
  const [formTitle, setFormTitle] = useState('')
  const [formType, setFormType] = useState('lecture')
  const [formStart, setFormStart] = useState('')
  const [formEnd, setFormEnd] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formCourseId, setFormCourseId] = useState('')
  const [courses, setCourses] = useState<any[]>([])

  useEffect(() => {
    loadEvents()
    api.get('/courses/').then(r => setCourses(r.data || []))
  }, [currentMonth])

  const loadEvents = async () => {
    setLoading(true)
    try {
      const start = startOfMonth(currentMonth).toISOString()
      const end = endOfMonth(currentMonth).toISOString()
      const { data } = await api.get('/scheduler/events', { params: { start_date: start, end_date: end } })
      setEvents(data || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  const createEvent = async () => {
    if (!formTitle || !formStart || !formEnd) { toast.error('Fill required fields'); return }
    try {
      await api.post('/scheduler/events', {
        title: formTitle, event_type: formType,
        start_at: new Date(formStart).toISOString(),
        end_at: new Date(formEnd).toISOString(),
        course_id: formCourseId || null,
        description: formDesc || null,
      })
      toast.success('Event created')
      setShowCreate(false)
      setFormTitle(''); setFormType('lecture'); setFormStart(''); setFormEnd(''); setFormDesc(''); setFormCourseId('')
      loadEvents()
    } catch { toast.error('Failed to create event') }
  }

  // Calendar grid
  const monthStart = startOfMonth(currentMonth)
  const monthEnd = endOfMonth(currentMonth)
  const calStart = startOfWeek(monthStart, { weekStartsOn: 0 })
  const calEnd = endOfWeek(monthEnd, { weekStartsOn: 0 })
  const days = eachDayOfInterval({ start: calStart, end: calEnd })

  const getEventsForDay = (day: Date) =>
    events.filter(e => isSameDay(new Date(e.start_at), day))

  const isTeacher = user?.role === 'teacher' || user?.role === 'admin'

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Scheduler</h1>
        {isTeacher && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} /> New Event
          </button>
        )}
      </div>

      {/* Month Navigation */}
      <div className="flex-between" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost btn-icon" onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}>
            <ChevronLeft size={20} />
          </button>
          <h2 style={{ fontSize: 20, minWidth: 200, textAlign: 'center' }}>
            {format(currentMonth, 'MMMM yyyy')}
          </h2>
          <button className="btn btn-ghost btn-icon" onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}>
            <ChevronRight size={20} />
          </button>
        </div>
        <button className="btn btn-secondary" onClick={() => setCurrentMonth(new Date())}>Today</button>
      </div>

      {/* Calendar Grid */}
      <div className="calendar-grid">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
          <div key={d} className="calendar-day-header">{d}</div>
        ))}
        {days.map(day => {
          const dayEvents = getEventsForDay(day)
          return (
            <div key={day.toISOString()}
              className={`calendar-day ${!isSameMonth(day, currentMonth) ? 'other-month' : ''} ${isToday(day) ? 'today' : ''}`}>
              <div className={isToday(day) ? 'day-number' : ''} style={{ fontSize: 13, marginBottom: 4, fontWeight: isToday(day) ? 600 : 400 }}>
                {format(day, 'd')}
              </div>
              {dayEvents.slice(0, 3).map(ev => (
                <div key={ev.id} className="event-chip"
                  style={{ background: ev.color + '22', color: ev.color, borderLeft: `3px solid ${ev.color}` }}
                  onClick={() => setSelectedEvent(ev)} title={ev.title}>
                  {ev.title}
                </div>
              ))}
              {dayEvents.length > 3 && (
                <div className="text-muted" style={{ fontSize: 10, padding: '0 4px' }}>
                  +{dayEvents.length - 3} more
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Event Detail Slide-over */}
      {selectedEvent && (
        <>
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.2)', zIndex: 499 }}
            onClick={() => setSelectedEvent(null)} />
          <div className="slideover" style={{ padding: 24 }}>
            <div className="flex-between" style={{ marginBottom: 20 }}>
              <h3>{selectedEvent.title}</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setSelectedEvent(null)}>
                <X size={20} />
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <span className="text-muted text-small">Type</span>
                <p className="font-medium" style={{ textTransform: 'capitalize' }}>{selectedEvent.event_type.replace('_', ' ')}</p>
              </div>
              <div>
                <span className="text-muted text-small">When</span>
                <p className="font-medium">
                  {format(new Date(selectedEvent.start_at), 'PPp')} — {format(new Date(selectedEvent.end_at), 'p')}
                </p>
              </div>
              {selectedEvent.course_name && (
                <div>
                  <span className="text-muted text-small">Course</span>
                  <p className="font-medium">{selectedEvent.course_name}</p>
                </div>
              )}
              {selectedEvent.location && (
                <div>
                  <span className="text-muted text-small">Location</span>
                  <p className="font-medium">{selectedEvent.location}</p>
                </div>
              )}
              {selectedEvent.description && (
                <div>
                  <span className="text-muted text-small">Description</span>
                  <p>{selectedEvent.description}</p>
                </div>
              )}
              <div>
                <span className="text-muted text-small">Created by</span>
                <p className="font-medium">{selectedEvent.creator_name || 'Unknown'}</p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Create Event Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>New Event</h3>
              <button className="btn btn-ghost btn-icon" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="input-group">
                <label className="input-label">Title *</label>
                <input className="input" value={formTitle} onChange={e => setFormTitle(e.target.value)} placeholder="Event title" />
              </div>
              <div className="grid-2">
                <div className="input-group">
                  <label className="input-label">Type</label>
                  <select className="input" value={formType} onChange={e => setFormType(e.target.value)}>
                    <option value="lecture">Lecture</option>
                    <option value="meeting">Meeting</option>
                    <option value="exam">Exam</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-label">Course</label>
                  <select className="input" value={formCourseId} onChange={e => setFormCourseId(e.target.value)}>
                    <option value="">None (Personal)</option>
                    {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid-2">
                <div className="input-group">
                  <label className="input-label">Start *</label>
                  <input className="input" type="datetime-local" value={formStart} onChange={e => setFormStart(e.target.value)} />
                </div>
                <div className="input-group">
                  <label className="input-label">End *</label>
                  <input className="input" type="datetime-local" value={formEnd} onChange={e => setFormEnd(e.target.value)} />
                </div>
              </div>
              <div className="input-group">
                <label className="input-label">Description</label>
                <textarea className="input" value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={2} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={createEvent}>Create Event</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
