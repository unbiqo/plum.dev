'use client'

import { useEffect, useRef, useState } from 'react'
import type { DictMedicalSummaryLabels } from '@/lib/i18n'
import type { MedicalMessage, MedicalBackendState } from '@/components/MedicalCenterChat'
import { detectSpecialty, normalizeComplaint } from '@/lib/medicalSummary'

type Props = {
  messages: MedicalMessage[]
  dict: DictMedicalSummaryLabels
  backendState?: MedicalBackendState | null
}

// ---------------------------------------------------------------------------
// Backend-aware detectors — the backend is the source of truth; specialty
// detection lives in lib/medicalSummary.ts (detectSpecialty) for testability.
// ---------------------------------------------------------------------------

function detectComplaint(messages: MedicalMessage[], backendComplaint?: string | null): string {
  if (backendComplaint) return normalizeComplaint(backendComplaint)
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
  | 'new_dialog'
  | 'consultation'
  | 'exploring'
  | 'doctor_selection'
  | 'intent_detected'
  | 'objection'
  | 'agreed_next_step'
  | 'slots_offered'
  | 'awaiting_contact'
  | 'booking_created'
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
  // The backend conversation status already folds in lead progress (slots,
  // awaiting contact, booking created), so prefer it when present.
  if (conversationStatus) return conversationStatus as ConvStatus
  if (leadStatus === 'contact_collected') return 'contact_collected'
  if (leadStatus === 'contact_requested') return 'contact_requested'
  return messages.some((m) => m.from === 'user') ? 'exploring' : 'new_dialog'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const _DOT_COLOR: Record<ConvStatus, string> = {
  new_dialog:        'bg-secondary',
  consultation:      'bg-secondary',
  exploring:         'bg-blue-400',
  doctor_selection:  'bg-blue-400',
  intent_detected:   'bg-accent',
  objection:         'bg-yellow-400',
  agreed_next_step:  'bg-accent',
  slots_offered:     'bg-accent',
  awaiting_contact:  'bg-yellow-400',
  booking_created:   'bg-green-500',
  contact_requested: 'bg-yellow-400',
  contact_collected: 'bg-green-500',
  off_topic:         'bg-secondary',
  emergency:         'bg-red-500',
}

export default function MedicalCenterSummaryPanel({ messages, dict, backendState }: Props) {
  const specialty = detectSpecialty(backendState?.specialty)
  const complaint = detectComplaint(messages, backendState?.symptomsOrGoal)
  const time = detectTime(messages, backendState?.selectedSlot || backendState?.preferredTime)

  // Flash fields as the backend fills them in — the заявка visibly assembles
  // itself while the visitor chats. CSS animation lives in globals.css and is
  // disabled under prefers-reduced-motion.
  const [flashed, setFlashed] = useState<Set<string>>(new Set())
  const prevFieldsRef = useRef<Record<string, string> | null>(null)

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
      status === 'slots_offered' ||
      status === 'awaiting_contact' ||
      status === 'booking_created' ||
      status === 'contact_requested' ||
      status === 'contact_collected')
  const pillLabel =
    status === 'contact_collected' || status === 'booking_created'
      ? dict.pillContact
      : status === 'contact_requested' || status === 'awaiting_contact'
        ? dict.pillAwaiting
        : dict.pillReady

  const dotColor = _DOT_COLOR[status] ?? 'bg-secondary'

  useEffect(() => {
    const fields: Record<string, string> = { specialty, complaint, time, status: statusLabel }
    const prev = prevFieldsRef.current
    prevFieldsRef.current = fields
    if (!prev) return
    const changed = new Set(Object.keys(fields).filter((k) => prev[k] !== fields[k]))
    if (changed.size === 0) return
    setFlashed(changed)
    const id = setTimeout(() => setFlashed(new Set()), 900)
    return () => clearTimeout(id)
  }, [specialty, complaint, time, statusLabel])

  const flashClass = (key: string) => (flashed.has(key) ? ' field-flash' : '')

  return (
    <div className="bg-surface border border-border-col rounded-2xl p-6 flex flex-col">
      <div className="flex items-center gap-2 mb-5">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
        <span className="text-sm font-semibold text-primary">{dict.title}</span>
      </div>

      <dl className="space-y-4 flex-1">
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.specialty}</dt>
          <dd className={`text-sm text-primary font-medium rounded-md${flashClass('specialty')}`}>{specialty}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.complaint}</dt>
          <dd className={`text-sm text-primary font-medium rounded-md${flashClass('complaint')}`}>{complaint}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.time}</dt>
          <dd className={`text-sm text-primary font-medium rounded-md${flashClass('time')}`}>{time}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{dict.status}</dt>
          <dd className={`flex items-center gap-1.5 rounded-md${flashClass('status')}`}>
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
