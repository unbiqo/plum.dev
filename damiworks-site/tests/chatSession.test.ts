/**
 * Unit tests for per-instance chat session storage + TTL.
 * Run with: npx tsx tests/chatSession.test.ts
 * No test framework required — uses Node built-in assert + a memory localStorage.
 */
import assert from 'node:assert/strict'

// --- minimal localStorage polyfill so the browser-focused helper runs in Node ---
class MemoryStorage {
  private map = new Map<string, string>()
  getItem(k: string): string | null {
    return this.map.has(k) ? (this.map.get(k) as string) : null
  }
  setItem(k: string, v: string): void {
    this.map.set(k, String(v))
  }
  removeItem(k: string): void {
    this.map.delete(k)
  }
  clear(): void {
    this.map.clear()
  }
}
const storage = new MemoryStorage()
;(globalThis as unknown as { localStorage: Storage }).localStorage = storage as unknown as Storage

import {
  chatSessionKey,
  loadChatSession,
  resetChatSession,
  touchChatSession,
  DAMIWORKS_SESSION_TTL_MS,
  ENGLISH_SCHOOL_SESSION_TTL_MS,
} from '../lib/chatSession'

const SITE = 'damiworks_site'
const SCHOOL = 'damiworks_english_school_demo'

function pass(name: string) {
  console.log(`  ✓ ${name}`)
}

function suite(name: string, fn: () => void) {
  console.log(`\n${name}`)
  fn()
}

function reset() {
  storage.clear()
}

// ---------------------------------------------------------------------------

suite('loadChatSession', () => {
  reset()
  {
    const { session, isNew, expired } = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS)
    assert.match(session.chat_id, /[0-9a-f-]{8,}/i, 'mints a uuid-like chat_id')
    assert.equal(session.instance_id, SITE)
    assert.equal(isNew, true, 'first load is new')
    assert.equal(expired, false, 'first load is not an expiry')
    pass('a fresh load mints a new uuid chat_id, isNew=true, expired=false')
  }

  {
    const first = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS)
    const second = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS)
    assert.equal(first.session.chat_id, second.session.chat_id, 'same id reused within TTL')
    assert.equal(second.isNew, false)
    pass('reload within TTL reuses the same chat_id')
  }

  {
    reset()
    const t0 = 1_000_000_000_000
    const first = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS, t0)
    const later = t0 + DAMIWORKS_SESSION_TTL_MS + 1
    const second = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS, later)
    assert.notEqual(first.session.chat_id, second.session.chat_id, 'expired -> new id')
    assert.equal(second.expired, true, 'flagged as expired')
    assert.equal(second.isNew, true)
    pass('a session past its TTL is replaced and flagged expired')
  }

  {
    reset()
    const t0 = 2_000_000_000_000
    loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS, t0)
    // touch keeps it alive past the original window
    touchChatSession(SITE, t0 + DAMIWORKS_SESSION_TTL_MS - 1000)
    const again = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS, t0 + DAMIWORKS_SESSION_TTL_MS + 500)
    assert.equal(again.expired, false, 'touch slides the TTL window forward')
    assert.equal(again.isNew, false)
    pass('touchChatSession slides the TTL window so an active session survives')
  }
})

suite('resetChatSession', () => {
  reset()
  const before = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS).session.chat_id
  const after = resetChatSession(SITE).chat_id
  assert.notEqual(before, after, 'reset mints a new id')
  const reloaded = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS).session.chat_id
  assert.equal(after, reloaded, 'the reset id is persisted')
  pass('reset creates and persists a new chat_id')
})

suite('per-instance isolation', () => {
  reset()
  assert.notEqual(chatSessionKey(SITE), chatSessionKey(SCHOOL), 'distinct storage keys per instance')

  const site = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS).session.chat_id
  const school = loadChatSession(SCHOOL, ENGLISH_SCHOOL_SESSION_TTL_MS).session.chat_id
  assert.notEqual(site, school, 'DamiWorks and English School get different chat_ids')

  // Touch/reset on one instance must not affect the other.
  resetChatSession(SCHOOL)
  const siteAfter = loadChatSession(SITE, DAMIWORKS_SESSION_TTL_MS).session.chat_id
  assert.equal(site, siteAfter, 'resetting English School does not overwrite DamiWorks')
  pass('different instance_id values use separate keys and never overwrite each other')
})

console.log('\nAll chatSession tests passed.\n')
