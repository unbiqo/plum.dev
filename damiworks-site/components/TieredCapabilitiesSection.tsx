import type { DictCapabilities } from '@/lib/i18n'

const TIER_TOP_BORDER = [
  'border-t-[3px] border-t-border-col',
  'border-t-[3px] border-t-accent/50',
  'border-t-[3px] border-t-accent',
]

const TIER_NUMBER_COLOR = [
  'text-secondary/30',
  'text-accent/30',
  'text-accent/50',
]

export default function TieredCapabilitiesSection({ dict }: { dict: DictCapabilities }) {
  return (
    <section className="py-24 bg-surface border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-3">{dict.headline}</h2>
          <p className="text-secondary text-lg max-w-2xl mx-auto">{dict.subheadline}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {dict.tiers.map((tier, idx) => (
            <div
              key={tier.id}
              className={`bg-bg rounded-2xl p-6 flex flex-col border border-border-col ${TIER_TOP_BORDER[idx]}`}
            >
              {/* Number */}
              <div className={`text-5xl font-bold leading-none mb-3 ${TIER_NUMBER_COLOR[idx]}`}>
                {tier.number}
              </div>

              {/* Name */}
              <h3 className="text-lg font-bold text-primary mb-1">{tier.name}</h3>

              {/* Tagline */}
              <p className="text-sm text-secondary mb-5 pb-5 border-b border-border-col leading-relaxed">
                {tier.tagline}
              </p>

              {/* Feature list */}
              <ul className="space-y-3.5 flex-1">
                {tier.features.map((feature) => (
                  <li key={feature.name} className="flex items-start gap-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent/40 flex-shrink-0 mt-1.5" />
                    <div>
                      <div className="text-sm font-semibold text-primary">{feature.name}</div>
                      <div className="text-xs text-secondary mt-0.5 leading-relaxed">
                        {feature.description}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>

              {/* Footer */}
              <div className="mt-6 pt-4 border-t border-border-col">
                <p className="text-xs text-secondary leading-relaxed">{tier.footerText}</p>
              </div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="text-center mt-12">
          <p className="text-sm text-secondary mb-4">{dict.cta}</p>
          <a
            href="#demo"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-accent border border-accent/30 bg-accent-soft/40 hover:bg-accent-soft px-5 py-2.5 rounded-xl transition-colors"
          >
            {dict.ctaLink}
          </a>
        </div>
      </div>
    </section>
  )
}
