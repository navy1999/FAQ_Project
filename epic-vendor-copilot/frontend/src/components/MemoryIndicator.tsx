export function MemoryIndicator({ turnRefs }: { turnRefs: number[] }) {
  const earliestTurn = turnRefs.length > 0 ? Math.min(...turnRefs) + 1 : '?';
  return (
    <div 
      title="This answer references context from earlier in the conversation."
      style={{
        display: 'inline-block',
        background: '#e0f2f1',
        color: '#00695c',
        padding: '4px 10px',
        borderRadius: '12px',
        fontSize: '0.85rem',
        fontWeight: '500',
        alignSelf: 'flex-start',
        cursor: 'help'
      }}
    >
      ↩ Memory: turn {earliestTurn}
    </div>
  );
}
