import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="font-display text-3xl font-semibold">Page not found</h1>
      <p className="mt-3 max-w-prose text-mist">
        This page does not exist yet, or the address is wrong.
      </p>
      <p className="mt-6">
        <Link href="/" className="text-floodlight hover:underline">
          Back to the predictions
        </Link>
      </p>
    </main>
  );
}
