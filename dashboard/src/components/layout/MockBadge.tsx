// Quiet flag that the view is backed by mock fixtures rather than live ingest.
// Callers render it only when CAMINA_DATA_SOURCE=mock.
export function MockBadge() {
  return <span className="whitespace-nowrap rounded-sm border border-line px-2 py-0.5 text-xs text-ink-2">Mock data</span>;
}
