import { useState, useEffect } from 'react'

interface AccessibilitySettings {
  highContrast: boolean
  largeText: boolean
  reducedMotion: boolean
}

export default function AccessibilityToggle() {
  const [settings, setSettings] = useState<AccessibilitySettings>(() => {
    const saved = localStorage.getItem('ca-accessibility')
    return saved ? JSON.parse(saved) : { highContrast: false, largeText: false, reducedMotion: false }
  })
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    localStorage.setItem('ca-accessibility', JSON.stringify(settings))
    document.documentElement.classList.toggle('high-contrast', settings.highContrast)
    document.documentElement.classList.toggle('large-text', settings.largeText)
    document.documentElement.classList.toggle('reduced-motion', settings.reducedMotion)
  }, [settings])

  const toggle = (key: keyof AccessibilitySettings) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="ca-accessibility">
      <button 
        onClick={() => setIsOpen(!isOpen)} 
        className="ca-btn ca-btn-ghost"
        aria-label="Accessibility settings"
        aria-expanded={isOpen}
      >
        ♿ Accessibility
      </button>
      
      {isOpen && (
        <div className="ca-accessibility-panel" role="menu">
          <label>
            <input type="checkbox" checked={settings.highContrast} onChange={() => toggle('highContrast')} />
            High Contrast
          </label>
          <label>
            <input type="checkbox" checked={settings.largeText} onChange={() => toggle('largeText')} />
            Larger Text
          </label>
          <label>
            <input type="checkbox" checked={settings.reducedMotion} onChange={() => toggle('reducedMotion')} />
            Reduce Motion
          </label>
        </div>
      )}
    </div>
  )
}
