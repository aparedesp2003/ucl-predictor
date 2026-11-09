// The site's static social card (1200×630), shared by opengraph-image and twitter-image.
// Rendered once at build time from vendored fonts (OFL, licences alongside); no database access.
import { readFile } from "node:fs/promises";
import path from "node:path";

import { cacheLife } from "next/cache";
import { ImageResponse } from "next/og";

import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";

export const CARD_SIZE = { width: 1200, height: 630 };
export const CARD_ALT = `${SITE_NAME}: Champions League predictions`;

// Cached so the card is prerendered at build: uncached file reads would make the route dynamic.
async function loadAssets() {
  "use cache";
  cacheLife("max");
  const dir = path.join(process.cwd(), "app");
  const read = async (file: string) =>
    (await readFile(path.join(dir, file))).toString("base64");
  const [fraunces, inter, icon] = await Promise.all([
    read("_og/fraunces-latin-600-normal.woff"),
    read("_og/inter-latin-400-normal.woff"),
    read("icon.svg"),
  ]);
  return { fraunces, inter, icon };
}

export async function renderCard(): Promise<ImageResponse> {
  const assets = await loadAssets();
  const fraunces = Buffer.from(assets.fraunces, "base64");
  const inter = Buffer.from(assets.inter, "base64");
  const mark = `data:image/svg+xml;base64,${assets.icon}`;

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "72px 80px",
        backgroundColor: "#070B24",
        backgroundImage:
          "radial-gradient(circle at 85% 0%, rgba(127,162,255,0.22), rgba(7,11,36,0) 55%)",
        color: "#EEF1FF",
        fontFamily: "Inter",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        {/* eslint-disable-next-line @next/next/no-img-element -- rendered by Satori, not the browser */}
        <img src={mark} width={88} height={88} alt="" />
        <div style={{ fontSize: 36, color: "#A9B3D6" }}>{SITE_NAME}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
        <div
          style={{
            fontFamily: "Fraunces",
            fontSize: 76,
            lineHeight: 1.08,
            letterSpacing: "-0.01em",
            maxWidth: 1000,
          }}
        >
          {`${SITE_NAME} — Champions League predictions`}
        </div>
        <div
          style={{
            fontSize: 32,
            lineHeight: 1.35,
            color: "#A9B3D6",
            maxWidth: 940,
          }}
        >
          {SITE_DESCRIPTION}
        </div>
      </div>
      <div
        style={{
          display: "flex",
          height: 6,
          width: 160,
          backgroundColor: "#7FA2FF",
          borderRadius: 3,
        }}
      />
    </div>,
    {
      ...CARD_SIZE,
      fonts: [
        { name: "Fraunces", data: fraunces, weight: 600, style: "normal" },
        { name: "Inter", data: inter, weight: 400, style: "normal" },
      ],
    },
  );
}
