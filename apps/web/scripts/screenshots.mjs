// Full-page screenshots of the main pages at desktop and phone widths.
// Usage: pnpm --filter web screenshots [label]   (dev server must be running; BASE_URL to override)
// Also reports horizontal overflow, and tap targets under 24x24 px at phone widths.
import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "@playwright/test";

const base = process.env.BASE_URL ?? "http://localhost:3000";
const label = process.argv[2] ?? "latest";
const out = path.join(import.meta.dirname, "..", "screenshots", label);
const pages = [
  ["home", "/"],
  ["matches-4", "/matches/4"],
  ["simulator", "/simulator"],
  ["accuracy", "/accuracy"],
  ["about", "/about"],
];
const widths = [1440, 390];

await mkdir(out, { recursive: true });
const browser = await chromium.launch();
const errors = [];
for (const width of widths) {
  const context = await browser.newContext({
    viewport: { width, height: 900 },
    timezoneId: "Europe/Madrid",
  });
  const page = await context.newPage();
  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning")
      errors.push(`${width} ${msg.text()}`);
  });
  for (const [name, route] of pages) {
    await page.goto(base + route, { waitUntil: "networkidle" });
    await page.waitForFunction(
      () => !document.querySelector('[role="status"]'),
    );
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    // WCAG 2.5.8: targets under 24x24 CSS px, except links inside a sentence.
    const small =
      width < 768
        ? await page.evaluate(() =>
            [
              ...document.querySelectorAll(
                'a[href], button, summary, select, input, [role="button"], [tabindex="0"]',
              ),
            ]
              .filter((el) => {
                const r = el.getBoundingClientRect();
                if (r.width <= 1 || r.height <= 1) return false; // hidden (sr-only)
                const inline =
                  getComputedStyle(el).display === "inline" &&
                  el.parentElement?.closest("p, li");
                return !inline && (r.width < 24 || r.height < 24);
              })
              .map((el) => {
                const r = el.getBoundingClientRect();
                const label = (
                  el.getAttribute("aria-label") ||
                  el.textContent ||
                  el.tagName
                )
                  .trim()
                  .slice(0, 40);
                return `${label} (${Math.round(r.width)}x${Math.round(r.height)})`;
              }),
          )
        : [];
    const file = path.join(out, `${name}-${width}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(
      `${file}  horizontal overflow: ${overflow}px` +
        (small.length
          ? `
  small tap targets: ${small.join("; ")}`
          : ""),
    );
  }
  await context.close();
}
await browser.close();
if (errors.length)
  console.log("console errors/warnings:\n" + errors.join("\n"));
