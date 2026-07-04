// Tests for lib/freeform.ts — free-form intake extraction, merge behavior,
// and quick-reply chip dismissal. Run with: npx tsx tests/freeform.test.ts

import {
  extractFreeformIntake,
  filterUnusedChips,
  hasFreeformSummary,
  mergeFreeformIntake,
} from '../lib/freeform'
import { INITIAL_INTAKE, recommendPackage, type IntakeState } from '../lib/intake'

let failures = 0

function check(name: string, cond: boolean) {
  if (cond) {
    console.log(`  ✓ ${name}`)
  } else {
    failures += 1
    console.error(`  ✗ ${name}`)
  }
}

// The dental transcript's user messages, verbatim.
const DENTAL_TEXTS = [
  'здравствуйте, у меня своя стоматологи и мне нужно отвечать на вопросы клиентов и назначать appointment. вы можете такое сделать?',
  'мне клиенты пишут в ватсап. Трафик приходит с инстаграм, 2гис и сайта.',
  '1с',
]

console.log('\nextractFreeformIntake')
{
  const ex = extractFreeformIntake(DENTAL_TEXTS)
  check(
    'dental transcript extracts channels WhatsApp/Instagram/2GIS/Website',
    ['WhatsApp', 'Instagram', '2GIS', 'Website'].every((c) => ex.channels.includes(c)),
  )
  check('dental transcript extracts answering + booking tasks',
    ex.tasks.includes('Отвечать на вопросы') && ex.tasks.includes('Запись клиентов'))
  check('dental transcript extracts 1С handoff', ex.handoff === '1С')
  check('dental transcript extracts dental business type', ex.businessType === 'Стоматология')

  const empty = extractFreeformIntake(['привет', 'как дела?'])
  check('smalltalk extracts nothing', empty.channels.length === 0 && empty.tasks.length === 0)
}

console.log('\nmergeFreeformIntake')
{
  const ex = extractFreeformIntake(DENTAL_TEXTS)
  const merged = mergeFreeformIntake(INITIAL_INTAKE, ex)
  check('summary is no longer empty without the questionnaire', hasFreeformSummary(merged))
  check('completed flag untouched', merged.completed === false)
  check('recommendation derivable from free-form state', ['Start', 'Sales Assistant', 'Integrated AI Employee'].includes(recommendPackage(merged)))

  // Questionnaire answers always win over extraction.
  const answered: IntakeState = { ...INITIAL_INTAKE, channels: ['Telegram'], handoff: 'amoCRM' }
  const merged2 = mergeFreeformIntake(answered, ex)
  check('questionnaire channels win over extraction', merged2.channels.join(',') === 'Telegram')
  check('questionnaire handoff wins over extraction', merged2.handoff === 'amoCRM')
  check('extraction fills fields the questionnaire left empty', merged2.tasks.length > 0)

  // Completed intake is never modified.
  const done: IntakeState = { ...INITIAL_INTAKE, completed: true }
  check('completed intake never modified', mergeFreeformIntake(done, ex) === done)
}

console.log('\nfilterUnusedChips')
{
  const chips = ['Подобрать AI-сотрудника', 'Сколько стоит?', 'Как это работает?', 'Чем отличается от чат-бота?']
  const after = filterUnusedChips(chips, ['Сколько стоит?'])
  check('clicked chip disappears', !after.includes('Сколько стоит?'))
  check('other chips remain', after.length === 3 && after.includes('Как это работает?'))
  check('no clicks — all chips visible', filterUnusedChips(chips, []).length === 4)
  check('all clicked — none visible', filterUnusedChips(chips, chips).length === 0)
}

if (failures > 0) {
  console.error(`\n${failures} freeform test(s) failed.`)
  process.exit(1)
}
console.log('\nAll freeform tests passed.')
