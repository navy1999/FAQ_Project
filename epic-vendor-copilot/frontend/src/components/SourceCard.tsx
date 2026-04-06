import { useState } from 'react';
import { SourceInfo } from '../types';

export function SourceCard({ source, answerText }: { source: SourceInfo; answerText?: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const displayConf = source.confidence !== null && source.confidence !== undefined;
  const isRouted = source.confidence === null;
  const confidencePercent = displayConf ? `${Math.round(source.confidence! * 100)}%` : null;

  let confColor = '#999';
  if (displayConf) {
    if (source.confidence! >= 0.75) confColor = '#2e7d32'; // green
    else if (source.confidence! >= 0.55) confColor = '#f57c00'; // amber
    else confColor = '#c62828'; // red
  }

  const truncate = (text: string, len: number) => {
    if (!text) return '';
    return text.length > len ? text.slice(0, len) + '…' : text;
  };

  const hasSource = source.id !== null && source.id !== undefined;

  return (
    <div className="source-card">
      <div className="source-header">
        <strong className="source-section">📄 {source.section || 'General'}</strong>
        <span 
          className="confidence-badge"
          style={{ 
            color: confColor,
            borderColor: `${confColor}40`,
            backgroundColor: `${confColor}10`
          }}
        >
          {isRouted ? 'Routed' : `Confidence: ${confidencePercent}`}
        </span>
      </div>
      
      {source.question && (
        <div className="source-question">
          "{truncate(source.question, 60)}"
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
        {source.url && (
          <a 
            href={source.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="source-link"
          >
            ● {source.url.replace(/^https?:\/\//, '').split('/')[0]}...
          </a>
        )}

        {hasSource && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setIsExpanded(!isExpanded); }}}
            className="source-peek-btn"
            aria-expanded={isExpanded}
          >
            {isExpanded ? 'Hide source ▲' : 'View source ▼'}
          </button>
        )}
      </div>

      {isExpanded && hasSource && (
        <div className="source-peek-panel">
          {source.question && (
            <h4 className="source-peek-heading">{source.question}</h4>
          )}
          <p className="source-peek-text">
            {answerText || 'Full answer text not available in this view.'}
          </p>
        </div>
      )}
    </div>
  );
}
