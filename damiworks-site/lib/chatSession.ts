// Unified per-instance chat session storage with an explicit TTL.
//
// Each chat demo persists its OWN session under an instance-scoped localStorage
// key: `damiworks_chat_session_v1:<instance_id>`. The session is per browser /
// device (localStorage is origin + browser scoped) — never shared, never
// hardcoded. A different browser, device, or incognito window gets a different
// session automatically.
//
// Why does an old intake remain after a page reload?
//   Because the session (chat_id) is persisted locally and the backend / lead
//   upsert is keyed by (instance_id, chat_id). On reload we reuse the same
//   chat_id, so the flow continues from the previous session. This is
//   intentional — but only within the TTL below. Once the session is older than
//   its TTL it is treated as stale: we mint a new chat_id and the caller clears
//   the local chat history for that instance.

export const DAMIWORKS_SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7 days
export const ENGLISH_SCHOOL_SESSION_TTL_MS = 24 * 60 * 60 * 1000 // 24 hours
export const BEAUTY_SESSION_TTL_MS = 24 * 60 * 60 * 1000 // 24 hours

const SESSION_KEY_PREFIX = 'damiworks_chat_session_v1'

export type ChatSession = {
  chat_id: string
  created_at: string
  updated_at: string
  instance_id: string
}

export type LoadResult = {
  session: ChatSession
  /** True when a brand-new session was minted (no prior session, corrupt, or expired). */
  isNew: boolean
  /** True only when an existing session was discarded because it exceeded the TTL. */
  expired: boolean
}

export function chatSessionKey(instanceId: string): string {
  return `${SESSION_KEY_PREFIX}:${instanceId}`
}

export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

function readStorage(): Storage | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage : null
  } catch {
    return null // SSR or privacy mode where storage access throws
  }
}

function persist(storage: Storage | null, key: string, session: ChatSession): void {
  if (!storage) return
  try {
    storage.setItem(key, JSON.stringify(session))
  } catch {
    // storage full / disabled — non-fatal, session still works for this page load
  }
}

function newSession(instanceId: string, now: number): ChatSession {
  const iso = new Date(now).toISOString()
  return { chat_id: generateUUID(), created_at: iso, updated_at: iso, instance_id: instanceId }
}

function isExpired(session: ChatSession, ttlMs: number, now: number): boolean {
  const last = new Date(session.updated_at).getTime()
  if (Number.isNaN(last)) return true
  return now - last > ttlMs
}

/**
 * Load the session for an instance: reuse it when present and within TTL (and
 * bump `updated_at` so an active conversation keeps its sliding window), or mint
 * a fresh one. The result is always persisted back to storage.
 */
export function loadChatSession(
  instanceId: string,
  ttlMs: number,
  now: number = Date.now(),
): LoadResult {
  const storage = readStorage()
  const key = chatSessionKey(instanceId)

  let stored: ChatSession | null = null
  const raw = storage?.getItem(key)
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as Partial<ChatSession>
      if (parsed && typeof parsed.chat_id === 'string' && parsed.chat_id) {
        const createdAt = parsed.created_at ?? new Date(now).toISOString()
        stored = {
          chat_id: parsed.chat_id,
          created_at: createdAt,
          updated_at: parsed.updated_at ?? createdAt,
          instance_id: instanceId,
        }
      }
    } catch {
      stored = null // corrupt — fall through to a fresh session
    }
  }

  if (stored && !isExpired(stored, ttlMs, now)) {
    const bumped: ChatSession = { ...stored, updated_at: new Date(now).toISOString() }
    persist(storage, key, bumped)
    return { session: bumped, isNew: false, expired: false }
  }

  const expired = stored !== null // had a session, but it was stale
  const fresh = newSession(instanceId, now)
  persist(storage, key, fresh)
  return { session: fresh, isNew: true, expired }
}

/** Bump `updated_at` to keep an active session alive (sliding TTL). No-op if missing. */
export function touchChatSession(instanceId: string, now: number = Date.now()): void {
  const storage = readStorage()
  if (!storage) return
  const key = chatSessionKey(instanceId)
  const raw = storage.getItem(key)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw) as ChatSession
    persist(storage, key, {
      ...parsed,
      instance_id: instanceId,
      updated_at: new Date(now).toISOString(),
    })
  } catch {
    // ignore corrupt storage
  }
}

/** Reset: mint a brand-new session (new chat_id) for the instance and persist it. */
export function resetChatSession(instanceId: string, now: number = Date.now()): ChatSession {
  const storage = readStorage()
  const fresh = newSession(instanceId, now)
  persist(storage, chatSessionKey(instanceId), fresh)
  return fresh
}
