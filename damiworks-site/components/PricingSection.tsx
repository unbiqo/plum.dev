import { Check } from 'lucide-react'
import type { DictPricing } from '@/lib/i18n'

export default function PricingSection({ dict }: { dict: DictPricing }) {
  return (
    <section id="pricing" className="scroll-mt-20 py-24 bg-surface border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-3">{dict.headline}</h2>
          <p className="text-secondary text-lg">{dict.subheadline}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {dict.plans.map((plan) => (
            <div
              key={plan.id}
              className={`relative bg-bg rounded-2xl p-8 flex flex-col ${
                plan.highlighted
                  ? 'border-2 border-accent shadow-md'
                  : 'border border-border-col'
              }`}
            >
              {plan.badge && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                  <span className="bg-accent text-white text-xs font-semibold px-3 py-1 rounded-full whitespace-nowrap">
                    {plan.badge}
                  </span>
                </div>
              )}

              <h3 className="text-xl font-bold text-primary mb-1">{plan.name}</h3>
              <p className="text-secondary text-sm mb-6">{plan.description}</p>

              <div className="mb-6 pb-6 border-b border-border-col">
                <div className="text-xl font-bold text-primary">{plan.priceSetup}</div>
                <div className="text-sm font-medium mt-1.5 text-accent">
                  {plan.priceMonthly}
                </div>
                {plan.priceMonthlyDetail && (
                  <div className="text-xs text-secondary mt-0.5">{plan.priceMonthlyDetail}</div>
                )}
              </div>

              <ul className="space-y-2.5 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-secondary">
                    <Check size={15} className="text-accent mt-0.5 flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>

              {plan.supportNote && (
                <div className="mt-5 pt-4 border-t border-border-col">
                  <p className="text-xs text-secondary leading-relaxed">{plan.supportNote}</p>
                </div>
              )}

              {plan.limitNote && (
                <p className="text-xs text-secondary/60 mt-2 leading-relaxed">{plan.limitNote}</p>
              )}

              {plan.reassurance && (
                <p className="text-xs text-accent/80 mt-3 leading-relaxed">{plan.reassurance}</p>
              )}

              <a
                href="#contact"
                className={`mt-6 text-center py-3 rounded-xl font-medium text-sm transition-colors block ${
                  plan.highlighted
                    ? 'bg-accent text-white hover:opacity-90'
                    : 'border border-border-col text-primary hover:bg-surface'
                }`}
              >
                {plan.cta}
              </a>
            </div>
          ))}
        </div>

        <p className="text-center text-sm text-secondary mt-8">{dict.note}</p>
      </div>
    </section>
  )
}
