import { createHash, timingSafeEqual } from "node:crypto";

const digest = (s: string) => createHash("sha256").update(s, "utf8").digest();

/**
 * True when the Authorization header is "Bearer <secret>". Hashing both sides first gives
 * timingSafeEqual equal-length inputs, so neither the token's content nor its length leaks
 * through timing. An unset or empty secret authorises nothing.
 */
export function isAuthorized(
  header: string | null,
  secret: string | undefined,
): boolean {
  if (!secret || !header) return false;
  const match = /^Bearer\s+(\S+)\s*$/i.exec(header);
  if (!match) return false;
  return timingSafeEqual(digest(match[1]), digest(secret));
}
