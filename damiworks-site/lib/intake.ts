// Guided intake flow — types, constants, and pure scoring/recommendation functions.
// No React. Imported by LiveChat and the lead API route.

export type IntakeField = 'channels' | 'tasks' | 'handoff' | 'volume' | 'timeline' | 'businessType'

export type IntakeState = {
  channels: string[]
  tasks: string[]
  handoff: string | null
  volume: string | null
  timeline: string | null
  businessType: string | null
  completed: boolean
}

export type IntakeQuestion = {
  id: IntakeField
  text: string
  options: string[]
  multi: boolean
  optional?: boolean
}

export type PackageId = 'Start' | 'Sales Assistant' | 'Integrated AI Employee'
export type InterestLevel = 'cold' | 'warm' | 'hot'

// A lead is one entity that evolves through events: `created` (intake done,
// recommendation shown, waiting for contact) → `updated` (contact captured,
// ready for follow-up). The owner receives one notification per event — never
// two identical "new lead" messages.
export type LeadEvent = 'created' | 'updated'

export type LeadContact = {
  name: string | null
  telegram: string | null
  phone: string | null
  raw: string
}

export type LeadSummary = {
  chat_id: string
  interest_level: InterestLevel
  channels: string[]
  tasks: string[]
  handoff: string | null
  volume: string | null
  timeline: string | null
  business_type: string | null
  recommended_package: PackageId
  estimated_price: string
  conversation_summary: string
  last_messages: Array<{ role: 'user' | 'assistant'; content: string }>
  created_at: string
  event?: LeadEvent
  contact?: LeadContact | null
  status?: string
}

export const INTAKE_QUESTIONS: IntakeQuestion[] = [
  {
    id: 'channels',
    text: 'Где вам пишут клиенты? Можно выбрать несколько.',
    options: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Другое'],
    multi: true,
  },
  {
    id: 'tasks',
    text: 'Что AI-сотрудник должен делать в первую очередь? (можно выбрать несколько)',
    options: [
      'Отвечать на вопросы',
      'Собирать контакты',
      'Квалифицировать лидов',
      'Передавать заявки менеджеру',
      'Делать follow-up',
    ],
    multi: true,
  },
  {
    id: 'handoff',
    text: 'Куда передавать заявки?',
    options: ['Telegram', 'Google Sheets', 'amoCRM', 'Bitrix24', 'Пока не знаю'],
    multi: false,
  },
  {
    id: 'volume',
    text: 'Сколько примерно обращений в день?',
    options: ['1–10', '10–30', '30–100', '100+'],
    multi: false,
  },
  {
    id: 'timeline',
    text: 'Когда хотите запустить?',
    options: ['В ближайшие дни', 'В этом месяце', 'Просто изучаю'],
    multi: false,
  },
  {
    id: 'businessType',
    text: 'Какой у вас бизнес? (необязательно)',
    options: ['Услуги', 'Онлайн-магазин', 'Обучение', 'Клиника/салон', 'Другое'],
    multi: false,
    optional: true,
  },
]

export const REQUIRED_INTAKE_STEPS = INTAKE_QUESTIONS.filter((q) => !q.optional).length // 5

export const INITIAL_INTAKE: IntakeState = {
  channels: [],
  tasks: [],
  handoff: null,
  volume: null,
  timeline: null,
  businessType: null,
  completed: false,
}

export const PACKAGE_PRICES: Record<PackageId, { setup: string; monthly: string }> = {
  Start: { setup: '150 000–200 000 ₸', monthly: '40 000–60 000 ₸/мес' },
  'Sales Assistant': { setup: '350 000 ₸', monthly: '120 000 ₸/мес' },
  'Integrated AI Employee': { setup: '700 000 ₸', monthly: '200 000 ₸/мес' },
}

/** Apply a single intake answer to the current state, returning a new object. */
export function applyIntakeAnswer(state: IntakeState, field: IntakeField, answers: string[]): IntakeState {
  const next = { ...state }
  switch (field) {
    case 'channels':
      next.channels = answers
      break
    case 'tasks':
      next.tasks = answers
      break
    case 'handoff':
      next.handoff = answers[0] ?? null
      break
    case 'volume':
      next.volume = answers[0] ?? null
      break
    case 'timeline':
      next.timeline = answers[0] ?? null
      break
    case 'businessType':
      next.businessType = answers[0] ?? null
      break
  }
  return next
}

/**
 * Score the intake using deterministic rules.
 * userMessages: free-text messages the user sent after intake (lowercase).
 * userClickedSend: whether the user manually clicked "Send this to Dami".
 */
export function scoreIntake(
  intake: IntakeState,
  userMessages: string[],
  userClickedSend: boolean,
): number {
  let score = 0

  if (intake.timeline === 'В ближайшие дни' || intake.timeline === 'В этом месяце') score += 2
  if (['10–30', '30–100', '100+'].includes(intake.volume ?? '')) score += 2
  if (
    intake.tasks.includes('Передавать заявки менеджеру') ||
    intake.tasks.includes('Квалифицировать лидов')
  )
    score += 2
  if (['Google Sheets', 'amoCRM', 'Bitrix24'].includes(intake.handoff ?? '')) score += 1
  if (userClickedSend) score += 1

  const lowers = userMessages.map((m) => m.toLowerCase())
  if (lowers.some((m) => /стоит|цена|цену|стоимост|сколько/.test(m))) score += 1
  if (lowers.some((m) => /хочу начать|давайте|как запустить|свяжитесь/.test(m))) score += 2

  return score
}

export function getInterestLevel(score: number): InterestLevel {
  if (score >= 6) return 'hot'
  if (score >= 3) return 'warm'
  return 'cold'
}

/** Pick a package based on intake answers. */
export function recommendPackage(intake: IntakeState): PackageId {
  const hasCRM = ['amoCRM', 'Bitrix24'].includes(intake.handoff ?? '')
  const hasFollowUp =
    intake.tasks.includes('Делать follow-up') || intake.tasks.includes('Квалифицировать лидов')
  const highVolume = ['30–100', '100+'].includes(intake.volume ?? '')
  // Low-volume exploratory: truly just looking, no CRM — keep at Start
  const isExploratory = intake.volume === '1–10' && intake.timeline === 'Просто изучаю'

  // Integrated only when CRM/API integration is explicitly required
  if (hasCRM) return 'Integrated AI Employee'
  // Sales Assistant for qualification, follow-up, handoff tasks, or moderate/high volume
  if (hasFollowUp || intake.tasks.includes('Передавать заявки менеджеру') || (highVolume && !isExploratory))
    return 'Sales Assistant'
  return 'Start'
}

/** Build the hidden context injected into the user message by the proxy. */
export function buildIntakeContextString(intake: IntakeState): string {
  const channels = intake.channels.join(', ') || 'не указаны'
  const tasks = intake.tasks.join(', ') || 'не указаны'
  const pkg = recommendPackage(intake)
  const prices = PACKAGE_PRICES[pkg]
  const priceStr =
    pkg === 'Start'
      ? `${prices.setup} за запуск + ${prices.monthly}`
      : `от ${prices.setup} за запуск + ${prices.monthly}`
  return [
    `[WEBSITE INTAKE CONTEXT — DO NOT ASK AGAIN]`,
    `Client answered the questionnaire. Use this; do not re-ask.`,
    `- Channels: ${channels}`,
    `- Tasks: ${tasks}`,
    `- Handoff: ${intake.handoff ?? 'не указано'}`,
    `- Volume: ${intake.volume ? `${intake.volume}/day` : 'не указан'}`,
    `- Timeline: ${intake.timeline ?? 'не указано'}`,
    `- Business type: ${intake.businessType ?? 'не указан'}`,
    `- Recommended package: ${pkg}`,
    `- Shown price: ${priceStr}`,
    ``,
    `Rules:`,
    `- Do NOT ask which functionality is priority (already selected above).`,
    `- Do NOT ask which channel they use (already selected).`,
    `- Do NOT ask about volume or timeline (already selected).`,
    `- If user asks about price, explain using the selected tasks and package above.`,
    `- If user says it is expensive, explain package contents and offer Start as cheaper option.`,
    `- If user references the questionnaire, confirm their selections and move forward.`,
  ].join('\n')
}

/** Format a Telegram-ready lead notification (HTML). */
function formatContactInline(contact?: LeadContact | null): string {
  if (!contact) return '—'
  const parts = [contact.name, contact.telegram, contact.phone].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : '—'
}

function formatLeadCreated(lead: LeadSummary): string {
  const emoji = lead.interest_level === 'hot' ? '🔥' : lead.interest_level === 'warm' ? '✅' : '🔵'
  const lines = [
    `${emoji} <b>New DamiWorks lead</b>`,
    '',
    `Interest: <b>${lead.interest_level.toUpperCase()}</b>`,
    `Package: ${lead.recommended_package}`,
    `Price: ${lead.estimated_price}`,
    '',
    `Business: ${lead.business_type ?? '—'}`,
    `Channels: ${lead.channels.join(', ') || '—'}`,
    `Tasks: ${lead.tasks.join(', ') || '—'}`,
    `Handoff: ${lead.handoff ?? '—'}`,
    `Volume: ${lead.volume ?? '—'}/day`,
    `Timeline: ${lead.timeline ?? '—'}`,
    '',
    `Contact: ${formatContactInline(lead.contact)}`,
    `Status: ${lead.status ?? (lead.contact ? 'Ready for follow-up' : 'Waiting for contact')}`,
    '',
    `Chat ID: <code>${lead.chat_id}</code>`,
  ]
  if (lead.last_messages.length > 0) {
    lines.push('', '<b>Last messages:</b>')
    for (const m of lead.last_messages.slice(-3)) {
      const prefix = m.role === 'user' ? '👤' : '🤖'
      lines.push(`${prefix} ${m.content.slice(0, 200)}`)
    }
  }
  return lines.join('\n')
}

function formatLeadUpdated(lead: LeadSummary): string {
  const c = lead.contact
  const lines = [
    '📝 <b>Lead updated</b>',
    '',
    `Package: ${lead.recommended_package}`,
    `Business: ${lead.business_type ?? '—'}`,
    '',
    '<b>Contact:</b>',
    `Name: ${c?.name ?? '—'}`,
    `Telegram: ${c?.telegram ?? '—'}`,
    `Phone: ${c?.phone ?? '—'}`,
    '',
    `Status: ${lead.status ?? 'Ready for follow-up'}`,
    '',
    `Chat ID: <code>${lead.chat_id}</code>`,
  ]
  return lines.join('\n')
}

export function formatLeadMessage(lead: LeadSummary): string {
  return lead.event === 'updated' ? formatLeadUpdated(lead) : formatLeadCreated(lead)
}
