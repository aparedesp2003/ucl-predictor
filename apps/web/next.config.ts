import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // The social card reads its fonts and mark from disk (app/_og/card.tsx); ship them with the
  // function in case the cached card is regenerated at runtime.
  outputFileTracingIncludes: {
    "/opengraph-image": ["./app/_og/*.woff", "./app/icon.svg"],
    "/twitter-image": ["./app/_og/*.woff", "./app/icon.svg"],
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
