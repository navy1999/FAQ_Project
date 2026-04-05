import { useState, useRef } from 'react';
import { Message } from '../types';

export function useConversation() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const sessionIdRef = useRef<string>('');
  if (!sessionIdRef.current) {
    sessionIdRef.current = crypto.randomUUID();
  }
  const sessionId = sessionIdRef.current;

  const sendMessage = async (text: string) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      source: null,
      memoryUsed: false,
      memoryTurnRefs: [],
      domainRoute: null,
      clarificationNeeded: false,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text })
      });

      if (!resp.ok) {
        throw new Error('API error');
      }

      const data = await resp.json();
      
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.answer || '',
        source: data.source || null,
        memoryUsed: !!data.memory_used,
        memoryTurnRefs: data.memory_turn_refs || [],
        domainRoute: data.domain_route || null,
        clarificationNeeded: !!data.clarification_needed,
        timestamp: Date.now()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: "Something went wrong. Please try again.",
        source: null,
        memoryUsed: false,
        memoryTurnRefs: [],
        domainRoute: null,
        clarificationNeeded: false,
        timestamp: Date.now()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearSession = async () => {
    try {
      await fetch(`/api/session/${sessionId}`, { method: 'DELETE' });
    } catch(e) {
      // ignore
    }
    setMessages([]);
  };

  return {
    messages,
    sendMessage,
    isLoading,
    sessionId,
    clearSession
  };
}
