// Screenshots for the repo-root README: home, matches, simulator and accuracy at desktop (1440) and
// phone (390) widths, from the live site by default, written to docs/screenshots/ as compressed PNG.
// Usage: pnpm --filter web screenshots:readme   (BASE_URL to capture another deployment)
import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "@playwright/test";
import sharp from "sharp";

const base = process.env.BASE_URL ?? "https://ucl-predictor-red.vercel.app";
const out = path.join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "docs",
  "screenshots",
);
const pages = [
  ["home", "/"],
  ["matches", "/matches"],
  ["simulator", "/simulator"],
  ["accuracy", "/accuracy"],
];
// The first screen of each page, not the full scroll: that is what a README reader takes in.
const viewports = [
  { width: 1440, height: 900, deviceScaleFactor: 1 },
  { width: 390, height: 844, deviceScaleFactor: 2 },
];

await mkdir(out, { recursive: true });
const browser = await chromium.launch();
for (const viewport of viewports) {
  const { deviceScaleFactor, ...size } = viewport;
  const context = await browser.newContext({
    viewport: size,
    deviceScaleFactor,
    timezoneId: "Europe/Madrid",
    colorScheme: "dark",
  });
  const page = await context.newPage();
  for (const [name, route] of pages) {
    await page.goto(base + route, { waitUntil: "networkidle" });
    await page.waitForFunction(
      () => !document.querySelector('[role="status"]'),
    );
    const raw = await page.screenshot();
    const file = path.join(out, `${name}-${size.width}.png`);
    const info = await sharp(raw)
      .png({ palette: true, quality: 90, effort: 10, compressionLevel: 9 })
      .toFile(file);
    console.log(
      `${file}  ${info.width}x${info.height}  ${Math.round(info.size / 1024)} KB`,
    );
  }
  await context.close();
}
await browser.close();
