import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MessageBubble } from '../components/MessageBubble'

const mockSource = {
    id: 'vs-001',
    section: 'Sign-In & Account Access',
    question: 'How do I request an account?',
    url: 'https://vendorservices.epic.com/FAQ/Index',
    confidence: 0.91,
}

describe('MessageBubble', () => {
    it('renders user message correctly', () => {
        render(<MessageBubble message={{ role: "user", content: "What is Vendor Services?" } as any} />)
        expect(screen.getByText('What is Vendor Services?')).toBeDefined()
    })

    it('renders assistant message correctly', () => {
        render(<MessageBubble message={{ role: "assistant", content: "Vendor Services is a portal." } as any} />)
        expect(screen.getByText('Vendor Services is a portal.')).toBeDefined()
    })

    it('shows source card when source is provided', () => {
        render(
            <MessageBubble
                message={{
                    role: "assistant",
                    content: "Here is the answer.",
                    source: mockSource
                } as any}
            />
        )
        // Match partial text to ignore the emoji
        expect(screen.getByText(/Sign-In & Account Access/)).toBeDefined()
    })

    it('shows memory indicator when memory_used is true', () => {
        render(
            <MessageBubble
                message={{
                    role: "assistant",
                    content: "Answer using memory.",
                    memoryUsed: true,
                    memoryTurnRefs: [2]
                } as any}
            />
        )
        // MemoryIndicator renders "↩ Memory: turn 3" (2+1)
        // Use a more specific regex to avoid matching the content text "memory"
        expect(screen.getByText(/Memory: turn/i)).toBeDefined()
    })

    it('does not show source card for user messages', () => {
        render(
            <MessageBubble
                message={{
                    role: "user",
                    content: "My question",
                    source: mockSource
                } as any}
            />
        )
        expect(screen.queryByText(/Sign-In & Account Access/)).toBeNull()
    })
})