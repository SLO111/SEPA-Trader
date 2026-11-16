const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "sepa_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  cache.clear(); // another user signs in or out: never show their cached data
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Short-lived memory cache for GET requests that change slowly, so moving between pages is instant.
// Any write (POST / PUT / PATCH / DELETE) clears it, so you never see stale data after an action.
const CACHE_TTL: [string, number][] = [
  ["/api/strategies", 3600_000],
  ["/api/markets/screener/presets", 3600_000],
  ["/api/markets/overview", 60_000],
  ["/api/markets/", 120_000],
  ["/api/feed/summary", 300_000],
  ["/api/ideas", 60_000],
  ["/api/stock/", 120_000],
  ["/api/sepa/", 120_000],
  ["/api/watchlists", 30_000],
];
const cache = new Map<string, { at: number; data: unknown }>();
const inflight = new Map<string, Promise<unknown>>();

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET") {
    cache.clear();
    return request<T>(path, init);
  }
  const ttl = CACHE_TTL.find(([p]) => path.startsWith(p))?.[1];
  if (!ttl) return request<T>(path, init);
  const hit = cache.get(path);
  if (hit && Date.now() - hit.at < ttl) return hit.data as T;
  const pending = inflight.get(path);
  if (pending) return pending as Promise<T>; // the same request is already on its way
  const p = request<T>(path, init)
    .then((data) => {
      cache.set(path, { at: Date.now(), data });
      return data;
    })
    .finally(() => inflight.delete(path));
  inflight.set(path, p);
  return p;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "The server is not responding. Make sure the backend is running (see README).");
  }
  if (res.status === 401 && token && !path.startsWith("/api/auth/")) {
    // Session expired or the server's secret changed: sign out and go to the login page.
    setToken(null);
    // Public pages (the landing page, login, register) never bounce to the login screen: only the app's own pages do.
    const here = typeof window !== "undefined" ? window.location.pathname : "/";
    const isPublic = here === "/" || here.startsWith("/login") || here.startsWith("/register");
    if (!isPublic && !path.startsWith("/api/auth/me")) window.location.href = "/login";
    throw new ApiError(401, "Your session has expired. Please log in again.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? `Invalid data: ${data.detail[0]?.msg ?? "check the fields"}` : `Server error ${res.status}. Please try again.`;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const post = <T>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });
export const put = <T>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });

/** Download an authenticated file (e.g. a PDF report) and save it with the server-provided name. */
export async function download(path: string, fallbackName: string) {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof data.detail === "string" ? data.detail : "Download failed");
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
