'use client'

import type { DictMedicalSummaryLabels } from '@/lib/i18n'
import type { MedicalMessage, MedicalBackendState } from '@/components/MedicalCenterChat'

type Props = {
  messages: MedicalMessage[]
  dict: DictMedicalSummaryLabels
  backendState?: MedicalBackendState | null
}

// ---------------------------------------------------------------------------
// Backend-aware detectors — prefer backend state, fall back to regex on messages
// ---------------------------------------------------------------------------

const _SPECIALTY_PATTERNS: Array<[RegExp, string]> = [
  [/кардиолог/i, 'Кардиолог'],
  [/педиатр/i, 'Педиатр'],
  [/терапевт/i, 'Терапевт'],
  [/эндокринолог/i, 'Эндокринолог'],
  [/гастроэнтеролог/i, 'Гастроэнтеролог'],
  [/невролог/i, 'Невролог'],
  [/лор|отоларинголог/i, 'ЛОР'],
  [/дерматолог/i, 'Дерматолог'],
  [/гинеколог/i, 'Гинеколог'],
  [/уролог/i, 'Уролог'],
  [/офтальмолог|окулист/i, 'Офтальмолог'],
  [/узи/i, 'УЗИ'],
  [/анализ/i, 'Анализы'],
]

function detectSpecialty(messages: MedicalMessage[], backendSpecialty?: string | null): string {
  if (backendSpecialty && backendSpecialty !== 'unknown') return backendSpecialty
  const all = messages.map((m) => m.text).join(' ')
  for (const [re, label] of _SPECIALTY_PATTERNS) {
    if (re.test(all)) return label
  }
  return '—'
}

function detectComplaint(messages: MedicalMessage[], backendComplaint?: string | null): string {
  if (backendComplaint) return backendComplaint
  return '—'
}

function detectTime(messages: MedicalMessage[], backendTime?: string | null): string {
  if (backendTime) return backendTime
  const userMsgs = messages.filter((m) => m.from === 'user')
  for (let i = userMsgs.length - 1; i >= 0; i--) {
    const match = userMsgs[i].text.match(
      /(?:после\s+\d+|в\s+\d{1,2}(?::\d{2})?|утром|вечером|днём|по\s+вечерам|по\s+утрам|после\s+работы|по\s+выходным|сегодня|завтра|в\s+(?:пн|вт|ср|чт|пт|сб|вс)|понедельник|вторник|сред|четверг|пятниц|суббот|воскресен)/i,
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
  | 'contact_requested'
  | 'contact_collected'
  | 'off_topic'
  | 'emergency'

function resolveStatus(
  messages: MedicalMessage[],
  leadStatus?: string | null,
  conversationStatus?: string | null,
): ConvStatus {
  // Emergency wins over everything — the visitor was told to call 103/112.
  if (conversationStatus === 'emergency') return 'emergency'
  if (leadStatus === 'contact_collected') return 'contact_collected'
  if (leadStatus === 'contact_requested') return 'contact_requested'
  if (conversationStatus) return conversationStatus as ConvStatus
  return messages.some((m) => m.from === 'user') ? 'exploring' : 'consultation'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const _DOT_COLOR: Record<ConvStatus, string> = {
  consultation:      'bg-secondary',
  exploring:         'bg-blue-400',
  intent_detected:   'bg-accent',
  objection:         'bg-yellow-400',
  agreed_next_step:  'bg-accent',
  contact_requested: 'bg-yellow-400',
  contact_collected: 'bg-green-500',
  off_topic:         'bg-secondary',
  emergency:         'bg-red-500',
}

export default function MedicalCenterSummaryPanel({ messages, dict, backendState }: Props) {
  const specialty = detectSpecialty(messages, backendState?.specialty)
  const complaint = detectComplaint(messages, backendState?.symptomsOrGoal)
  const time = detectTime(messages, backendState?.preferredTime)

  const status = resolveStatus(
    messages,
    backendState?.leadStatus,
    backendState?.conversationStatus,
  )
  const statusLabel =
    status === 'emergency'
      ? dict.statusValues.emergency
      : backendState?.conversationStatusLabel ?? dict.statusValues[status] ?? status

  const showEmergencyPill = status === 'emergency'
  const showPill =
    !showEmergencyPill &&
    (status === 'agreed_next_step' ||
      status === 'contact_requested' ||
      status === 'contact_collected')
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
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.specialty}</dt>
          <dd className="text-sm text-primary font-medium">{specialty}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.complaint}</dt>
          <dd className="text-sm text-primary font-medium">{complaint}</dd>
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

      {showEmergencyPill && (
        <div className="mt-6 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-center text-sm font-medium text-red-500">
          {dict.pillEmergency}
        </div>
      )}

      {showPill && (
        <div className="mt-6 rounded-xl border border-accent/20 bg-accent-soft/60 px-3 py-2.5 text-center text-sm font-medium text-accent">
          {pillLabel}
        </div>
      )}
    </div>
  )
}
