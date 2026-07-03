/**
 * Unit tests for the Calendly CTA helper + related copy invariants.
 * Run with: npx tsx tests/calendly.test.ts
 * No test framework required — uses Node built-in assert.
 */
import assert from 'node:assert/strict'

import { resolveCalendlyUrl } from '../lib/calendly'
import { dictionaries } from '../lib/i18n'

function pass(name: string) {
  console.log(`  ✓ ${name}`)
}

function suite(name: string, fn: () => void) {
  console.log(`\n${name}`)
  fn()
}

// ---------------------------------------------------------------------------

suite('resolveCalendlyUrl', () => {
  assert.equal(resolveCalendlyUrl(undefined), null)
  assert.equal(resolveCalendlyUrl(null), null)
  assert.equal(resolveCalendlyUrl(''), null)
  assert.equal(resolveCalendlyUrl('   '), null)
  pass('missing/empty env var resolves to null (CTA hidden)')

  assert.equal(resolveCalendlyUrl('calendly.com/damir'), null)
  pass('non-http(s) value resolves to null (no broken CTA)')

  assert.equal(
    resolveCalendlyUrl('https://calendly.com/damir/20min'),
    'https://calendly.com/damir/20min',
  )
  assert.equal(
    resolveCalendlyUrl('  https://calendly.com/damir/20min  '),
    'https://calendly.com/damir/20min',
  )
  pass('valid URL is returned trimmed (CTA shown)')
})

suite('Calendly CTA copy', () => {
  for (const locale of ['en', 'ru'] as const) {
    const dict = dictionaries[locale]
    assert.ok(dict.liveChat.bookCallButton.length > 0, `${locale}: chat book-call label present`)
    assert.ok(dict.liveChat.leaveContactButton.length > 0, `${locale}: chat leave-contact label present`)
    assert.ok(dict.contact.calendlyButton.length > 0, `${locale}: contact section CTA label present`)
    assert.ok(dict.contact.calendlySubtext.length > 0, `${locale}: contact section subtext present`)

    // Discovery mode: none of the new DamiWorks CTA copy may leak package prices.
    const newCopy = [
      dict.liveChat.bookCallButton,
      dict.liveChat.leaveContactButton,
      dict.contact.headline,
      dict.contact.calendlyButton,
      dict.contact.calendlySubtext,
    ].join(' ')
    assert.ok(!/₸|тенге|KZT|\d{3}\s?\d{3}/i.test(newCopy), `${locale}: no prices in Calendly CTA copy`)
  }
  pass('labels exist in both locales and contain no DamiWorks prices')
})

console.log('\nAll calendly tests passed.')
