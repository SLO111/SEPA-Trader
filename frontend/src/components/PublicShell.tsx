"use client";

import Link from "next/link";
import AppShell from "@/components/AppShell";
import { LegalFooter } from "@/components/legal/LegalPage";
import Logo from "@/components/Logo";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

/** Pages anyone can open (track record, leaderboard, academy, shared watchlists): the app shell when logged in, a light header otherwise. */
export default function PublicShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const t = useT();
  if (loading) return <div className="h-screen bg-bg" />;
  if (user) return <AppShell>{children}</AppShell>;
  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <Logo />
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/track-record" className="text-muted hover:text-text">{t("Track record")}</Link>
          <Link href="/leaderboard" className="text-muted hover:text-text">{t("Leaderboard")}</Link>
          <Link href="/academy" className="text-muted hover:text-text">{t("Academy")}</Link>
          <Link href="/login" className="text-muted hover:text-text">{t("Log in")}</Link>
          <Link href="/register" className="rounded-md bg-accent px-3 py-1.5 font-medium text-white hover:bg-blue-500">{t("Sign up free")}</Link>
        </nav>
      </header>
      <main className="flex-1">{children}</main>
      <LegalFooter />
    </div>
  );
}
