import { useState } from 'react';

interface LetterPreviewProps {
  content: string;
}

export function LetterPreview({ content }: LetterPreviewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="letter-preview">
      <div className="letter-preview-header">
        <span>📄 Your Letter</span>
        <button onClick={handleCopy} className="copy-button">
          {copied ? '✓ Copied!' : '📋 Copy'}
        </button>
      </div>
      <pre className="letter-content">{content}</pre>
    </div>
  );
}
