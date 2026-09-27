// One quiet line at the end of the page: who made it, and where to report a problem.
const LINK = "underline-offset-4 hover:text-[var(--ink-1)] hover:underline print:underline";

export function CreditFooter() {
  return (
    <footer className="mt-10 flex flex-wrap gap-x-2 gap-y-1 border-t border-[var(--line)] pt-4 text-xs text-[var(--ink-2)] print:mt-4 print:border-0 print:pt-0">
      <span>Tiago Tamagusko</span>
      <span aria-hidden="true">·</span>
      <a href="mailto:tamagusko@gmail.com" className={LINK}>tamagusko@gmail.com</a>
      <span aria-hidden="true">·</span>
      <a href="https://github.com/tamagusko/camina/issues" target="_blank" rel="noopener noreferrer" className={LINK}>
        Report a problem<span className="hidden print:inline">: github.com/tamagusko/camina/issues</span>
      </a>
    </footer>
  );
}
