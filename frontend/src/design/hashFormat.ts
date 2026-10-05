/** Truncate a hash/id to head…tail; tail 0 keeps only the head. */
export function shortHash(value: string, head = 6, tail = 4): string {
  return value.length <= head + tail + 1 ? value : `${value.slice(0, head)}…${tail > 0 ? value.slice(-tail) : ""}`;
}
