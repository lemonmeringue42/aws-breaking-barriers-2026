import { useState } from 'react'

interface AppointmentBookingProps {
  slots: Array<{
    datetime: string
    bureau_id: string
    available: boolean
    priority_slot: boolean
  }>
  urgencyScore: number
  category: string
  caseNotes: string
  onBook: (slot: string, phoneNumber: string) => void
  onCancel: () => void
}

const AppointmentBooking = ({ slots, urgencyScore, category, caseNotes, onBook, onCancel }: AppointmentBookingProps) => {
  const [selectedSlot, setSelectedSlot] = useState<string>('')
  const [phoneNumber, setPhoneNumber] = useState('')

  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString)
    return {
      date: date.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }),
      time: date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
    }
  }

  const handleBook = () => {
    if (selectedSlot && phoneNumber) {
      onBook(selectedSlot, phoneNumber)
    }
  }

  const urgencyLabel = urgencyScore >= 8 ? 'URGENT' : urgencyScore >= 5 ? 'Medium Priority' : 'Standard'
  const urgencyColor = urgencyScore >= 8 ? '#F87171' : urgencyScore >= 5 ? '#FBBF24' : '#60A5FA'

  return (
    <div className="appointment-booking">
      <div className="appointment-header">
        <h3>Book Phone Appointment</h3>
        <span className="urgency-badge" style={{ background: urgencyColor }}>
          {urgencyLabel} (Score: {urgencyScore}/10)
        </span>
      </div>

      <div className="appointment-info">
        <p><strong>Category:</strong> {category}</p>
        {caseNotes && <p><strong>Case Summary:</strong> {caseNotes}</p>}
      </div>

      <div className="appointment-slots">
        <h4>Available Slots {urgencyScore >= 8 && '(Priority slots shown first)'}</h4>
        <div className="slots-grid">
          {slots.slice(0, 12).map((slot, idx) => {
            const { date, time } = formatDateTime(slot.datetime)
            return (
              <button
                key={idx}
                className={`slot-btn ${selectedSlot === slot.datetime ? 'selected' : ''} ${slot.priority_slot ? 'priority' : ''}`}
                onClick={() => setSelectedSlot(slot.datetime)}
              >
                {slot.priority_slot && <span className="priority-star">⭐</span>}
                <div className="slot-date">{date}</div>
                <div className="slot-time">{time}</div>
              </button>
            )
          })}
        </div>
      </div>

      <div className="appointment-contact">
        <label htmlFor="phone">Your Phone Number</label>
        <input
          id="phone"
          type="tel"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          placeholder="07XXX XXXXXX"
          className="phone-input"
        />
        <p className="help-text">An advisor will call you at this number</p>
      </div>

      <div className="appointment-actions">
        <button onClick={onCancel} className="ca-btn ca-btn-outline">Cancel</button>
        <button 
          onClick={handleBook} 
          disabled={!selectedSlot || !phoneNumber}
          className="ca-btn ca-btn-primary"
        >
          Confirm Booking
        </button>
      </div>

      <style>{`
        .appointment-booking {
          background: var(--ca-bg-secondary);
          border-radius: var(--ca-radius-lg);
          padding: 1.5rem;
          margin: 1rem 0;
        }

        .appointment-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }

        .appointment-header h3 {
          margin: 0;
          color: var(--ca-text-primary);
        }

        .urgency-badge {
          padding: 0.25rem 0.75rem;
          border-radius: var(--ca-radius-sm);
          font-size: 0.85rem;
          font-weight: 600;
          color: white;
        }

        .appointment-info {
          background: var(--ca-bg-tertiary);
          padding: 1rem;
          border-radius: var(--ca-radius-sm);
          margin-bottom: 1.5rem;
        }

        .appointment-info p {
          margin: 0.5rem 0;
          color: var(--ca-text-secondary);
        }

        .appointment-slots h4 {
          margin: 0 0 1rem 0;
          color: var(--ca-text-primary);
          font-size: 0.95rem;
        }

        .slots-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
          gap: 0.75rem;
          margin-bottom: 1.5rem;
        }

        .slot-btn {
          background: var(--ca-bg-tertiary);
          border: 2px solid var(--ca-border);
          border-radius: var(--ca-radius-sm);
          padding: 0.75rem;
          cursor: pointer;
          transition: all 0.2s;
          position: relative;
        }

        .slot-btn:hover {
          border-color: var(--ca-primary);
          background: var(--ca-bg-elevated);
        }

        .slot-btn.selected {
          border-color: var(--ca-primary);
          background: var(--ca-primary);
        }

        .slot-btn.selected .slot-date,
        .slot-btn.selected .slot-time {
          color: white;
        }

        .slot-btn.priority {
          border-color: var(--ca-accent);
        }

        .priority-star {
          position: absolute;
          top: 4px;
          right: 4px;
          font-size: 0.75rem;
        }

        .slot-date {
          font-size: 0.85rem;
          color: var(--ca-text-secondary);
          margin-bottom: 0.25rem;
        }

        .slot-time {
          font-size: 1rem;
          font-weight: 600;
          color: var(--ca-text-primary);
        }

        .appointment-contact {
          margin-bottom: 1.5rem;
        }

        .appointment-contact label {
          display: block;
          margin-bottom: 0.5rem;
          color: var(--ca-text-primary);
          font-weight: 500;
        }

        .phone-input {
          width: 100%;
          padding: 0.75rem;
          background: var(--ca-bg-tertiary);
          border: 1px solid var(--ca-border);
          border-radius: var(--ca-radius-sm);
          color: var(--ca-text-primary);
          font-size: 1rem;
        }

        .phone-input:focus {
          outline: none;
          border-color: var(--ca-primary);
        }

        .help-text {
          margin: 0.5rem 0 0 0;
          font-size: 0.85rem;
          color: var(--ca-text-muted);
        }

        .appointment-actions {
          display: flex;
          gap: 1rem;
          justify-content: flex-end;
        }

        .ca-btn-primary {
          background: var(--ca-primary);
          color: white;
        }

        .ca-btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  )
}

export default AppointmentBooking
