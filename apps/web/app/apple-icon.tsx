import { ImageResponse } from "next/og";

import { ARENA_MARK_SMALL_SVG, svgDataUri } from "@/lib/brand/marks";

// iOS home-screen icon: the small Arena mark (outlined numbers, no web font) centred on night.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#070B24",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- rendered by Satori, not the browser */}
      <img
        src={svgDataUri(ARENA_MARK_SMALL_SVG)}
        width={132}
        height={110}
        alt=""
      />
    </div>,
    size,
  );
}
