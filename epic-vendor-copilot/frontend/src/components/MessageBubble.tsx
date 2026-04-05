import { Message } from '../types';
import { SourceCard } from './SourceCard';
import { MemoryIndicator } from './MemoryIndicator';

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  const bubbleClass = `message-bubble ${isUser ? 'user' : 'assistant'} ${message.clarificationNeeded ? 'clarification-border' : ''}`;

  return (
    <div className={`message-wrapper ${isUser ? 'user' : 'assistant'}`}>
      <div className={bubbleClass}>
        {message.content}
        {message.streaming && <span className="cursor-blink">|</span>}

        {message.domainRoute && (
          <div className="domain-route-pill">
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
