import { useState, useRef, useEffect } from 'react';
import { Message, ResponseType } from '../types';

export function useConversation() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const isLoadingRef = useRef(false);
  const [systemInfo, setSystemInfo] = useState<{ mode: string; provider: string }>({ mode: 'Template', provider: 'none' });
  
  const sessionIdRef = useRef<string>('');
  if (!sessionIdRef.current) {
    sessionIdRef.current = crypto.randomUUID();
  }
  const sessionId = sessionIdRef.current;

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health', { signal: controller.signal })
      .then(r => r.json())
      .then(data => setSystemInfo({ mode: data.mode, provider: data.provider }))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;
    
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      source: null,
      memoryUsed: false,
      memoryTurnRefs: [],
      responseType: "answer",
      timestamp: Date.now()
    };

    const tempId = crypto.randomUUID();
    const assistantMessage: Message = {
      id: tempId,
      role: 'assistant',
      content: '',
      source: null,
      memoryUsed: false,
      memoryTurnRefs: [],
      responseType: "answer",
      timestamp: Date.now(),
      streaming: true
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    isLoadingRef.current = true;
    setIsLoading(true);

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text })
      });

      if (!resp.ok) {
        throw new Error('API error');
      }

      const reader = resp.body?.getReader();
      const decoder = new TextDecoder("utf-8");
      if (!reader) return;

      let currentContent = '';
      let isDone = false;

      while (!isDone) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunkStr = decoder.decode(value, { stream: true });
        const lines = chunkStr.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;
            
            let payload: any;
            try {
              payload = JSON.parse(dataStr);
            } catch (e) {
              continue;
            }

            if (payload.chunk) {
              currentContent += payload.chunk;
              setMessages(prev => 
                prev.map(m => m.id === tempId ? { ...m, content: currentContent } : m)
              );
              if (currentContent.length > 0 && isLoadingRef.current) {
                isLoadingRef.current = false;
                setIsLoading(false);
              }
            } else if (payload.done) {
              isDone = true;
              setMessages(prev => 
                prev.map(m => m.id === tempId ? {
                  ...m,
                  source: payload.source || null,
                  memoryUsed: !!payload.memory_used,
                  memoryTurnRefs: payload.memory_turn_refs || [],
                  responseType: (payload.response_type as ResponseType) || "answer",
                  streaming: false,
                  tokenBudgetUsed: payload.token_budget_used,
                  mode: payload.mode
                } : m)
              );
            }
          }
        }
      }
    } catch (err) {
      setMessages(prev => 
        prev.map(m => m.id === tempId ? {
          ...m, 
          content: "Something went wrong. Please try again.",
          streaming: false
        } : m)
      );
    } finally {
      isLoadingRef.current = false;
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
    clearSession,
    systemInfo
  };
}
