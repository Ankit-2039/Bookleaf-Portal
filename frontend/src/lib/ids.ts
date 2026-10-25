/** Client-generated id for idempotent sends. Falls back when crypto.randomUUID is unavailable (non-HTTPS origins). */
export function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}