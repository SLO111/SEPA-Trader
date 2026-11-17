"use client";

import { useEffect, useRef } from "react";

/** While a panel / dialog is open, the phone's Back button (or browser back) closes it instead of leaving the page. */
export function useBackClose(open: boolean, close: () => void) {
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    if (!open) return;
    const tag = `vn-overlay-${Math.random().toString(36).slice(2)}`;
    window.history.pushState({ ...(window.history.state || {}), [tag]: true }, "");
    let viaBack = false;
    const onPop = () => {
      // nested overlays: only the one whose history entry was popped closes
      if (window.history.state && window.history.state[tag]) return;
      viaBack = true;
      closeRef.current();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      // closed with ✕ / outside tap: drop the extra history entry we added
      if (!viaBack && window.history.state && window.history.state[tag]) window.history.back();
    };
  }, [open]);
}
