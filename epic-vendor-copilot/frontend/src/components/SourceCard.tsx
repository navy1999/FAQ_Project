import { SourceInfo } from '../types';

export function SourceCard({ source }: { source: SourceInfo }) {
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
    </div>
  );
}
