// Quiet flag that the view is backed by mock fixtures rather than live ingest.
// Callers render these only when CAMINA_DATA_SOURCE=mock, so both disappear
// with real data.
const MOCK_SENTENCE = "Mock data: simulated values to demonstrate the dashboard, not actual counts.";

export function MockBadge() {
  return <span title={MOCK_SENTENCE} className="whitespace-nowrap rounded-sm border border-line px-2 py-0.5 text-xs text-ink-2">Mock data</span>;
}

/** The same warning in full, where values are read closely (street page, PDF). */
export function MockNotice() {
  return <p className="text-sm text-[var(--ink-1)]">{MOCK_SENTENCE}</p>;
}
