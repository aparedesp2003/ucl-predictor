/** Phones only: tells sighted users a wide table scrolls sideways (screen readers navigate it). */
export function ScrollHint() {
  return (
    <p className="mb-2 text-xs text-mist sm:hidden" aria-hidden>
      Swipe the table sideways for more columns.
    </p>
  );
}
