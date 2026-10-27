import { sql } from "drizzle-orm";
import { connection } from "next/server";

import { getDb } from "@/lib/db";

export async function GET() {
  // Opt out of prerendering: this must hit the database on every request.
  await connection();
  try {
    await getDb().execute(sql`select 1`);
    return Response.json({ status: "ok" });
  } catch (error) {
    console.error("health check failed", error);
    return Response.json({ status: "error" }, { status: 503 });
  }
}
