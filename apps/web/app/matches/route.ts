import { connection } from "next/server";

import { currentMatchday } from "@/lib/data/derive";
import { getSeasonMatches } from "@/lib/data/matches";
import { safely } from "@/lib/data/safe";

// /matches has no page of its own: send visitors to the current (or next) matchday.
export async function GET(request: Request) {
  await connection();
  const matches = (await safely(getSeasonMatches)) ?? [];
  return Response.redirect(
    new URL(`/matches/${currentMatchday(matches)}`, request.url),
    307,
  );
}
