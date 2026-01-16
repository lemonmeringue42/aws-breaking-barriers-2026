import { useState, useEffect } from 'react'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '../../../amplify/data/resource'

const client = generateClient<Schema>({ authMode: 'userPool' })

interface DashboardProps {
  userId: string
}

const Dashboard = ({ userId }: DashboardProps) => {
  const [appointments, setAppointments] = useState<any[]>([])
  const [deadlines, setDeadlines] = useState<any[]>([])
  const [documents, setDocuments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [userId])

  const loadData = async () => {
    setLoading(true)
    try {
      // Load appointments
      const apptResponse = await client.models.Appointment.list({
        filter: { userId: { eq: userId }, status: { eq: 'scheduled' } }
      })
      setAppointments(apptResponse.data || [])

      // Load deadlines
      const deadlineResponse = await client.models.Deadline.list({
        filter: { userId: { eq: userId }, completed: { eq: false } }
      })
      setDeadlines(deadlineResponse.data || [])

      // Load documents
      const docResponse = await client.models.Document.list({
        filter: { userId: { eq: userId } }
      })
      setDocuments(docResponse.data || [])
    } catch (error) {
      console.error('Error loading dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getDaysUntil = (isoString: string) => {
    const days = Math.ceil((new Date(isoString).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    if (days < 0) return 'Overdue'
    if (days === 0) return 'Today'
    if (days === 1) return 'Tomorrow'
    return `${days} days`
  }

  if (loading) {
    return <div className="dashboard-loading">Loading your dashboard...</div>
  }

  const hasData = appointments.length > 0 || deadlines.length > 0 || documents.length > 0

  return (
    <div className="dashboard">
      <h2>Your Dashboard</h2>

      {!hasData && (
        <div className="dashboard-empty">
          <p>No appointments, deadlines, or documents yet.</p>
          <p>Ask the assistant to help you book an appointment or track a deadline.</p>
        </div>
      )}

      {appointments.length > 0 && (
        <section className="dashboard-section">
          <h3>📞 Upcoming Appointments</h3>
          <div className="dashboard-cards">
            {appointments.map((appt) => (
              <div key={appt.id} className="dashboard-card appointment-card">
                <div className="card-header">
                  <span className="card-category">{appt.category}</span>
                  <span className={`urgency-badge urgency-${appt.urgencyScore >= 8 ? 'high' : appt.urgencyScore >= 5 ? 'medium' : 'low'}`}>
                    Urgency: {appt.urgencyScore}/10
                  </span>
                </div>
                <div className="card-body">
                  <p className="card-time">{formatDate(appt.scheduledTime)}</p>
                  <p className="card-bureau">{appt.bureauName}</p>
                  {appt.phoneNumber && <p className="card-phone">📱 {appt.phoneNumber}</p>}
                  {appt.caseNotes && <p className="card-notes">{appt.caseNotes}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {deadlines.length > 0 && (
        <section className="dashboard-section">
          <h3>⏰ Important Deadlines</h3>
          <div className="dashboard-cards">
            {deadlines.map((deadline) => (
              <div key={deadline.id} className="dashboard-card deadline-card">
                <div className="card-header">
                  <span className="card-category">{deadline.category}</span>
                  <span className={`priority-badge priority-${deadline.priority}`}>
                    {deadline.priority}
                  </span>
                </div>
                <div className="card-body">
                  <p className="card-title">{deadline.title}</p>
                  <p className="card-due">Due: {formatDate(deadline.dueDate)}</p>
                  <p className={`card-countdown ${getDaysUntil(deadline.dueDate) === 'Today' || getDaysUntil(deadline.dueDate) === 'Overdue' ? 'urgent' : ''}`}>
                    {getDaysUntil(deadline.dueDate)}
                  </p>
                  {deadline.description && <p className="card-description">{deadline.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {documents.length > 0 && (
        <section className="dashboard-section">
          <h3>📄 Your Documents</h3>
          <div className="dashboard-cards">
            {documents.map((doc) => (
              <div key={doc.id} className="dashboard-card document-card">
                <div className="card-header">
                  <span className="card-category">{doc.category}</span>
                  <span className="card-type">{doc.type.replace(/_/g, ' ')}</span>
                </div>
                <div className="card-body">
                  <p className="card-title">{doc.title}</p>
                  <p className="card-date">Created: {formatDate(doc.createdAt)}</p>
                  <button className="view-doc-btn" onClick={() => alert('Document viewer coming soon')}>
                    View Document
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <style>{`
        .dashboard {
          padding: 1.5rem;
          max-width: 1200px;
          margin: 0 auto;
        }

        .dashboard h2 {
          margin: 0 0 1.5rem 0;
          color: var(--ca-text-primary);
        }

        .dashboard-empty {
          background: var(--ca-bg-secondary);
          padding: 2rem;
          border-radius: var(--ca-radius-lg);
          text-align: center;
          color: var(--ca-text-secondary);
        }

        .dashboard-section {
          margin-bottom: 2rem;
        }

        .dashboard-section h3 {
          margin: 0 0 1rem 0;
          color: var(--ca-text-primary);
          font-size: 1.1rem;
        }

        .dashboard-cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 1rem;
        }

        .dashboard-card {
          background: var(--ca-bg-secondary);
          border-radius: var(--ca-radius-md);
          padding: 1rem;
          border: 1px solid var(--ca-border);
        }

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
          padding-bottom: 0.75rem;
          border-bottom: 1px solid var(--ca-border);
        }

        .card-category {
          font-size: 0.85rem;
          color: var(--ca-primary);
          font-weight: 600;
          text-transform: capitalize;
        }

        .urgency-badge, .priority-badge {
          font-size: 0.75rem;
          padding: 0.25rem 0.5rem;
          border-radius: var(--ca-radius-sm);
          font-weight: 600;
        }

        .urgency-high { background: #F87171; color: white; }
        .urgency-medium { background: #FBBF24; color: white; }
        .urgency-low { background: #60A5FA; color: white; }

        .priority-urgent { background: #F87171; color: white; }
        .priority-high { background: #FBBF24; color: white; }
        .priority-medium { background: #60A5FA; color: white; }
        .priority-low { background: var(--ca-bg-tertiary); color: var(--ca-text-secondary); }

        .card-body p {
          margin: 0.5rem 0;
          color: var(--ca-text-secondary);
          font-size: 0.9rem;
        }

        .card-title {
          font-weight: 600;
          color: var(--ca-text-primary) !important;
          font-size: 1rem !important;
        }

        .card-time, .card-due {
          color: var(--ca-text-primary) !important;
          font-weight: 500;
        }

        .card-countdown {
          font-size: 1.1rem;
          font-weight: 600;
          color: var(--ca-primary);
        }

        .card-countdown.urgent {
          color: var(--ca-error);
        }

        .card-type {
          font-size: 0.75rem;
          color: var(--ca-text-muted);
          text-transform: capitalize;
        }

        .view-doc-btn {
          margin-top: 0.75rem;
          padding: 0.5rem 1rem;
          background: var(--ca-primary);
          color: white;
          border: none;
          border-radius: var(--ca-radius-sm);
          cursor: pointer;
          font-size: 0.9rem;
        }

        .view-doc-btn:hover {
          background: var(--ca-primary-hover);
        }

        @media (max-width: 768px) {
          .dashboard-cards {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  )
}

export default Dashboard
