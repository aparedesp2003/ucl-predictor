import { describe, expect, it } from "vitest";

import { pageMetadata } from "./site";

describe("pageMetadata", () => {
  const m = pageMetadata({
    title: "Accuracy",
    description: "D",
    path: "/accuracy",
  });

  it("repeats title, description and URL into the social tags", () => {
    expect(m.alternates.canonical).toBe("/accuracy");
    expect(m.openGraph).toMatchObject({
      title: "Accuracy · Matchcast",
      description: "D",
      url: "/accuracy",
    });
    expect(m.twitter).toMatchObject({
      card: "summary_large_image",
      title: "Accuracy · Matchcast",
    });
  });

  it("keeps the social card, which a page-level openGraph would otherwise drop", () => {
    expect(m.openGraph.images[0]).toMatchObject({
      url: "/opengraph-image",
      width: 1200,
      height: 630,
    });
    expect(m.twitter.images[0]).toMatchObject({ url: "/twitter-image" });
  });
});
