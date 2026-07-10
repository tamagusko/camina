import "server-only";
import { createHash, timingSafeEqual } from "node:crypto";

// Constant-time secret comparison. Both sides are SHA-256 hashed first so
// the buffers always have equal length: timingSafeEqual throws on unequal
// lengths, and short-circuiting on length would leak the secret's length.
export function secureCompare(a: string, b: string): boolean {
  const hashA = createHash("sha256").update(a).digest();
  const hashB = createHash("sha256").update(b).digest();
  return timingSafeEqual(hashA, hashB);
}
