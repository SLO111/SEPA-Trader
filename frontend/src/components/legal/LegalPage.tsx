import Link from "next/link";
import Logo from "@/components/Logo";

export const LEGAL_UPDATED = "November 2026";

/** Public page layout for the Terms, Privacy and Disclaimer (no login needed). */
export default function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Logo />
          <nav className="flex gap-4 text-sm text-muted">
            <Link href="/terms" className="hover:text-text">Terms</Link>
            <Link href="/privacy" className="hover:text-text">Privacy</Link>
            <Link href="/disclaimer" className="hover:text-text">Disclaimer</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="mt-1 text-sm text-muted">Last updated: {LEGAL_UPDATED}</p>
        <div className="legal mt-6 space-y-4 text-sm leading-relaxed text-text/90 [&_h2]:mt-6 [&_h2]:text-base [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc">
          {children}
        </div>
      </main>
    </div>
  );
}

/** One-line footer for every app page: the legal links. */
export function LegalFooter() {
  return (
    <footer className="hidden flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-1.5 text-[11px] text-muted md:flex">
      <span>© {new Date().getFullYear()} Vnicorn Investments</span>
      <span className="ml-auto flex gap-3">
        <Link href="/terms" className="hover:text-text">Terms</Link>
        <Link href="/privacy" className="hover:text-text">Privacy</Link>
        <Link href="/disclaimer" className="hover:text-text">Risk disclaimer</Link>
      </span>
    </footer>
  );
}
