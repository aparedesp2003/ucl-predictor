"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Marks its subtree ready after the first paint, so `.grow-bar` children grow from zero to their
 * width once (globals.css). With prefers-reduced-motion the bars are drawn at full width at once.
 */
export function GrowOnMount({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => setReady(true));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, []);
  return (
    <div
      className={cn("grow-scope", className)}
      data-ready={ready ? "" : undefined}
    >
      {children}
    </div>
  );
}
