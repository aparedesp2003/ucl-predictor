import type { MetadataRoute } from "next";

import { LEAGUE_MATCHDAYS, siteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteUrl();
  const matchdays = Array.from(
    { length: LEAGUE_MATCHDAYS },
    (_, i) => `/matches/${i + 1}`,
  );
  return [
    { url: `${base}/`, changeFrequency: "daily", priority: 1 },
    ...matchdays.map((path) => ({
      url: `${base}${path}`,
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
    { url: `${base}/simulator`, changeFrequency: "daily", priority: 0.8 },
    { url: `${base}/accuracy`, changeFrequency: "daily", priority: 0.7 },
    { url: `${base}/about`, changeFrequency: "monthly", priority: 0.5 },
  ];
}
