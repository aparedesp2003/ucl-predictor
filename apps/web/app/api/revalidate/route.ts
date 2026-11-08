import "@/lib/env";

import { revalidateTag } from "next/cache";

import { CACHE_TAGS } from "@/lib/data/tags";
import { isAuthorized } from "@/lib/revalidate-auth";

/**
 * Called by the matchday pipeline after a run that changed data:
 *   POST /api/revalidate   Authorization: Bearer <REVALIDATE_SECRET>
 * Expires every cache tag at once ({ expire: 0 }: updateTag only works in Server Actions), so the
 * next visit to each page reads fresh data. Only POST is exported; other methods get 405.
 */
export async function POST(request: Request) {
  if (
    !isAuthorized(
      request.headers.get("authorization"),
      process.env.REVALIDATE_SECRET,
    )
  ) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  for (const tag of CACHE_TAGS) revalidateTag(tag, { expire: 0 });
  return Response.json({ revalidated: CACHE_TAGS, now: Date.now() });
}
