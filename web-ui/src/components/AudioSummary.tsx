import { useState } from 'react'
import { speak, stopSpeaking } from '../services/novaSonicService'

interface AudioSummaryProps {
  content: string
}

export default function AudioSummary({ content }: AudioSummaryProps) {
  const [isPlaying, setIsPlaying] = useState(false)

  const handlePlay = () => {
    if (isPlaying) {
      stopSpeaking()
      setIsPlaying(false)
    } else {
      // Clean markdown for speech
      const cleanText = content
        .replace(/[#*_`~\[\]()]/g, '')
        .replace(/\n+/g, '. ')
        .replace(/[-•]\s*/g, '')
        .trim()
      
      speak(cleanText)
      setIsPlaying(true)
      
      // Reset after estimated duration (rough: 150 words/min)
      const words = cleanText.split(' ').length
      const duration = (words / 150) * 60 * 1000
      setTimeout(() => setIsPlaying(false), duration)
    }
  }

  return (
    <button 
      onClick={handlePlay} 
      className="ca-audio-summary-btn"
      aria-label={isPlaying ? 'Stop audio summary' : 'Play audio summary'}
    >
      {isPlaying ? '⏹️ Stop' : '🔊 Listen'}
    </button>
  )
}
