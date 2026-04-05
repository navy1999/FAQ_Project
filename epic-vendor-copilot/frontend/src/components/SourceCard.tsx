import { SourceInfo } from '../types';

export function SourceCard({ source }: { source: SourceInfo }) {
  const displayConf = source.confidence !== null && source.confidence !== undefined;
  const isRouted = source.confidence === null;
  const confidencePercent = displayConf ? `${Math.round(source.confidence! * 100)}%` : null;

  let confColor = '#999';
  if (displayConf) {
    if (source.confidence! >= 0.75) confColor = '#2e7d32'; // green
    else if (source.confidence! >= 0.55) confColor = '#f57c00'; // amber
  }

  const truncate = (text: string, len: number) => {
    if (!text) return '';
    return text.length > len ? text.slice(0, len) + '…' : text;
  };

  return (
    <div style={{
      background: '#fafafa',
      border: '1px solid #eaeaea',
      borderRadius: '6px',
      padding: '10px 14px',
      fontSize: '0.9rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <strong style={{ color: '#555' }}>{source.section || 'General'}</strong>
        <span style={{ 
          color: confColor,
          fontWeight: 'bold',
          fontSize: '0.8rem',
          background: '#fff',
          padding: '2px 6px',
          borderRadius: '4px',
          border: `1px solid ${confColor}40`
        }}>
          {isRouted ? 'Routed' : confidencePercent}
        </span>
      </div>
      
      {source.question && (
        <div style={{ color: '#333', fontStyle: 'italic' }}>
          "{truncate(source.question, 60)}"
        </div>
      )}

      {source.url && (
        <a 
          href={source.url} 
          target="_blank" 
          rel="noopener noreferrer"
          style={{
            fontSize: '0.85rem',
            color: '#0277bd',
            textDecoration: 'none',
            marginTop: '4px',
            display: 'inline-block'
          }}
        >
          View Source →
        </a>
      )}
    </div>
  );
}
