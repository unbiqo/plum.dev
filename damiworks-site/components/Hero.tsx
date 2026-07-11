import type { DictHero } from '@/lib/i18n'
import HeroChatPreview from '@/components/HeroChatPreview'
import { Check } from 'lucide-react'

export default function Hero({ dict }: { dict: DictHero }) {
  return (
    <section className="bg-bg py-20 lg:py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* Left column */}
          <div>
            {dict.eyebrow && (
              <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-accent">
                {dict.eyebrow}
              </p>
            )}
            <h1 className="text-4xl lg:text-5xl font-bold text-primary leading-tight mb-5">
              {dict.headlinePart1}
              <span className="text-accent">{dict.headlineAccent}</span>
            </h1>
            <p className="text-lg text-secondary leading-relaxed mb-8 max-w-md">
              {dict.subheadline}
            </p>
            <div className="flex flex-wrap gap-3 mb-3">
              <a
                href={dict.ctaPrimary.href}
                className="inline-flex items-center bg-accent text-white font-medium px-6 py-3 rounded-xl hover:opacity-90 transition-opacity"
              >
                {dict.ctaPrimary.label}
              </a>
              <a
                href={dict.ctaSecondary.href}
                className="inline-flex items-center bg-surface text-primary font-medium px-6 py-3 rounded-xl border border-border-col hover:bg-bg transition-colors"
              >
                {dict.ctaSecondary.label}
              </a>
            </div>
            {dict.trustBadges.length > 0 && (
              <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2">
                {dict.trustBadges.map((badge) => (
                  <li key={badge} className="flex items-center gap-1.5 text-xs font-medium text-secondary">
                    <Check size={14} className="text-accent" aria-hidden="true" />
                    {badge}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Right column — animated chat preview */}
          <HeroChatPreview dict={dict.chat} />

        </div>
      </div>
    </section>
  )
}
