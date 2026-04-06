// frontend/src/__tests__/useConversation.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useConversation } from '../hooks/useConversation'

// Mock fetch globally
const mockFetch = vi.fn()
globalThis.fetch = mockFetch as any

describe('useConversation', () => {
    beforeEach(() => {
        mockFetch.mockReset()
        // Provide a default resolution for the /api/health useEffect call
        mockFetch.mockImplementation(async (url: string) => {
            if (url === '/api/health') {
                return {
                    ok: true,
                    json: async () => ({ mode: 'Template', provider: 'none' })
                }
            }
            return { ok: true, json: async () => ({}) }
        })
    })

    it('initializes with empty messages', () => {
        const { result } = renderHook(() => useConversation())
        expect(result.current.messages).toEqual([])
    })

    it('adds user message immediately on send', async () => {
        mockFetch.mockImplementation(async (url: string) => {
            if (url === '/api/health') return { ok: true, json: async () => ({}) }
            
            // Return stream mock for chat
            return {
                ok: true,
                body: {
                    getReader: () => {
                        let called = false;
                        return {
                            read: async () => {
                                if (called) return { done: true };
                                called = true;
                                const enc = new TextEncoder();
                                return {
                                    done: false,
                                    value: enc.encode('data: {"chunk": "Test answer"}\n\ndata: {"done": true, "mode": "template"}\n\n')
                                }
                            }
                        }
                    }
                }
            }
        })

        const { result } = renderHook(() => useConversation())
        await act(async () => {
            await result.current.sendMessage('What is Vendor Services?')
        })

        expect(result.current.messages[0].role).toBe('user')
        expect(result.current.messages[0].content).toBe('What is Vendor Services?')
    })

    it('adds assistant message after successful response', async () => {
        mockFetch.mockImplementation(async (url: string) => {
            if (url === '/api/health') return { ok: true, json: async () => ({}) }
            
            // Return stream mock for chat
            return {
                ok: true,
                body: {
                    getReader: () => {
                        let called = false;
                        return {
                            read: async () => {
                                if (called) return { done: true };
                                called = true;
                                const enc = new TextEncoder();
                                return {
                                    done: false,
                                    value: enc.encode('data: {"chunk": "Vendor Services is a portal by Epic."}\n\ndata: {"done": true, "mode": "template", "source": {"id": "vs-001", "section": "General", "question": "Q", "url": "http://x", "confidence": 0.9}}\n\n')
                                }
                            }
                        }
                    }
                }
            }
        })

        const { result } = renderHook(() => useConversation())
        await act(async () => {
            await result.current.sendMessage('What is Vendor Services?')
        })

        expect(result.current.messages[1].role).toBe('assistant')
        expect(result.current.messages[1].content).toBe('Vendor Services is a portal by Epic.')
    })

    it('shows error message on network failure', async () => {
        mockFetch.mockImplementation(async (url: string) => {
            if (url === '/api/health') return { ok: true, json: async () => ({}) }
            throw new Error('Network error');
        })

        const { result } = renderHook(() => useConversation())
        await act(async () => {
            await result.current.sendMessage('test')
        })

        expect(result.current.messages[1].role).toBe('assistant')
        expect(result.current.messages[1].content).toBe('Something went wrong. Please try again.')
    })

    it('rejects empty message without calling fetch', async () => {
        const { result } = renderHook(() => useConversation())
        await act(async () => {
            await result.current.sendMessage('   ')
        })

        // Check it was only called for health check
        expect(mockFetch).not.toHaveBeenCalledWith(expect.stringContaining('/api/chat'), expect.anything())
        expect(result.current.messages).toHaveLength(0)
    })
})