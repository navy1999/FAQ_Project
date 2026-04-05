import { Message } from '../types';
import { SourceCard } from './SourceCard';
import { MemoryIndicator } from './MemoryIndicator';

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div style={{
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      maxWidth: '80%',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      <div style={{
        background: isUser ? '#008080' : '#ffffff',
        color: isUser ? '#ffffff' : '#333333',
        padding: '12px 16px',
        borderRadius: '8px',
        boxShadow: isUser ? 'none' : '0 1px 3px rgba(0,0,0,0.1)',
        borderLeft: message.clarificationNeeded ? '4px solid #ffb300' : 'none',
        whiteSpace: 'pre-wrap',
        lineHeight: '1.5'
      }}>
        {message.content}
        {message.streaming && <span style={{ animation: 'blink 1s step-end infinite' }}>|</span>}

        {message.domainRoute && (
          <div style={{
            display: 'inline-block',
            marginTop: '8px',
            padding: '4px 8px',
            background: '#e0e0e0',
            color: '#555',
            fontSize: '0.8rem',
            borderRadius: '12px',
          }}>
            🔀 {message.domainRoute}
          </div>
        )}
      </div>

      {!isUser && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {message.memoryUsed && <MemoryIndicator turnRefs={message.memoryTurnRefs} />}
          {message.source && message.source.id && <SourceCard source={message.source} />}
        </div>
      )}
    </div>
  );
}
