import { CheckCircle2 } from 'lucide-react'
import type { DictLaunch } from '@/lib/i18n'

// One section that closes one question: "How do we start?" Strict hierarchy:
// scoping → turnkey setup → improvements on real dialogs → what we track →
// price → CTA. Replaces the former Pricing (pilot offer), ValueProp and
// WhatWeNeed sections on the RU page.
export default function LaunchSection({ dict }: { dict: DictLaunch }) {
  return (
    <section id="pricing" className="scroll-mt-20 border-t border-border-col bg-bg py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 text-lg leading-relaxed text-secondary">{dict.subheadline}</p>
        </div>

        {/* Steps: scoping → turnkey setup → real-dialog improvements */}
        <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-3">
          {dict.steps.map((step) => (
            <article key={step.number} className="rounded-2xl border border-border-col bg-surface p-6">
              <span className="text-xs font-bold uppercase tracking-wider text-accent">{step.number}</span>
              <h3 className="mt-3 text-lg font-bold text-primary">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-secondary">{step.description}</p>
            </article>
          ))}
        </div>

        {/* Tracking + what we need + price + CTA in one closing container */}
        <div className="mt-6 grid grid-cols-1 gap-8 rounded-2xl border border-border-col bg-surface p-6 lg:grid-cols-[1.15fr_0.85fr] lg:p-8">
          <div>
            <h3 className="font-bold text-primary">{dict.measuresTitle}</h3>
            <ul className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {dict.measures.map((measure) => (
                <li key={measure} className="flex gap-2.5 text-sm leading-relaxed text-primary">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                  <span>{measure}</span>
                </li>
              ))}
            </ul>

            <h3 className="mt-8 font-bold text-primary">{dict.needTitle}</h3>
            <ul className="mt-3 flex flex-wrap gap-2">
              {dict.needItems.map((item) => (
                <li
                  key={item}
                  className="rounded-full border border-border-col bg-bg px-3.5 py-1.5 text-sm text-secondary"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col justify-center rounded-2xl border border-accent/25 bg-accent-soft/45 p-6">
            <p className="text-2xl font-bold text-primary">{dict.pricingLine}</p>
            <p className="mt-2 text-sm leading-relaxed text-secondary">{dict.priceNote}</p>
            <div className="mt-6 flex flex-col gap-2.5">
              <a
                href="#contact"
                className="inline-flex min-h-12 items-center justify-center rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              >
                {dict.ctaPrimary}
              </a>
              <a
                href="#demo"
                className="inline-flex min-h-12 items-center justify-center rounded-xl border border-border-col bg-surface px-6 py-3 text-sm font-medium text-primary transition-colors hover:bg-bg"
              >
                {dict.ctaSecondary}
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
