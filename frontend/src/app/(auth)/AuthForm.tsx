"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isLogin) await login(email, password);
      else await register(email, password, name);
      router.replace("/chart");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare");
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-accent";

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-panel p-6">
          <h1 className="text-lg font-semibold">{isLogin ? "Intră în cont" : "Creează cont gratuit"}</h1>
          {!isLogin && (
            <label className="block text-sm">
              <span className="mb-1 block text-muted">Nume</span>
              <input value={name} onChange={(e) => setName(e.target.value)} className={field} autoComplete="name" />
            </label>
          )}
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Email</span>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={field} autoComplete="email" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Parolă {!isLogin && "(minim 8 caractere)"}</span>
            <input
              type="password"
              required
              minLength={isLogin ? 1 : 8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={field}
              autoComplete={isLogin ? "current-password" : "new-password"}
            />
          </label>
          {error && <p className="rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
          <button disabled={busy} className="w-full rounded-md bg-accent py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60">
            {busy ? "Se procesează…" : isLogin ? "Intră" : "Creează cont"}
          </button>
          <p className="text-center text-sm text-muted">
            {isLogin ? "Nu ai cont? " : "Ai deja cont? "}
            <Link href={isLogin ? "/register" : "/login"} className="text-accent hover:underline">
              {isLogin ? "Înregistrează-te" : "Intră"}
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
