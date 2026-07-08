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
pass('specialty labels normalize to Russian')

// Symptom EN -> RU.
const complaint = normalizeComplaint('headache and fever')
assert.ok(complaint.includes('головная боль'), 'headache -> головная боль')
assert.ok(complaint.includes('температура'), 'fever -> температура')
pass('symptom labels normalize to Russian')

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
