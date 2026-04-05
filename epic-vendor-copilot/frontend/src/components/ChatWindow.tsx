import React, { useState, useRef, useEffect } from 'react';
import { useConversation } from '../hooks/useConversation';
import { MessageBubble } from './MessageBubble';

export function ChatWindow() {
  const { messages, sendMessage, isLoading, clearSession, systemInfo } = useConversation();
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

  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant');
  const tokensUsed = lastAssistantMsg?.tokenBudgetUsed ?? null;

  return (
    <div className="chat-layout">
      <header className="chat-header">
        <div className="header-title-wrapper">
          <h1 className="header-title">Epic Vendor Copilot</h1>
          <span className="mode-badge">
            {systemInfo.mode === 'llm' ? `LLM • ${systemInfo.provider}` : 'Template Mode'}
          </span>
        </div>
        <button onClick={clearSession} className="clear-btn">
          Clear Session
        </button>
      </header>
      
      <div className="chat-body">
        {messages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-svg-wrapper">
              <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>
            <h2>Epic Vendor Services</h2>
            <div className="chip-container">
              {["How do I enroll?", "What sandbox environments exist?", "Where are billing docs?"].map(query => (
                <button 
                  key={query}
                  onClick={() => { setInputText(query); }}
                  className="suggestion-chip"
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
          <div className="typing-indicator">
            <span>●</span>
            <span>●</span>
            <span>●</span>
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      <div className="chat-footer">
        <div className="input-container">
          <textarea 
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask a question..."
            className="chat-input"
          />
          <button 
            onClick={handleSend}
            disabled={isLoading || !inputText.trim()}
            className="send-btn"
          >
            Send
          </button>
        </div>
        {tokensUsed !== null && (
          <div className="token-counter">
            Tokens used for last response: {tokensUsed}
          </div>
        )}
      </div>
    </div>
  );
}
