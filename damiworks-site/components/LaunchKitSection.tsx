import type { CSSProperties } from 'react'
import { ArrowDown, ArrowRight } from 'lucide-react'
import type { DictLaunchKit } from '@/lib/i18n'
import StaggerReveal from '@/components/StaggerReveal'

function staggerStyle(index: number): CSSProperties {
  return { '--stagger-i': index } as CSSProperties
}

function SideZone({
  zone,
  index,
}: {
  zone: { title: string; items: string[] }
  index: number
}) {
  return (
    <div
      data-stagger-item
      style={staggerStyle(index)}
      className="rounded-2xl border border-border-col bg-bg p-6"
    >
      <h3 className="text-sm font-semibold uppercase tracking-wider text-secondary">{zone.title}</h3>
      <ul className="mt-4 flex flex-wrap gap-2 lg:flex-col lg:items-start">
        {zone.items.map((item) => (
          <li
            key={item}
            className="rounded-full border border-border-col bg-surface px-3.5 py-1.5 text-sm font-medium text-primary"
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Connector({ index }: { index: number }) {
  return (
    <div
      data-stagger-item
      style={staggerStyle(index)}
      className="flex items-center justify-center py-1 text-accent lg:px-2"
      aria-hidden="true"
    >
      <ArrowDown size={20} className="lg:hidden" />
      <ArrowRight size={20} className="hidden lg:block" />
    </div>
  )
}

// «Что входит в запуск» as a systems diagram, not a card grid: incoming
// channels → the AI core → the ready request. The core zone deliberately
// dominates (denser background, thicker border, larger column) — it is the
// product being bought.
export default function LaunchKitSection({ dict }: { dict: DictLaunchKit }) {
  return (
    <section className="border-t border-border-col bg-surface py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 text-lg leading-relaxed text-secondary">{dict.subheadline}</p>
        </div>

        <StaggerReveal className="mt-12">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1.45fr_auto_1fr] lg:items-center lg:gap-0">
            <SideZone zone={dict.channels} index={0} />
            <Connector index={1} />

            {/* Core zone — visually dominant */}
            <div
              data-stagger-item
              style={staggerStyle(2)}
              className="rounded-2xl border-2 border-accent/40 bg-gradient-to-b from-accent-soft/70 via-accent-soft/35 to-surface p-6 shadow-lg shadow-accent/10 lg:p-7"
            >
              <h3 className="text-lg font-bold text-primary">{dict.core.title}</h3>
              <div className="mt-4 space-y-3">
                {dict.core.layers.map((layer) => (
                  <div key={layer.title} className="rounded-xl border border-accent/20 bg-surface/90 p-4">
                    <p className="text-sm font-semibold text-primary">{layer.title}</p>
                    <p className="mt-1 text-sm leading-relaxed text-secondary">{layer.text}</p>
                  </div>
                ))}
              </div>
            </div>

            <Connector index={3} />
            <SideZone zone={dict.handoff} index={4} />
          </div>
        </StaggerReveal>
      </div>
    </section>
  )
}
