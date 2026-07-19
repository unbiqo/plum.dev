import type { CSSProperties } from 'react'
import { CheckCircle2 } from 'lucide-react'
import type { DictAdminHandoff } from '@/lib/i18n'
import StaggerReveal from '@/components/StaggerReveal'

// The single dark section on the page — a deliberate visual break in the light
// rhythm, placed at the most selling moment: what the administrator actually
// receives after a dialog. Static mock card, no fake interactive buttons.
export default function AdminHandoffSection({ dict }: { dict: DictAdminHandoff }) {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-t border-border-col bg-primary py-20 lg:py-24">
      <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-6 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Left: the claim */}
        <div>
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-accent">
            {dict.eyebrow}
          </p>
          <h2 className="text-3xl font-bold leading-tight text-white lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 max-w-xl text-lg leading-relaxed text-white/70">{dict.subheadline}</p>
          <ul className="mt-7 space-y-3.5">
            {dict.points.map((point) => (
              <li key={point} className="flex gap-3 text-sm leading-relaxed text-white/85">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Right: the request card, mini-CRM style — fields cascade in like a live заявка filling up.
            Slower stagger step than the default: the card should visibly assemble field by field. */}
        <StaggerReveal className="[--stagger-step:340ms]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-6 lg:p-7">
            <div className="mb-5 flex items-center gap-2">
              <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-green-500" aria-hidden="true" />
              <span className="text-sm font-semibold text-white">{dict.card.title}</span>
            </div>

            <dl className="space-y-4">
              {dict.card.fields.map((field, index) => (
                <div key={field.label} data-stagger-item style={{ '--stagger-i': index } as CSSProperties}>
                  <dt className="mb-0.5 text-xs uppercase tracking-wider text-white/45">{field.label}</dt>
                  <dd className="text-sm font-medium text-white/90">{field.value}</dd>
                </div>
              ))}
            </dl>

            <div
              data-stagger-item
              style={{ '--stagger-i': dict.card.fields.length } as CSSProperties}
              className="mt-6 rounded-xl border border-accent/30 bg-accent/15 px-3 py-2.5 text-center text-sm font-medium text-accent"
            >
              {dict.card.pill}
            </div>

            <div
              data-stagger-item
              style={{ '--stagger-i': dict.card.fields.length + 1 } as CSSProperties}
              className="mt-4 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3"
            >
              <p className="text-xs uppercase tracking-wider text-white/45">{dict.card.nextStepLabel}</p>
              <p className="mt-1 text-sm leading-relaxed text-white/85">{dict.card.nextStep}</p>
            </div>
          </div>
        </StaggerReveal>
      </div>
    </section>
  )
}
