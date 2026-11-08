import "server-only";

/** Run a data read; on failure log it and return null so the section shows its empty state. */
export async function safely<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch (error) {
    console.error("data read failed", error);
    return null;
  }
}
