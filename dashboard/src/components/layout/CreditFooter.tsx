// Who made it, and where to report a problem: one quiet line at the end of the
// street page, and a short credit beside the map's own attribution.
const AUTHOR = "Tiago Tamagusko";
const EMAIL = "tamagusko@gmail.com";
const ISSUES_URL = "https://github.com/tamagusko/camina/issues";
const LINK = "underline-offset-4 hover:text-[var(--ink-1)] hover:underline print:underline";

export function CreditFooter() {
  return (
    <footer className="mt-10 flex flex-wrap gap-x-2 gap-y-1 border-t border-[var(--line)] pt-4 text-xs text-[var(--ink-2)] print:mt-4 print:border-0 print:pt-0">
      <span>{AUTHOR}</span>
      <span aria-hidden="true">·</span>
      <a href={`mailto:${EMAIL}`} className={LINK}>{EMAIL}</a>
      <span aria-hidden="true">·</span>
      <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer" className={LINK}>
        Report a problem<span className="hidden print:inline">: github.com/tamagusko/camina/issues</span>
      </a>
    </footer>
  );
}

/** The map credit, as HTML for MapLibre's attribution control (desktop). */
export const MAP_CREDIT_HTML = `<a href="mailto:${EMAIL}">${AUTHOR}</a> · <a href="${ISSUES_URL}" target="_blank" rel="noopener noreferrer">Report a problem</a>`;

/** The same credit for the phone sheet, where the attribution is a text line. */
export function MapCredit() {
  return (
    <>
      <a href={`mailto:${EMAIL}`}>{AUTHOR}</a> · <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer">Report a problem</a>
    </>
  );
}
