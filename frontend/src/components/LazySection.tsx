"use client";

import { useEffect, useRef, useState } from "react";

/** Mounts its content only when it is about to scroll into view, so long pages open fast. */
export default function LazySection({ id, children, minHeight = 320 }: { id?: string; children: React.ReactNode; minHeight?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || show) return;
    if (typeof IntersectionObserver === "undefined") return setShow(true);
    const io = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && setShow(true), { rootMargin: "400px 0px" });
    io.observe(el);
    // opened via a link to this section (#id): load right away
    if (id && typeof window !== "undefined" && window.location.hash === `#${id}`) setShow(true);
    return () => io.disconnect();
  }, [id, show]);

  return (
    <div id={id} ref={ref} className="scroll-mt-28" style={show ? undefined : { minHeight }}>
      {show ? children : <div className="h-full animate-pulse rounded-xl border border-line bg-panel/50" style={{ minHeight }} />}
    </div>
  );
}
