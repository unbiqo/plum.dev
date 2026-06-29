// Frontend mirror of the backend contact-detection rules
// (damiworks-ai-service/app/web_site_intake_policy.py). Used post-intake to
// decide when a user reply is a contact (phone / Telegram / bare name after a
// contact ask) so the UI can close the lead and emit a LeadUpdated event.

import type { LeadContact } from './intake'

const ASKED_FOR_CONTACT_RE =
  /остав\w*|\bимя\b|\bномер\b|whatsapp|telegram|телеграм\w*|\bконтакт\w*|свяжемся|с вами свяж\w+|следующ\w+ шаг|перед(ам|адим) заявку/i

export function assistantAskedForContact(lastAssistantMessage: string): boolean {
  return ASKED_FOR_CONTACT_RE.test(lastAssistantMessage || '')
}

const TELEGRAM_RE = /@[A-Za-z0-9_]{3,}|t\.me\/|\btelegram\b|\bтелеграм\w*|\bтг\b|мой тг|мой telegram/i
const PHONE_RE = /\+?\d[\d\-\s()]{6,}\d/g

// Other deterministic intents that must never be misread as a bare name.
const OTHER_INTENT_RE =
  /готов|давай|подходит|погнали|запуска|интересно|попробовать|дальше|не помню|не знаю|дешевле|сколько|что входит|как (нач|раб)|следующий шаг/i

const FILLERS = new Set([
  'да', 'нет', 'ок', 'окей', 'хорошо', 'ладно', 'понятно', 'не знаю', 'не помню',
  'пока нет', 'позже', 'что дальше', 'как начать', 'сколько стоит', 'что входит',
  'можно дешевле',
])

export function hasPhone(text: string): boolean {
  const matches = (text || '').match(PHONE_RE) ?? []
  return matches.some((m) => m.replace(/\D/g, '').length >= 7)
}

function extractPhone(text: string): string | null {
  const m = (text || '').match(/\+?\d[\d\-\s()]{6,}\d/)
  return m ? m[0].trim() : null
}

function isPlausibleName(s: string): boolean {
  const t = s.trim()
  if (t.length < 2 || t.length > 40) return false
  if (t.includes('?')) return false
  if (t.split(/\s+/).length > 4) return false
  if (!/[^\W\d_]/u.test(t)) return false // at least one letter
  if (!/^[\w .\-]+$/u.test(t)) return false
  if (OTHER_INTENT_RE.test(t)) return false
  return !FILLERS.has(t.toLowerCase().replace(/ё/g, 'е'))
}

export type ParsedContact = LeadContact & { kind: 'phone' | 'telegram' | 'name' | null }

export function parseContactReply(userMessage: string, lastAssistantMessage = ''): ParsedContact {
  const raw = (userMessage || '').trim()
  const none: ParsedContact = { kind: null, name: null, telegram: null, phone: null, raw }

  if (hasPhone(raw)) {
    return { kind: 'phone', name: null, telegram: null, phone: extractPhone(raw), raw }
  }
  if (TELEGRAM_RE.test(raw)) {
    const at = raw.match(/@[A-Za-z0-9_]{3,}/)
    return { kind: 'telegram', name: null, telegram: at ? at[0] : raw, phone: null, raw }
  }
  if (assistantAskedForContact(lastAssistantMessage) && isPlausibleName(raw)) {
    return { kind: 'name', name: raw, telegram: null, phone: null, raw }
  }
  return none
}

export function isContactLikeReply(userMessage: string, lastAssistantMessage = ''): boolean {
  return parseContactReply(userMessage, lastAssistantMessage).kind !== null
}
