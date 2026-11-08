import { Lock } from "lucide-react";

/** The match has kicked off, so its prediction can no longer change. */
export function LockedChip() {
  return (
    <span
      title="Kicked off: this prediction is final"
      className="inline-flex items-center gap-1 rounded-sm border border-line px-1.5 py-0.5 text-xs text-mist"
    >
      <Lock aria-hidden className="size-3" strokeWidth={2} />
      Locked
    </span>
  );
}
