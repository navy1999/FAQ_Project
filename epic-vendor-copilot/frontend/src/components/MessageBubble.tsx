import { Message } from '../types';
import { SourceCard } from './SourceCard';
import { MemoryIndicator } from './MemoryIndicator';

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  
  const isClarification = message.responseType === 'clarification';
  const isDomainMiss = message.responseType === 'domain_miss';
  
  const bubbleClass = `message-bubble ${isUser ? 'user' : 'assistant'} ${isClarification ? 'clarification-border' : ''} ${isDomainMiss ? 'domain-miss' : ''}`;

  return (
    <div className={`message-wrapper ${isUser ? 'user' : 'assistant'}`}>
      <div className={bubbleClass}>
        {message.content}
        {message.streaming && <span className="cursor-blink">|</span>}
      </div>

      {!isUser && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {message.memoryUsed && <MemoryIndicator turnRefs={message.memoryTurnRefs} />}
          {message.source && message.source.id && <SourceCard source={message.source} answerText={message.content} />}
        </div>
      )}
    </div>
  );
}
