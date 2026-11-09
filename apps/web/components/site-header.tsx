"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Wordmark } from "@/components/brand/arena-mark";
import { NAV_ITEMS, SITE_NAME } from "@/lib/site";
import { cn } from "@/lib/utils";

export function SiteHeader() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/"
      ? pathname === "/"
      : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6">
        <Link
          href="/"
          aria-label={`${SITE_NAME} home`}
          className="flex min-h-11 items-center rounded-sm"
        >
          <Wordmark />
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
