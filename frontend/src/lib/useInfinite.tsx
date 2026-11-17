"use client";

import { useEffect, useRef, useState } from "react";

export const PAGE = 50;

/** Load the next batch when the sentinel element scrolls into view (400px early). */
export function useSentinel(onVisible: () => void, active: boolean) {
  const ref = useRef<HTMLElement | null>(null);
  const cb = useRef(onVisible);
  cb.current = onVisible;
  useEffect(() => {
    const el = ref.current;
    if (!el || !active) return;
    const io = new IntersectionObserver((entries) => entries[0].isIntersecting && cb.current(), { rootMargin: "400px" });
    io.observe(el);
    return () => io.disconnect();
  });
  return ref;
}

type Page<T> = { results: T[]; count: number; has_more: boolean; loading?: { ready: number; total: number } | null };

/** A list paged by the server: 50 rows first, the next 50 when you scroll to the end. `key` changes reset it. */
export function useInfiniteServer<T>(fetchPage: (offset: number) => Promise<Page<T>>, key: string, idOf: (row: T) => string | number) {
  const [rows, setRows] = useState<T[] | null>(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [warming, setWarming] = useState<Page<T>["loading"]>(null);
  const [error, setError] = useState<unknown>(null);
  const req = useRef(0);
  const fetchRef = useRef(fetchPage);
  fetchRef.current = fetchPage;

  useEffect(() => {
    const id = ++req.current;
    setRows(null);
    setError(null);
    const t = setTimeout(() => {
      fetchRef.current(0)
        .then((r) => {
          if (id !== req.current) return;
          setRows(r.results);
          setTotal(r.count);
          setHasMore(r.has_more);
          setWarming(r.loading ?? null);
        })
        .catch((e) => id === req.current && setError(e));
    }, 150);
    return () => clearTimeout(t);
  }, [key]);

  const loadMore = () => {
    if (!rows || !hasMore || loadingMore) return;
    const id = req.current;
    setLoadingMore(true);
    fetchRef.current(rows.length)
      .then((r) => {
        if (id !== req.current) return; // the filters changed meanwhile
        setRows((cur) => {
          const have = new Set((cur ?? []).map(idOf));
          return [...(cur ?? []), ...r.results.filter((x) => !have.has(idOf(x)))];
        });
        setHasMore(r.has_more);
        setTotal(r.count);
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  };
  const sentinel = useSentinel(loadMore, hasMore);
  return { rows, setRows, total, hasMore, loadingMore, loadMore, sentinel, warming, error };
}

/** A list already fetched in full: shows 50, then 50 more each time the end scrolls into view. */
export function useShowMore<T>(items: T[] | null | undefined, resetKey = "") {
  const [n, setN] = useState(PAGE);
  useEffect(() => setN(PAGE), [resetKey]);
  const all = items ?? [];
  const hasMore = all.length > n;
  const more = () => setN((x) => x + PAGE);
  const sentinel = useSentinel(more, hasMore);
  return { visible: all.slice(0, n), total: all.length, hasMore, more, sentinel };
}

/** The row at the end of a table that triggers the next batch (with a button as a fallback). */
export function LoadMoreRow({ sentinel, colSpan, loading, onClick }: {
  sentinel: React.RefObject<HTMLElement | null>; colSpan: number; loading?: boolean; onClick: () => void;
}) {
  return (
    <tr ref={sentinel as React.RefObject<HTMLTableRowElement>}>
      <td colSpan={colSpan} className="px-3 py-4 text-center text-xs text-muted">
        {loading ? "Loading more…" : <button onClick={onClick} className="hover:text-text">Load more</button>}
      </td>
    </tr>
  );
}

/** Same for lists that are not tables. */
export function LoadMoreBlock({ sentinel, loading, onClick }: { sentinel: React.RefObject<HTMLElement | null>; loading?: boolean; onClick: () => void }) {
  return (
    <div ref={sentinel as React.RefObject<HTMLDivElement>} className="py-4 text-center text-xs text-muted">
      {loading ? "Loading more…" : <button onClick={onClick} className="hover:text-text">Load more</button>}
    </div>
  );
}

export function ShowingCount({ shown, total }: { shown: number; total: number }) {
  if (!total) return null;
  return <p className="mt-2 text-right text-xs text-muted">Showing {shown} of {total}</p>;
}
