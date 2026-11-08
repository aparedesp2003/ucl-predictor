"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, SITE_NAME } from "@/lib/site";
import { cn } from "@/lib/utils";

/** A ball of five-pointed stars: an original mark, not any competition's logo. */
function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className="size-7 text-floodlight">
      <circle
        cx="16"
        cy="16"
        r="14.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      {[
        [16, 9.5, 4.2],
        [9.6, 15, 3.2],
        [22.4, 15, 3.2],
        [11.8, 22.4, 3.2],
        [20.2, 22.4, 3.2],
      ].map(([x, y, r]) => (
        <path key={`${x}-${y}`} d={star(x, y, r)} fill="currentColor" />
      ))}
    </svg>
  );
}

function star(cx: number, cy: number, r: number): string {
  const points = Array.from({ length: 10 }, (_, i) => {
    const radius = i % 2 === 0 ? r : r * 0.42;
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    return `${(cx + radius * Math.cos(angle)).toFixed(2)},${(cy + radius * Math.sin(angle)).toFixed(2)}`;
  });
  return `M${points.join("L")}Z`;
}

export function SiteHeader() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/"
      ? pathname === "/"
      : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex min-h-11 items-center gap-2 rounded-sm">
          <Mark />
          <span className="font-display text-xl font-semibold tracking-tight">
            {SITE_NAME}
          </span>
        </Link>
        <nav aria-label="Main" className="-mx-2 flex flex-wrap">
          {NAV_ITEMS.map(({ href, label }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center rounded-sm px-2 text-sm",
                  active
                    ? "font-semibold text-starlight underline decoration-floodlight decoration-2 underline-offset-8"
                    : "text-mist hover:text-starlight",
                )}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
