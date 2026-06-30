'use client'

import type { DictSchoolSummaryLabels } from '@/lib/i18n'
import type { SchoolMessage, SchoolBackendState } from '@/components/EnglishSchoolChat'

type Props = {
  messages: SchoolMessage[]
  dict: DictSchoolSummaryLabels
  backendState?: SchoolBackendState | null
}

// ---------------------------------------------------------------------------
// Backend-aware detectors — prefer backend state, fall back to regex on messages
// ---------------------------------------------------------------------------

function detectFormat(messages: SchoolMessage[], backendFormat?: string | null): string {
  if (backendFormat && backendFormat !== 'unknown') {
    const map: Record<string, string> = {
      individual: 'Индивидуально',
      group: 'Группа',
      online: 'Онлайн',
      offline: 'Офлайн',
    }
    return map[backendFormat] ?? '—'
  }
  const all = messages.map((m) => m.text.toLowerCase()).join(' ')
  if (/индивидуальн|личн|личные занятия|один.на.один/.test(all)) return 'Индивидуально'
  if (/групп(?:овые|овой|а|ы)|мини-групп/.test(all)) return 'Группа'
  if (/онлайн/.test(all)) return 'Онлайн'
  return '—'
}

function detectGoal(messages: SchoolMessage[], backendProgram?: string | null): string {
  if (backendProgram && backendProgram !== 'unknown') {
    const map: Record<string, string> = {
      ielts: 'IELTS',
      kids: 'Для детей',
      teen: 'Для подростков',
      high_school: 'High School',
      adult: 'Для взрослых',
      speaking_club: 'Speaking Club',
    }
    return map[backendProgram] ?? '—'
  }
  const userText = messages
    .filter((m) => m.from === 'user')
    .map((m) => m.text.toLowerCase())
    .join(' ')
  if (/ielts/.test(userText)) return 'IELTS'
  if (/ребён|ребенк|сын|дочь|дочер|ребёнка/.test(userText)) return 'Для ребёнка'
  if (/для себя|себе|сам|работа|путешеств|деловой/.test(userText)) return 'Для себя'
  if (/разговорн/.test(userText)) return 'Разговорный'
  return '—'
}

function detectTime(messages: SchoolMessage[], backendSchedule?: string | null): string {
  // Backend preferred_schedule is free text extracted from user's mention — prefer it.
  if (backendSchedule) return backendSchedule

  const userMsgs = messages.filter((m) => m.from === 'user')
  for (let i = userMsgs.length - 1; i >= 0; i--) {
    const text = userMsgs[i].text
    const match = text.match(
      /(?:после\s+\d+|в\s+\d{1,2}(?::\d{2})?|утром|вечером|днём|по\s+вечерам|по\s+утрам|после\s+работы|по\s+выходным|завтра|в\s+(?:пн|вт|ср|чт|пт|сб|вс)|понедельник|вторник|сред|четверг|пятниц|суббот|воскресен)/i,
    )
    if (match) return match[0]
  }
  return '—'
}

type ConvStatus =
  | 'consultation'
  | 'exploring'
  | 'intent_detected'
  | 'objection'
  | 'agreed_next_step'
  | 'not_ready'
  | 'contact_requested'
  | 'contact_collected'
  | 'off_topic'

function resolveStatus(
  messages: SchoolMessage[],
  leadStatus?: string | null,
  conversationStatus?: string | null,
): ConvStatus {
  // Lead status is monotonic and always wins for contact states.
  if (leadStatus === 'contact_collected') return 'contact_collected'
  if (leadStatus === 'contact_requested') return 'contact_requested'
  // Backend conversation status is authoritative for all pre-contact stages.
  if (conversationStatus) return conversationStatus as ConvStatus
  // Fallback when backend hasn't responded yet.
  return messages.some((m) => m.from === 'user') ? 'exploring' : 'consultation'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const _DOT_COLOR: Record<ConvStatus, string> = {
  consultation:     'bg-secondary',
  exploring:        'bg-blue-400',
  intent_detected:  'bg-accent',
  objection:        'bg-yellow-400',
  agreed_next_step: 'bg-accent',
  not_ready:        'bg-secondary',
  contact_requested:'bg-yellow-400',
  contact_collected:'bg-green-500',
  off_topic:        'bg-secondary',
}

export default function EnglishSchoolSummaryPanel({ messages, dict, backendState }: Props) {
  const format = detectFormat(messages, backendState?.formatPreference)
  const goal = detectGoal(messages, backendState?.program)
  const time = detectTime(messages, backendState?.preferredSchedule)

  const status = resolveStatus(
    messages,
    backendState?.leadStatus,
    backendState?.conversationStatus,
  )
  const statusLabel = backendState?.conversationStatusLabel ?? dict.statusValues[status] ?? status

  const showPill =
    status === 'agreed_next_step' ||
    status === 'contact_requested' ||
    status === 'contact_collected'
  const pillLabel =
    status === 'contact_collected'
      ? dict.pillContact
      : status === 'contact_requested'
        ? dict.pillAwaiting
        : dict.pillReady

  const dotColor = _DOT_COLOR[status] ?? 'bg-secondary'

  return (
    <div className="bg-surface border border-border-col rounded-2xl p-6 flex flex-col">
      <div className="flex items-center gap-2 mb-5">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
        <span className="text-sm font-semibold text-primary">{dict.title}</span>
      </div>

      <dl className="space-y-4 flex-1">
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.format}</dt>
          <dd className="text-sm text-primary font-medium">{format}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.goal}</dt>
          <dd className="text-sm text-primary font-medium">{goal}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.time}</dt>
          <dd className="text-sm text-primary font-medium">{time}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.status}</dt>
          <dd className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
            <span className="text-sm text-primary font-medium">{statusLabel}</span>
          </dd>
        </div>
      </dl>

      {showPill && (
        <div className="mt-6 rounded-xl border border-accent/20 bg-accent-soft/60 px-3 py-2.5 text-center text-sm font-medium text-accent">
          {pillLabel}
        </div>
      )}
    </div>
  )
}
