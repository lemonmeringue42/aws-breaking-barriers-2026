import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface AdviceCard {
  title: string
  icon: string
  items: string[]
}

interface AdvicePackProps {
  content: string
}

const ADVICE_PATTERNS: { pattern: RegExp; title: string; icon: string }[] = [
  { pattern: /energy|bill|payment|arrears|disconnection/i, title: 'Energy & Bills', icon: '⚡' },
  { pattern: /pip|disability|benefit|dwp/i, title: 'Benefits (PIP)', icon: '📋' },
  { pattern: /household support|hsf|council/i, title: 'Household Support Fund', icon: '🏠' },
  { pattern: /debt|money|budget/i, title: 'Debt & Budgeting', icon: '💰' },
  { pattern: /warm home|priority services/i, title: 'Energy Support Schemes', icon: '🔥' },
  { pattern: /food|bank|essentials/i, title: 'Essential Support', icon: '🛒' },
]

export default function AdvicePack({ content }: AdvicePackProps) {
  // Extract bullet points from markdown
  const lines = content.split('\n').filter(l => l.trim())
  const bulletPoints = lines.filter(l => l.match(/^[-*•]\s/))
  
  if (bulletPoints.length < 3) {
    // Not enough structure, render as markdown
    return (
      <div className="ca-advice-pack">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    )
  }

  // Group items into cards
  const cards: AdviceCard[] = []
  const usedItems = new Set<string>()

  for (const { pattern, title, icon } of ADVICE_PATTERNS) {
    const matchingItems = bulletPoints.filter(item => 
      pattern.test(item) && !usedItems.has(item)
    )
    if (matchingItems.length > 0) {
      matchingItems.forEach(item => usedItems.add(item))
      cards.push({ title, icon, items: matchingItems.map(i => i.replace(/^[-*•]\s*/, '')) })
    }
  }

  // Add remaining items to "Other Support"
  const remaining = bulletPoints.filter(item => !usedItems.has(item))
  if (remaining.length > 0) {
    cards.push({ title: 'Additional Support', icon: '📌', items: remaining.map(i => i.replace(/^[-*•]\s*/, '')) })
  }

  if (cards.length === 0) {
    return (
      <div className="ca-advice-pack">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="ca-advice-pack">
      <h4>📦 Your Advice Pack</h4>
      <div className="ca-advice-cards">
        {cards.map((card, i) => (
          <div key={i} className="ca-advice-card">
            <div className="ca-advice-card-header">
              <span className="ca-advice-icon">{card.icon}</span>
              <span className="ca-advice-title">{card.title}</span>
            </div>
            <ul>
              {card.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
