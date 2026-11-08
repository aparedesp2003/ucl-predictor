import { describe, expect, it } from "vitest";

import { isAuthorized } from "./revalidate-auth";

const SECRET = "s3cret-value-for-tests";

describe("isAuthorized", () => {
  it("accepts the right bearer token", () => {
    expect(isAuthorized(`Bearer ${SECRET}`, SECRET)).toBe(true);
    expect(isAuthorized(`bearer ${SECRET}`, SECRET)).toBe(true);
  });

  it("rejects a missing or empty header", () => {
    expect(isAuthorized(null, SECRET)).toBe(false);
    expect(isAuthorized("", SECRET)).toBe(false);
  });

  it("rejects other schemes and a bare token", () => {
    expect(isAuthorized(`Basic ${SECRET}`, SECRET)).toBe(false);
    expect(isAuthorized(SECRET, SECRET)).toBe(false);
    expect(isAuthorized("Bearer ", SECRET)).toBe(false);
  });

  it("rejects a wrong token of the same or a different length", () => {
    expect(isAuthorized(`Bearer ${SECRET.replace("s", "x")}`, SECRET)).toBe(
      false,
    );
    expect(isAuthorized(`Bearer ${SECRET}x`, SECRET)).toBe(false);
    expect(isAuthorized("Bearer x", SECRET)).toBe(false);
  });

  it("authorises nothing when the secret is unset or empty", () => {
    expect(isAuthorized("Bearer ", "")).toBe(false);
    expect(isAuthorized("Bearer undefined", undefined)).toBe(false);
    expect(isAuthorized("Bearer x", "")).toBe(false);
  });
});
