// Free-form intake extraction — mirrors app/web_site_intake_policy.py
// (extract_freeform_profile) so the summary panel fills in real time from
// natural conversation, without requiring the guided questionnaire.
// Pure functions, no React. Imported by LiveChat and tests.

import type { IntakeState } from './intake'

export type FreeformExtract = {
  channels: string[]
  tasks: string[]
  handoff: string | null
  businessType: string | null
}

// NOTE: JS \b is ASCII-only and breaks next to Cyrillic — use explicit
// lookarounds for word boundaries on Cyrillic tokens.
const CHANNEL_PATTERNS: Array<[RegExp, string]> = [
  [/whats\s*app|ватсап|вотсап|воцап/i, 'WhatsApp'],
  [/instagram|инстаграм/i, 'Instagram'],
  [/telegram|телеграм|(?:^|[^а-яёa-z0-9_])тг(?![а-яёa-z0-9_])/i, 'Telegram'],
  [/2\s*(?:гис|gis)|дубль\s*гис/i, '2ГИС'],
  [/сайт|website/i, 'Website'],
]

// Canonical values match lib/intake.ts questionnaire values where possible so
// displayValues() maps them to localized labels; extras render verbatim.
const TASK_PATTERNS: Array<[RegExp, string]> = [
  [/отвеча|ответы\s+(?:клиент|на\s+вопрос)|консультир/i, 'Отвечать на вопросы'],
  [/запис\w+|appointment|назнача\w+\s+(?:при[её]м|встреч)|бронир/i, 'Запись клиентов'],
  [/собира\w+\s+контакт|сбор\s+контакт/i, 'Собирать контакты'],
  [/квалифи/i, 'Квалифицировать лидов'],
  [/передава\w+\s+заявк|передача\s+заявок/i, 'Передавать заявки менеджеру'],
  [/follow[\s-]?up|фоллоу/i, 'Делать follow-up'],
]

const HANDOFF_PATTERNS: Array<[RegExp, string]> = [
  [/(?:^|[^a-zа-яё0-9_])1[сc](?![a-zа-яё0-9_])/i, '1С'],
  [/amo\s*crm|амосрм/i, 'amoCRM'],
  [/битрикс|bitrix/i, 'Bitrix24'],
  [/google\s*sheets|гугл\s*табл/i, 'Google Sheets'],
]

const BUSINESS_PATTERNS: Array<[RegExp, string]> = [
  [/стоматолог/i, 'Стоматология'],
  [/клиник|медцентр/i, 'Клиника/салон'],
  [/салон|барбершоп/i, 'Клиника/салон'],
  [/магазин/i, 'Онлайн-магазин'],
  [/школ\w+|курс\w+|репетит|обучени/i, 'Обучение'],
  [/кафе|ресторан|доставк\w+\s+еды/i, 'Услуги'],
]

// Negation guard — mirrors _ff_positive_text in web_site_intake_policy.py:
// "у нас нет CRM", "не используем WhatsApp", "Instagram раньше был, сейчас не
// работает" must not register facts.
const NEGATION_RE = /(?:^|[^а-яёa-z0-9_])(?:нет|не|без)(?![а-яёa-z0-9_])/i

const ALL_PATTERNS: RegExp[] = [
  ...CHANNEL_PATTERNS,
  ...TASK_PATTERNS,
  ...HANDOFF_PATTERNS,
  ...BUSINESS_PATTERNS,
].map(([re]) => re)

function clauseHasKeyword(clause: string): boolean {
  return ALL_PATTERNS.some((re) => re.test(clause))
}

function positiveText(text: string): string {
  const kept: string[] = []
  for (const clause of text.split(/[.,;!?\n]+/)) {
    if (NEGATION_RE.test(clause)) {
      // A negation clause without its own keyword refers back to the previous
      // clause ("Instagram раньше был, сейчас не работает") — drop it too.
      if (kept.length > 0 && !clauseHasKeyword(clause)) kept.pop()
      continue
    }
    kept.push(clause)
  }
  return kept.join(' . ')
}

/** Extract channels/tasks/CRM/business type from free-form user messages. */
export function extractFreeformIntake(userTexts: string[]): FreeformExtract {
  const combined = userTexts.filter(Boolean).map(positiveText).join('\n')
  const channels = CHANNEL_PATTERNS.filter(([re]) => re.test(combined)).map(([, label]) => label)
  const tasks = TASK_PATTERNS.filter(([re]) => re.test(combined)).map(([, label]) => label)
  const handoff = HANDOFF_PATTERNS.find(([re]) => re.test(combined))?.[1] ?? null
  const businessType = BUSINESS_PATTERNS.find(([re]) => re.test(combined))?.[1] ?? null
  return { channels, tasks, handoff, businessType }
}

/**
 * Merge free-form extraction into the intake state. Questionnaire answers
 * always win; extraction only fills fields the user has not answered.
 * Never touches `completed`.
 */
export function mergeFreeformIntake(intake: IntakeState, extracted: FreeformExtract): IntakeState {
  if (intake.completed) return intake
  return {
    ...intake,
    channels: intake.channels.length > 0 ? intake.channels : extracted.channels,
    tasks: intake.tasks.length > 0 ? intake.tasks : extracted.tasks,
    handoff: intake.handoff ?? extracted.handoff,
    businessType: intake.businessType ?? extracted.businessType,
  }
}

/** Enough free-form context to show a recommendation and a conversion next step. */
export function hasFreeformSummary(intake: IntakeState): boolean {
  return intake.channels.length > 0 && intake.tasks.length > 0
}

/** Quick replies: a clicked predefined chip disappears for the session. */
export function filterUnusedChips(chips: string[], usedChips: string[]): string[] {
  return chips.filter((chip) => !usedChips.includes(chip))
}
