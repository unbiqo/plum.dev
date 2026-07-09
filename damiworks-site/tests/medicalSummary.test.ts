/**
 * MedNova summary-panel normalization + demo order.
 * Run with: npx tsx tests/medicalSummary.test.ts
 */
import assert from 'node:assert/strict'
import { getDict, type Locale } from '../lib/i18n'
import { normalizeSpecialty, normalizeComplaint } from '../lib/medicalSummary'

function pass(name: string) {
  console.log(`  ✓ ${name}`)
}

console.log('\nmedical summary normalization')

// Specialty EN/RU -> RU label.
assert.equal(normalizeSpecialty('therapist'), 'Терапевт')
assert.equal(normalizeSpecialty('cardiologist'), 'Кардиолог')
assert.equal(normalizeSpecialty('neurologist'), 'Невролог')
assert.equal(normalizeSpecialty('pediatrician'), 'Педиатр')
assert.equal(normalizeSpecialty('dentist'), 'Стоматолог')
assert.equal(normalizeSpecialty('терапевт'), 'Терапевт')
// ENT / lor / otolaryngologist must all render as ЛОР, never English.
assert.equal(normalizeSpecialty('ENT'), 'ЛОР')
assert.equal(normalizeSpecialty('otolaryngologist'), 'ЛОР')
assert.equal(normalizeSpecialty('lor'), 'ЛОР')
// Musculoskeletal specialists render in Russian.
assert.equal(normalizeSpecialty('травматолог-ортопед'), 'Травматолог-ортопед')
assert.equal(normalizeSpecialty('ортопед'), 'Травматолог-ортопед')
assert.equal(normalizeSpecialty('ревматолог'), 'Ревматолог')
pass('specialty labels normalize to Russian (incl. ENT -> ЛОР, ортопед, ревматолог)')

// Symptom EN -> RU.
const complaint = normalizeComplaint('headache and fever')
assert.ok(complaint.includes('головная боль'), 'headache -> головная боль')
assert.ok(complaint.includes('температура'), 'fever -> температура')
const complaint2 = normalizeComplaint('redness and sneezing')
assert.ok(complaint2.includes('покраснение'), 'redness -> покраснение')
assert.ok(complaint2.includes('чихание'), 'sneezing -> чихание')
assert.ok(!/redness|sneezing/i.test(complaint2), 'no English redness/sneezing remains')
pass('symptom labels normalize to Russian (incl. redness/sneezing)')

// No English leaks for known values.
const known = normalizeSpecialty('therapist') + ' ' + normalizeComplaint('headache fever')
assert.ok(!/therapist|headache|fever/i.test(known), 'no English in normalized known values')
pass('no English therapist/headache/fever in RU summary for known values')

// Status labels are Russian.
const ru = getDict('ru').demo.medicalSummary.statusValues
for (const key of ['new_dialog', 'doctor_selection', 'slots_offered', 'awaiting_contact', 'booking_created'] as const) {
  assert.ok(/[а-яё]/i.test(ru[key]), `status ${key} is Russian`)
}
assert.equal(ru.booking_created, 'Запись создана')
assert.equal(ru.slots_offered, 'Предложены окна')
assert.equal(ru.awaiting_contact, 'Ожидает контакт')
pass('status labels are Russian')

// Demo order remains DamiWorks -> Medical Center -> English School.
function visibleOrder(locale: Locale): string[] {
  return getDict(locale).demo.scenarios.filter((s) => !s.hidden).map((s) => s.id)
}
for (const locale of ['ru', 'en'] as const) {
  const order = visibleOrder(locale)
  assert.deepEqual(order, ['damiworks', 'medical', 'english'], `${locale}: demo order`)
}
pass('demo order is DamiWorks, Medical Center, English School')

// English School scenario still present and intact.
for (const locale of ['ru', 'en'] as const) {
  const english = getDict(locale).demo.scenarios.find((s) => s.id === 'english')
  assert.ok(english && english.agentName === 'Alem English Academy', `${locale}: English School intact`)
}
pass('English School scenario unchanged')

console.log('\nAll medicalSummary tests passed.\n')
