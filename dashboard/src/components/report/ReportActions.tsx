"use client";
import { useEffect, useRef, useState } from "react";
import { Printer, Share2 } from "lucide-react";
import { formatDublinDateTime } from "@/lib/format-time";
import { shareLinks } from "@/lib/report";

const ICON_BUTTON =
  "inline-flex h-11 w-11 items-center justify-center rounded-full text-[var(--ink-2)] hover:bg-[var(--line)] hover:text-[var(--ink-1)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]";
const MENU_ITEM = "block w-full px-4 py-2.5 text-left text-sm text-[var(--ink-1)] hover:bg-[var(--line)]";

/** Share and print, as two quiet icons. Phones get the system share sheet;
 *  other browsers a small menu (WhatsApp, email, copy link). */
export function ReportActions({ title }: { title: string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menu.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  async function share() {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch {
        // Dismissed by the user.
      }
      return;
    }
    setCopied(false);
    setOpen((o) => !o);
  }

  async function copy() {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setOpen(false), 900);
  }

  const links = open ? shareLinks(title, window.location.href) : null;
  return (
    <div ref={menu} className="relative ml-auto flex items-center print:hidden">
      <button type="button" aria-label="Share" title="Share" aria-expanded={open} onClick={share} className={ICON_BUTTON}>
        <Share2 size={18} aria-hidden="true" />
      </button>
      <button type="button" aria-label="Print or save as PDF" title="Print or save as PDF" onClick={() => window.print()} className={ICON_BUTTON}>
        <Printer size={18} aria-hidden="true" />
      </button>
      {links && (
        <div role="menu" className="absolute right-0 top-12 z-10 w-44 overflow-hidden rounded-[var(--r-sm)] border border-[var(--line)] bg-[var(--surface)] py-1 shadow-[var(--card-shadow)]">
          <a role="menuitem" href={links.whatsapp} target="_blank" rel="noopener noreferrer" className={MENU_ITEM} onClick={() => setOpen(false)}>WhatsApp</a>
          <a role="menuitem" href={links.email} className={MENU_ITEM} onClick={() => setOpen(false)}>Email</a>
          <button role="menuitem" type="button" onClick={copy} className={MENU_ITEM}>{copied ? "Link copied" : "Copy link"}</button>
        </div>
      )}
    </div>
  );
}

/** Printed-only footer: where the report came from and when it was printed. */
export function PrintFooter() {
  const [meta, setMeta] = useState<{ url: string; printed: string } | null>(null);
  useEffect(() => {
    const update = () => setMeta({ url: window.location.href, printed: formatDublinDateTime(Date.now()) });
    update();
    window.addEventListener("beforeprint", update);
    return () => window.removeEventListener("beforeprint", update);
  }, []);
  if (!meta) return null;
  return (
    <footer className="mt-8 hidden border-t border-[var(--line)] pt-3 text-xs text-[var(--ink-2)] print:block">
      Printed {meta.printed} (Dublin time) from <span className="text-[var(--ink-1)]">{meta.url}</span>
    </footer>
  );
}
