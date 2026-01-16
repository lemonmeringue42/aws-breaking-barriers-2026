import { useState } from 'react'

interface BookingSlot {
  slot_id: string
  datetime: string
  display: string
  date: string
  time: string
}

interface BookingSlotsProps {
  slots: BookingSlot[]
  onSelect: (slotId: string, display: string) => void
}

export default function BookingSlots({ slots, onSelect }: BookingSlotsProps) {
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)

  // Group slots by date
  const slotsByDate = slots.reduce((acc, slot) => {
    if (!acc[slot.date]) acc[slot.date] = []
    acc[slot.date].push(slot)
    return acc
  }, {} as Record<string, BookingSlot[]>)

  const handleConfirm = () => {
    const slot = slots.find(s => s.slot_id === selectedSlot)
    if (slot) onSelect(slot.slot_id, slot.display)
  }

  return (
    <div className="ca-booking-slots">
      <h4>📅 Select an appointment time</h4>
      
      {Object.entries(slotsByDate).map(([date, dateSlots]) => (
        <div key={date} className="ca-booking-date-group">
          <div className="ca-booking-date-header">
            {new Date(date).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })}
          </div>
          <div className="ca-booking-times">
            {dateSlots.map(slot => (
              <button
                key={slot.slot_id}
                className={`ca-booking-slot ${selectedSlot === slot.slot_id ? 'selected' : ''}`}
                onClick={() => setSelectedSlot(slot.slot_id)}
              >
                {slot.time}
              </button>
            ))}
          </div>
        </div>
      ))}

      {selectedSlot && (
        <button className="ca-booking-confirm" onClick={handleConfirm}>
          Confirm Appointment
        </button>
      )}
    </div>
  )
}
