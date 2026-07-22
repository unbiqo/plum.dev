/**
 * Data-level tests for the MedNova Clinic demo locale wiring.
 * Run with: npx tsx tests/medicalDemo.test.ts
 */
import assert from 'node:assert/strict'
import { getDict, type Locale } from '../lib/i18n'

const RU_INTRO =
  'Здравствуйте! 💚 Меня зовут Айгуль, я администратор MedNova Clinic. Помогу подобрать врача, сориентировать по стоимости и записать на приём. Подскажите, пожалуйста, пациент взрослый или ребёнок, и что вас беспокоит?'

function pass(name: string) {
  console.log(`  ✓ ${name}`)
}

function checkLocale(locale: Locale) {
  const dict = getDict(locale).demo
  const medical = dict.scenarios.find((s) => s.id === 'medical')
  const english = dict.scenarios.find((s) => s.id === 'english')
  const beauty = dict.scenarios.find((s) => s.id === 'beauty')

  assert.ok(medical, `${locale}: medical scenario exists`)
  assert.equal(medical?.hidden, undefined, `${locale}: medical scenario is visible`)
  assert.equal(medical?.agentName, 'MedNova Clinic', `${locale}: medical agent name`)
  assert.ok(english, `${locale}: English School scenario remains present`)
  assert.equal(beauty?.hidden, true, `${locale}: beauty scenario remains hidden`)
  assert.equal(dict.customDemoTab.id, 'custom_demo', `${locale}: custom demo tab untouched`)
  assert.ok(
    dict.medicalSummary.statusValues.emergency.length > 0,
    `${locale}: emergency status is present`,
  )
}

console.log('\nmedical demo dictionaries')
checkLocale('en')
pass('English dictionary contains visible MedNova Clinic scenario')

checkLocale('ru')
const ruDemo = getDict('ru').demo
assert.equal(ruDemo.medicalChat.introMessage, RU_INTRO, 'ru: intro message matches required copy')
pass('Russian dictionary contains required intro message')

console.log('\nAll medicalDemo tests passed.\n')
