import '@testing-library/jest-dom'

// Mock crypto.randomUUID for JSDOM
if (!globalThis.crypto) {
  (globalThis as any).crypto = {
    randomUUID: () => 'test-uuid-' + Math.random().toString(36).substring(2, 9)
  };
} else if (!globalThis.crypto.randomUUID) {
  (globalThis.crypto as any).randomUUID = () => 'test-uuid-' + Math.random().toString(36).substring(2, 9);
}
