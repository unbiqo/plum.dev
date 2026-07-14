import type { CSSProperties } from 'react'
import { ShieldCheck } from 'lucide-react'
import type { DictSafetyFlow } from '@/lib/i18n'
import StaggerReveal from '@/components/StaggerReveal'

// Fixed tones by state order: answers (green), clarifies (amber), hands off
// (brand accent — a deliberate feature, not a fail state, so no alarm red).
const STATE_TONES = [
  { edge: 'border-l-green-500', dot: 'bg-green-500' },
  { edge: 'border-l-amber-400', dot: 'bg-amber-400' },
  { edge: 'border-l-accent', dot: 'bg-accent' },
]

// «AI знает, где отвечать, а где передать человеку» — a decision flow of three
// states instead of a checklist grid. Replaces TrustSection on the RU page.
export default function SafetyFlowSection({ dict }: { dict: DictSafetyFlow }) {
  return (
    <section id="trust" className="scroll-mt-20 border-t border-border-col bg-bg py-20">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-6 lg:grid-cols-[1fr_1.1fr] lg:items-center lg:gap-14">
        {/* Left: the claim + guarantees */}
        <div>
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 leading-relaxed text-secondary">{dict.subheadline}</p>
          <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2">
            {dict.guarantees.map((guarantee) => (
              <li key={guarantee} className="flex items-center gap-1.5 text-sm font-medium text-primary">
                <ShieldCheck size={15} className="shrink-0 text-accent" aria-hidden="true" />
                {guarantee}
              </li>
            ))}
          </ul>
        </div>

        {/* Right: the decision card — three states, cascading in */}
        <StaggerReveal>
          <div className="space-y-3">
            {dict.states.map((state, index) => {
              const tone = STATE_TONES[index] ?? STATE_TONES[STATE_TONES.length - 1]
              return (
                <div
                  key={state.title}
                  data-stagger-item
                  style={{ '--stagger-i': index } as CSSProperties}
                  className={`rounded-2xl border border-border-col border-l-4 bg-surface p-5 ${tone.edge}`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${tone.dot}`} aria-hidden="true" />
                    <h3 className="font-semibold text-primary">{state.title}</h3>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-secondary">{state.description}</p>
                  {state.note && (
                    <p className="mt-2 text-xs leading-relaxed text-secondary/80">{state.note}</p>
                  )}
                </div>
              )
            })}
          </div>
        </StaggerReveal>
      </div>
    </section>
  )
}
