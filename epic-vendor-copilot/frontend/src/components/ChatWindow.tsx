import React, { useState, useRef, useEffect } from 'react';
import { useConversation } from '../hooks/useConversation';
import { MessageBubble } from './MessageBubble';

export function ChatWindow() {
  const { messages, sendMessage, isLoading, clearSession } = useConversation();
  const [inputText, setInputText] = useState('');
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = () => {
    if (!inputText.trim() || isLoading) return;
    sendMessage(inputText.trim());
    setInputText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header style={{ padding: '16px', background: '#fff', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0, fontSize: '1.2rem', color: '#00567a' }}>Epic Vendor Copilot</h1>
        <button 
          onClick={clearSession} 
          style={{ padding: '8px 12px', background: '#f5f5f5', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer' }}
        >
          Clear
        </button>
      </header>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {messages.length === 0 ? (
          <div style={{ margin: 'auto', textAlign: 'center', color: '#666' }}>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>💬</div>
            <h2>Ask anything about Epic Vendor Services</h2>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginTop: '24px', flexWrap: 'wrap' }}>
              {["What is Vendor Services?", "How do I enroll?", "What APIs does Epic support?"].map(query => (
                <button 
                  key={query}
                  onClick={() => { setInputText(query); }}
                  style={{ padding: '8px 16px', background: '#e0f2fe', color: '#0369a1', border: 'none', borderRadius: '16px', cursor: 'pointer' }}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        
        {isLoading && (
          <div style={{ alignSelf: 'flex-start', background: '#fff', padding: '12px', borderRadius: '8px', boxShadow: '0 1px 2px rgba(0,0,0,0.1)', color: '#666' }}>
            <span style={{ animation: 'pulse 1.5s infinite' }}>●</span>
            <span style={{ animation: 'pulse 1.5s infinite', animationDelay: '0.2s', margin: '0 4px' }}>●</span>
            <span style={{ animation: 'pulse 1.5s infinite', animationDelay: '0.4s' }}>●</span>
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      <div style={{ padding: '16px', background: '#fff', borderTop: '1px solid #ddd' }}>
        <div style={{ display: 'flex', gap: '8px', maxWidth: '800px', margin: '0 auto' }}>
          <textarea 
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Type your message..."
            style={{ flex: 1, padding: '10px', borderRadius: '4px', border: '1px solid #ccc', resize: 'none', height: '44px', fontFamily: 'inherit' }}
          />
          <button 
            onClick={handleSend}
            disabled={isLoading || !inputText.trim()}
            style={{ padding: '0 20px', background: '#00567a', color: '#fff', border: 'none', borderRadius: '4px', cursor: inputText.trim() && !isLoading ? 'pointer' : 'not-allowed', opacity: isLoading || !inputText.trim() ? 0.7 : 1 }}
          >
            Send
          </button>
        </div>
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
        @keyframes blink {
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
