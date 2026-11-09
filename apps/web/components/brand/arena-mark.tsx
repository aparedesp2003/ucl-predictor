import { cn } from "@/lib/utils";

// The Ninety "Arena" mark: stadium bowl, floodlights, 90' on the stand. The numbers are <text> in
// the loaded Barlow Condensed (next/font hashes the family name, hence the CSS variable); the
// favicon, apple-icon and social card use the outlined copies in lib/brand/marks.ts.
const SCORE_FONT = { fontFamily: "var(--font-score)" };

/** Full mark. */
export function ArenaMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 100"
      role="img"
      aria-label="Ninety logo"
      className={className}
    >
      <path
        d="M12 50 V14 M108 50 V14"
        stroke="#C9D1E3"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <rect x="6" y="8" width="12" height="8" rx="2" fill="#7FA2FF" />
      <rect x="102" y="8" width="12" height="8" rx="2" fill="#7FA2FF" />
      <ellipse
        cx="60"
        cy="50"
        rx="50"
        ry="18"
        fill="#070B24"
        stroke="#EEF1FF"
        strokeWidth="3.5"
      />
      <ellipse
        cx="60"
        cy="50"
        rx="32"
        ry="10"
        fill="#1E3A8A"
        stroke="#7FA2FF"
        strokeWidth="2"
      />
      <path d="M60 40 V60" stroke="#7FA2FF" strokeWidth="1.5" />
      <path
        d="M10 50 L16 80 Q60 96 104 80 L110 50"
        fill="#070B24"
        stroke="#EEF1FF"
        strokeWidth="3.5"
        strokeLinejoin="round"
      />
      <text
        x="60"
        y="84"
        textAnchor="middle"
        fontSize="24"
        fontWeight="700"
        fill="#FFFFFF"
        style={SCORE_FONT}
      >
        90&apos;
      </text>
    </svg>
  );
}

/** Small mark (header and footer lockups): no floodlights, thicker strokes. Decorative. */
export function ArenaMarkSmall({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 100" aria-hidden className={className}>
      <ellipse
        cx="60"
        cy="50"
        rx="50"
        ry="18"
        fill="#070B24"
        stroke="#EEF1FF"
        strokeWidth="9"
      />
      <path
        d="M10 50 L16 80 Q60 96 104 80 L110 50"
        fill="#070B24"
        stroke="#EEF1FF"
        strokeWidth="9"
        strokeLinejoin="round"
      />
      <text
        x="60"
        y="88"
        textAnchor="middle"
        fontSize="34"
        fontWeight="700"
        fill="#7FA2FF"
        style={SCORE_FONT}
      >
        90
      </text>
    </svg>
  );
}

/** Small mark + NINETY, as in the header. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <ArenaMarkSmall className="h-[30px] w-9 shrink-0" />
      <span className="font-score text-2xl leading-none font-bold tracking-[0.04em] uppercase">
        Ninety
      </span>
    </span>
  );
}
