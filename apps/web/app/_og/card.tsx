// The site's static social card (1200×630), shared by opengraph-image and twitter-image.
// Rendered once at build time: vendored fonts (OFL, licences alongside) for the wordmark and
// tagline, and the outlined Arena mark from lib/brand/marks. No database access.
import { readFile } from "node:fs/promises";
import path from "node:path";

import { cacheLife } from "next/cache";
import { ImageResponse } from "next/og";

import { ARENA_MARK_SVG, svgDataUri } from "@/lib/brand/marks";
import { SITE_TAGLINE, SITE_TITLE } from "@/lib/site";

export const CARD_SIZE = { width: 1200, height: 630 };
export const CARD_ALT = SITE_TITLE;

// Cached so the card is prerendered at build: uncached file reads would make the route dynamic.
async function loadFonts() {
  "use cache";
  cacheLife("max");
  const dir = path.join(process.cwd(), "app", "_og");
  const read = async (file: string) =>
    (await readFile(path.join(dir, file))).toString("base64");
  const [barlow, inter] = await Promise.all([
    read("barlow-condensed-latin-700-normal.woff"),
    read("inter-latin-400-normal.woff"),
  ]);
  return { barlow, inter };
}

export async function renderCard(): Promise<ImageResponse> {
  const fonts = await loadFonts();

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        gap: 64,
        padding: "0 96px",
        backgroundColor: "#070B24",
        color: "#EEF1FF",
        fontFamily: "Inter",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- rendered by Satori, not the browser */}
      <img src={svgDataUri(ARENA_MARK_SVG)} width={360} height={300} alt="" />
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div
          style={{
            fontFamily: "Barlow Condensed",
            fontSize: 168,
            lineHeight: 1,
            letterSpacing: "0.04em",
          }}
        >
          NINETY
        </div>
        <div
          style={{
            fontSize: 36,
            lineHeight: 1.3,
            color: "#C9D1E3",
            maxWidth: 560,
          }}
        >
          {SITE_TAGLINE}
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 12,
            height: 6,
            width: 120,
            backgroundColor: "#7FA2FF",
            borderRadius: 3,
          }}
        />
      </div>
    </div>,
    {
      ...CARD_SIZE,
      fonts: [
        {
          name: "Barlow Condensed",
          data: Buffer.from(fonts.barlow, "base64"),
          weight: 700,
          style: "normal",
        },
        {
          name: "Inter",
          data: Buffer.from(fonts.inter, "base64"),
          weight: 400,
          style: "normal",
        },
      ],
    },
  );
}
