export const SITE_NAME = "Ninety";

export const SITE_DESCRIPTION =
  "Pre-kick-off probabilities for every Champions League match, and the title race simulated from them.";

/** The brand promise, on the social card. */
export const SITE_TAGLINE =
  "Champions League predictions, locked before kick-off";

export const GITHUB_URL = "https://github.com/aparedesp2003/ucl-predictor";

/** Public origin for metadata, sitemap and robots (no trailing slash). */
export function siteUrl(): string {
  const url = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  return url.replace(/\/+$/, "");
}

export const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/matches", label: "Matches" },
  { href: "/simulator", label: "Simulator" },
  { href: "/accuracy", label: "Accuracy" },
  { href: "/about", label: "About" },
] as const;

export const LEAGUE_MATCHDAYS = 8;

export const SITE_TITLE = `${SITE_NAME} — Champions League predictions`;

/** Root metadata: title template, social card defaults (the card itself is app/opengraph-image). */
export const ROOT_METADATA = {
  title: { default: SITE_TITLE, template: `%s · ${SITE_NAME}` },
  description: SITE_DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE_NAME,
    locale: "en_GB",
    url: "/",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
} as const;

/** A page's title and description, repeated into its Open Graph and Twitter tags and canonical URL. */
export function pageMetadata({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: string;
}) {
  const full = `${title} · ${SITE_NAME}`;
  // A page-level openGraph/twitter object replaces the root one, file-based card included, so
  // the card (app/opengraph-image, app/twitter-image) is referenced again here.
  const card = { width: 1200, height: 630, alt: SITE_TITLE, type: "image/png" };
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      ...ROOT_METADATA.openGraph,
      url: path,
      title: full,
      description,
      images: [{ url: "/opengraph-image", ...card }],
    },
    twitter: {
      ...ROOT_METADATA.twitter,
      title: full,
      description,
      images: [{ url: "/twitter-image", ...card }],
    },
  };
}
