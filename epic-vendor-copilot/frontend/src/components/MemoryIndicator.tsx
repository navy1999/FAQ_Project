export function MemoryIndicator({ turnRefs }: { turnRefs: number[] }) {
  const earliestTurn = turnRefs.length > 0 ? Math.min(...turnRefs) + 1 : '?';
  return (
    <div 
      className="memory-pill"
      title={`This answer implicitly pulled context from your query in turn ${earliestTurn}`}
    >
      ↩ Memory: turn {earliestTurn}
    </div>
  );
}
