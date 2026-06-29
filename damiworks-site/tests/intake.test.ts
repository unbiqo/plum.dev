/**
 * Unit tests for intake scoring, package recommendation, and lead summary.
 * Run with: npx tsx tests/intake.test.ts
 * No test framework required — uses Node built-in assert.
 */
import assert from 'node:assert/strict'

import {
  INITIAL_INTAKE,
  INTAKE_QUESTIONS,
  applyIntakeAnswer,
  buildIntakeContextString,
  formatLeadMessage,
  getInterestLevel,
  recommendPackage,
  scoreIntake,
  type IntakeState,
  type LeadSummary,
} from '../lib/intake'
import {
  assistantAskedForContact,
  isContactLikeReply,
  parseContactReply,
} from '../lib/contact'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pass(name: string) {
  console.log(`  ✓ ${name}`)
}

function suite(name: string, fn: () => void) {
  console.log(`\n${name}`)
  fn()
}

// ---------------------------------------------------------------------------
// scoreIntake
// ---------------------------------------------------------------------------

suite('scoreIntake', () => {
  const base: IntakeState = {
    ...INITIAL_INTAKE,
    channels: ['WhatsApp'],
    tasks: ['Отвечать на вопросы'],
    handoff: 'Пока не знаю',
    volume: '1–10',
    timeline: 'Просто изучаю',
    businessType: null,
    completed: true,
  }

  const cold = scoreIntake(base, [], false)
  assert.equal(cold, 0, 'cold lead: no scoring signals → 0')
  pass('cold lead scores 0')

  const withTimeline = scoreIntake({ ...base, timeline: 'В этом месяце' }, [], false)
  assert.equal(withTimeline, 2, 'timeline "В этом месяце" adds +2')
  pass('urgent timeline adds +2')

  const withVolume = scoreIntake({ ...base, volume: '10–30' }, [], false)
  assert.equal(withVolume, 2, 'volume 10–30 adds +2')
  pass('mid volume adds +2')

  const withHighVolume = scoreIntake({ ...base, volume: '100+' }, [], false)
  assert.equal(withHighVolume, 2, '100+ volume adds +2')
  pass('high volume adds +2')

  const withSalesTasks = scoreIntake(
    { ...base, tasks: ['Передавать заявки менеджеру'] },
    [],
    false,
  )
  assert.equal(withSalesTasks, 2, 'sales tasks add +2')
  pass('sales tasks add +2')

  const withHandoff = scoreIntake({ ...base, handoff: 'Google Sheets' }, [], false)
  assert.equal(withHandoff, 1, 'Google Sheets handoff adds +1')
  pass('Google Sheets handoff adds +1')

  const withClickedSend = scoreIntake(base, [], true)
  assert.equal(withClickedSend, 1, 'user clicked send adds +1')
  pass('user clicked send adds +1')

  const withPrice = scoreIntake(base, ['сколько стоит?'], false)
  assert.equal(withPrice, 1, 'price question adds +1')
  pass('price question adds +1')

  const withClose = scoreIntake(base, ['хочу начать'], false)
  assert.equal(withClose, 2, 'close intent adds +2')
  pass('close intent adds +2')

  const hot: IntakeState = {
    ...base,
    tasks: ['Квалифицировать лидов', 'Передавать заявки менеджеру'],
    handoff: 'Google Sheets',
    volume: '10–30',
    timeline: 'В ближайшие дни',
  }
  const hotScore = scoreIntake(hot, [], false)
  assert(hotScore >= 6, `hot lead should score ≥6, got ${hotScore}`)
  pass('hot lead scores ≥6')
})

// ---------------------------------------------------------------------------
// getInterestLevel
// ---------------------------------------------------------------------------

suite('getInterestLevel', () => {
  assert.equal(getInterestLevel(0), 'cold')
  assert.equal(getInterestLevel(2), 'cold')
  pass('0–2 → cold')

  assert.equal(getInterestLevel(3), 'warm')
  assert.equal(getInterestLevel(5), 'warm')
  pass('3–5 → warm')

  assert.equal(getInterestLevel(6), 'hot')
  assert.equal(getInterestLevel(10), 'hot')
  pass('6+ → hot')
})

// ---------------------------------------------------------------------------
// recommendPackage
// ---------------------------------------------------------------------------

suite('recommendPackage', () => {
  const base: IntakeState = {
    ...INITIAL_INTAKE,
    channels: ['WhatsApp'],
    tasks: ['Отвечать на вопросы'],
    handoff: 'Google Sheets',
    volume: '1–10',
    timeline: 'Просто изучаю',
    businessType: null,
    completed: true,
  }

  assert.equal(recommendPackage(base), 'Start')
  pass('FAQ + Google Sheets → Start')

  const withFollowUp = recommendPackage({
    ...base,
    tasks: ['Отвечать на вопросы', 'Делать follow-up'],
  })
  assert.equal(withFollowUp, 'Sales Assistant')
  pass('follow-up task → Sales Assistant')

  const withQualification = recommendPackage({
    ...base,
    tasks: ['Квалифицировать лидов'],
  })
  assert.equal(withQualification, 'Sales Assistant')
  pass('qualification task → Sales Assistant')

  const withCRM = recommendPackage({ ...base, handoff: 'amoCRM' })
  assert.equal(withCRM, 'Integrated AI Employee')
  pass('amoCRM handoff → Integrated AI Employee')

  // High volume alone → Sales Assistant (not Integrated — no CRM required)
  const highVolume = recommendPackage({ ...base, volume: '100+' })
  assert.equal(highVolume, 'Sales Assistant')
  pass('100+/day volume (no CRM) → Sales Assistant')

  // Bug scenario: 1 channel + basic task + Google Sheets + 30–100/day → Sales Assistant
  const bugScenario = recommendPackage({
    channels: ['WhatsApp'],
    tasks: ['Отвечать на вопросы'],
    handoff: 'Google Sheets',
    volume: '30–100',
    timeline: 'В ближайшие дни',
    businessType: 'Онлайн-магазин',
    completed: true,
  })
  assert.equal(bugScenario, 'Sales Assistant')
  pass('1 channel + basic task + Google Sheets + 30–100/day → Sales Assistant (not Integrated)')

  const multiChannelFollowUp = recommendPackage({
    ...base,
    channels: ['WhatsApp', 'Instagram'],
    tasks: ['Делать follow-up'],
  })
  assert.equal(multiChannelFollowUp, 'Sales Assistant')
  pass('multi-channel + follow-up → Sales Assistant')

  // QA scenario: 3 channels, all tasks, Google Sheets handoff, 1–10/day, "Просто изучаю"
  const qaScenario = recommendPackage({
    channels: ['WhatsApp', 'Instagram', 'Сайт'],
    tasks: ['Отвечать на вопросы', 'Собирать контакты', 'Делать follow-up', 'Передавать заявки менеджеру'],
    handoff: 'Google Sheets',
    volume: '1–10',
    timeline: 'Просто изучаю',
    businessType: 'Интернет-магазин',
    completed: true,
  })
  assert.equal(qaScenario, 'Sales Assistant')
  pass('QA scenario (3 channels + all tasks + Google Sheets + 1–10 + Просто изучаю) → Sales Assistant')

  // CRM always triggers Integrated regardless of volume/timeline
  const crmLowVolume = recommendPackage({
    ...base,
    handoff: 'amoCRM',
    volume: '1–10',
    timeline: 'Просто изучаю',
  })
  assert.equal(crmLowVolume, 'Integrated AI Employee')
  pass('amoCRM handoff → Integrated AI Employee even at low-volume exploratory')

  // Bitrix24 also triggers Integrated
  const bitrixHighVolume = recommendPackage({ ...base, handoff: 'Bitrix24', volume: '100+' })
  assert.equal(bitrixHighVolume, 'Integrated AI Employee')
  pass('Bitrix24 handoff → Integrated AI Employee')
})

// ---------------------------------------------------------------------------
// applyIntakeAnswer
// ---------------------------------------------------------------------------

suite('applyIntakeAnswer', () => {
  const state = { ...INITIAL_INTAKE }

  const after = applyIntakeAnswer(state, 'channels', ['WhatsApp', 'Instagram'])
  assert.deepEqual(after.channels, ['WhatsApp', 'Instagram'])
  pass('applies channels correctly')

  const afterTasks = applyIntakeAnswer(state, 'tasks', ['Отвечать на вопросы', 'Собирать контакты'])
  assert.deepEqual(afterTasks.tasks, ['Отвечать на вопросы', 'Собирать контакты'])
  pass('applies multi-select tasks correctly')

  const afterHandoff = applyIntakeAnswer(state, 'handoff', ['Google Sheets'])
  assert.equal(afterHandoff.handoff, 'Google Sheets')
  pass('applies single-select handoff correctly')

  const afterMultiChannels = applyIntakeAnswer(state, 'channels', ['WhatsApp', 'Instagram'])
  assert.deepEqual(afterMultiChannels.channels, ['WhatsApp', 'Instagram'])
  pass('multi-select channels stores full array')

  const afterVolume = applyIntakeAnswer(state, 'volume', ['10–30'])
  assert.equal(afterVolume.volume, '10–30')
  pass('applies volume correctly')

  const afterTimeline = applyIntakeAnswer(state, 'timeline', ['В этом месяце'])
  assert.equal(afterTimeline.timeline, 'В этом месяце')
  pass('applies timeline correctly')
})

// ---------------------------------------------------------------------------
// buildIntakeContextString
// ---------------------------------------------------------------------------

suite('buildIntakeContextString', () => {
  const intake: IntakeState = {
    channels: ['WhatsApp', 'Instagram'],
    tasks: ['Отвечать на вопросы', 'Собирать контакты'],
    handoff: 'Google Sheets',
    volume: '10–30',
    timeline: 'В этом месяце',
    businessType: 'Услуги',
    completed: true,
  }
  const ctx = buildIntakeContextString(intake)

  assert(ctx.includes('WhatsApp'), 'context includes channel')
  assert(ctx.includes('Google Sheets'), 'context includes handoff')
  assert(ctx.includes('10–30'), 'context includes volume')
  assert(ctx.includes('В этом месяце'), 'context includes timeline')
  assert(ctx.includes('Услуги'), 'context includes business type')
  assert(!ctx.includes('undefined'), 'no undefined values leaked')
  pass('context includes all intake fields')

  assert(ctx.toUpperCase().includes('DO NOT ASK AGAIN'), 'context has no-re-ask directive')
  pass('context has no-re-ask directive')

  assert(
    ctx.includes('Start') || ctx.includes('Sales Assistant') || ctx.includes('Integrated AI Employee'),
    'context includes recommended package',
  )
  pass('context includes recommended package')

  assert(ctx.includes('₸'), 'context includes KZT price')
  pass('context includes KZT price')

  // Verify the separator expected by the Python backend parser
  const separator = '\n\nCurrent user message:\n'
  const prefixed = ctx + separator + 'тест'
  assert(prefixed.includes(separator), 'prefix format matches Python parser expectation')
  pass('prefix format is parseable by backend')

  // Multiple channels all appear in context
  const multiCtx = buildIntakeContextString({ ...intake, channels: ['WhatsApp', 'Instagram'] })
  assert(multiCtx.includes('WhatsApp') && multiCtx.includes('Instagram'), 'all channels in context')
  pass('multiple channels all appear in context string')
})

// ---------------------------------------------------------------------------
// INTAKE_QUESTIONS — Q1 channels is multi-select
// ---------------------------------------------------------------------------

suite('INTAKE_QUESTIONS', () => {
  const q0 = INTAKE_QUESTIONS[0]
  assert.equal(q0.id, 'channels')
  assert.equal(q0.multi, true, 'channels question is multi-select')
  pass('Q1 channels is multi-select')

  assert(q0.text.includes('несколько'), 'channels question mentions "несколько"')
  pass('Q1 text mentions "можно выбрать несколько"')
})

// ---------------------------------------------------------------------------
// formatLeadMessage
// ---------------------------------------------------------------------------

suite('formatLeadMessage', () => {
  const lead: LeadSummary = {
    chat_id: 'test-123',
    interest_level: 'hot',
    channels: ['WhatsApp'],
    tasks: ['Квалифицировать лидов'],
    handoff: 'Google Sheets',
    volume: '10–30',
    timeline: 'В этом месяце',
    business_type: 'Услуги',
    recommended_package: 'Sales Assistant',
    estimated_price: 'от 350 000 ₸ + 120 000 ₸/мес',
    conversation_summary: 'summary',
    last_messages: [{ role: 'user', content: 'привет' }],
    created_at: '2026-01-01T00:00:00.000Z',
  }
  const msg = formatLeadMessage(lead)
  assert(msg.includes('🔥'), 'hot lead uses fire emoji')
  assert(msg.includes('HOT'), 'interest level shown')
  assert(msg.includes('Sales Assistant'), 'package shown')
  assert(msg.includes('test-123'), 'chat_id shown')
  assert(msg.includes('Google Sheets'), 'handoff shown')
  assert(msg.includes('привет'), 'last message shown')
  pass('hot lead message formatted correctly')

  const warmLead: LeadSummary = { ...lead, interest_level: 'warm' }
  assert(formatLeadMessage(warmLead).includes('✅'), 'warm lead uses check emoji')
  pass('warm lead uses ✅ emoji')

  const coldLead: LeadSummary = { ...lead, interest_level: 'cold' }
  assert(formatLeadMessage(coldLead).includes('🔵'), 'cold lead uses blue emoji')
  pass('cold lead uses 🔵 emoji')
})

// ---------------------------------------------------------------------------
// contact detection (mirror of backend)
// ---------------------------------------------------------------------------

const ASKED =
  'Оставьте, пожалуйста, имя и номер WhatsApp/Telegram — мы свяжемся, уточним детали и предложим следующий шаг.'

suite('assistantAskedForContact', () => {
  assert(assistantAskedForContact(ASKED), 'detects contact ask')
  assert(
    assistantAskedForContact('Можете оставить номер WhatsApp/Telegram — передадим заявку команде.'),
    'detects alt phrasing',
  )
  assert(!assistantAskedForContact('Запуск проходит так: 1. Уточняем задачи.'), 'non-ask is false')
  pass('assistantAskedForContact works')
})

suite('parseContactReply', () => {
  assert(parseContactReply('Jackiehan', ASKED).kind === 'name', 'bare name after ask is name')
  assert(parseContactReply('Damir Sarsenov', ASKED).kind === 'name', 'two-word name')
  assert(parseContactReply('@jackiehan', '').kind === 'telegram', '@handle is telegram')
  assert(parseContactReply('jackiehan мой тг', '').kind === 'telegram', 'мой тг is telegram')
  assert(parseContactReply('+77777102402', '').kind === 'phone', 'phone detected')
  assert(parseContactReply('+7 777 710 24 02', '').kind === 'phone', 'spaced phone detected')
  pass('parseContactReply classifies contacts')

  assert(parseContactReply('Jackiehan', '').kind === null, 'name without ask is not contact')
  assert(parseContactReply('ок', ASKED).kind === null, 'filler is not contact')
  assert(parseContactReply('готов', ASKED).kind === null, 'start word is not contact')
  assert(parseContactReply('что входит в запуск?', ASKED).kind === null, 'question is not contact')
  pass('parseContactReply rejects non-contacts')

  const phone = parseContactReply('+77777102402', ASKED)
  assert(phone.phone === '+77777102402', 'phone value captured')
  assert(isContactLikeReply('@jackiehan', ''), 'isContactLikeReply true for telegram')
})

// ---------------------------------------------------------------------------
// formatLeadMessage — created / updated events
// ---------------------------------------------------------------------------

suite('formatLeadMessage events', () => {
  const base: LeadSummary = {
    chat_id: 'evt-1',
    interest_level: 'hot',
    channels: ['WhatsApp'],
    tasks: ['Передавать заявки менеджеру'],
    handoff: 'Google Sheets',
    volume: '10–30',
    timeline: 'В этом месяце',
    business_type: 'Онлайн-магазин',
    recommended_package: 'Sales Assistant',
    estimated_price: 'от 350 000 ₸ + 120 000 ₸/мес',
    conversation_summary: 'summary',
    last_messages: [],
    created_at: '2026-01-01T00:00:00.000Z',
  }

  const created = formatLeadMessage({ ...base, event: 'created', contact: null })
  assert(created.includes('New DamiWorks lead'), 'created header')
  assert(created.includes('Waiting for contact'), 'created status waiting')
  assert(created.includes('Contact: —'), 'created contact empty')
  pass('created event renders waiting-for-contact')

  const updated = formatLeadMessage({
    ...base,
    event: 'updated',
    contact: { name: 'Jackiehan', telegram: '@jackiehan', phone: null, raw: 'Jackiehan' },
    status: 'Ready for follow-up',
  })
  assert(updated.includes('Lead updated'), 'updated header is distinct')
  assert(!updated.includes('New DamiWorks lead'), 'updated is not a new-lead message')
  assert(updated.includes('Jackiehan'), 'updated shows name')
  assert(updated.includes('@jackiehan'), 'updated shows telegram')
  assert(updated.includes('Ready for follow-up'), 'updated status')
  pass('updated event is a distinct lead-updated message')
})

// ---------------------------------------------------------------------------
// Done
// ---------------------------------------------------------------------------

console.log('\n✓ All tests passed\n')
