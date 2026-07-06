export const QUALITY_ISSUE_TYPES = [
  'hallucinated_fact',
  'wrong_price',
  'wrong_schedule_or_slot',
  'missed_contact_collection',
  'misunderstood_user',
  'unsafe_advice',
  'too_verbose',
  'too_pushy',
  'bad_tone',
  'wrong_language',
  'broken_flow',
  'unsafe_medical_answer',
  'diagnosis_or_prescription',
  'wrong_specialist_routing',
  'wrong_program_recommendation',
  'wrong_discount_or_promo',
  'other',
] as const

export const QUALITY_SEVERITIES = ['low', 'medium', 'high', 'critical'] as const
export const QUALITY_STATUSES = ['open', 'reviewed', 'fixed', 'ignored', 'added_to_evals'] as const
export const QUALITY_RATINGS = ['positive', 'negative'] as const
export const SUPPORTED_QUALITY_INSTANCE_IDS = [
  'damiworks_site',
  'damiworks_english_school_demo',
  'damiworks_medical_center_demo',
  'damiworks_custom_demo',
] as const

export type QualityIssueType = (typeof QUALITY_ISSUE_TYPES)[number]
export type QualitySeverity = (typeof QUALITY_SEVERITIES)[number]
export type QualityStatus = (typeof QUALITY_STATUSES)[number]
export type QualityRating = (typeof QUALITY_RATINGS)[number]

export type QualityChatMessage = {
  id?: string
  from: 'user' | 'ai'
  text: string
}

export type QualityFeedbackPayload = {
  instance_id: string
  chat_id: string
  message_id: string
  rating: QualityRating
  issue_type: QualityIssueType | string
  severity: QualitySeverity
  status?: QualityStatus
  user_message?: string | null
  assistant_answer: string
  corrected_answer?: string | null
  comment?: string | null
  reviewer_note?: string | null
  transcript_json: Array<{ role: 'user' | 'assistant' | 'system'; content: string; message_id?: string }>
  metadata?: Record<string, unknown>
  source?: string
  environment?: string
  tags?: string[]
}

export type ConversationFilters = {
  instance_id?: string
  chat_id?: string
  lead_status?: string
  has_feedback?: string
  rating?: string
  issue_type?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export function buildConversationQuery(filters: ConversationFilters): string {
  const qs = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    qs.set(key, String(value))
  })
  return qs.toString()
}

export function buildMessageReviewPayload(args: {
  instance_id: string
  chat_id: string
  message_id: string
  rating: QualityRating
  issue_type: QualityIssueType | string
  severity: QualitySeverity
  status?: QualityStatus
  user_message?: string | null
  assistant_answer: string
  corrected_answer?: string | null
  comment?: string | null
  reviewer_note?: string | null
  transcript_json: QualityFeedbackPayload['transcript_json']
  metadata?: Record<string, unknown>
}): QualityFeedbackPayload {
  return {
    ...args,
    status: args.status ?? 'open',
    source: 'admin_console',
    environment: typeof process !== 'undefined' ? process.env.NODE_ENV : undefined,
    tags: [],
  }
}

export function createMessageId(prefix = 'msg'): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}_${crypto.randomUUID()}`
  }
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

export function ensureMessageIds<T extends QualityChatMessage>(
  messages: T[],
  prefix = 'msg',
): T[] {
  let changed = false
  const next = messages.map((message) => {
    if (message.id) return message
    changed = true
    return { ...message, id: createMessageId(prefix) }
  })
  return changed ? next : messages
}

export function findPreviousUserMessage(
  messages: QualityChatMessage[],
  messageId: string,
): string | null {
  const idx = messages.findIndex((m) => m.id === messageId)
  if (idx < 0) return null
  for (let i = idx - 1; i >= 0; i--) {
    if (messages[i].from === 'user') return messages[i].text
  }
  return null
}

export function buildFeedbackTranscript(messages: QualityChatMessage[]) {
  return messages.map((m) => ({
    role: m.from === 'user' ? ('user' as const) : ('assistant' as const),
    content: m.text,
    message_id: m.id,
  }))
}

export function issueLabel(issue: string): string {
  return issue
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}
