import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // The social card reads its fonts from disk (app/_og/card.tsx); ship them with the function in
  // case the cached card is regenerated at runtime.
  outputFileTracingIncludes: {
    "/opengraph-image": ["./app/_og/*.woff"],
    "/twitter-image": ["./app/_og/*.woff"],
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
