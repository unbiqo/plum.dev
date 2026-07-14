import { ArrowRight, CheckCircle2, HelpCircle } from 'lucide-react'
import type { DictMessageToLead } from '@/lib/i18n'

// «Один вопрос пациента — два разных процесса»: the same incoming message,
// before and after DamiWorks. Sells structuring the first contact — no timers,
// no scripted animation, no blaming the administrator.
export default function MessageToLeadSection({ dict }: { dict: DictMessageToLead }) {
  return (
    <section className="border-t border-border-col bg-surface py-20">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 text-lg leading-relaxed text-secondary">{dict.subheadline}</p>
        </div>

        <div className="relative mt-12 grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
          {/* Before: the raw incoming message */}
          <article className="flex flex-col rounded-2xl border border-border-col bg-bg p-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-secondary">
              {dict.before.title}
            </h3>
            <div className="mt-5 max-w-[85%] self-start rounded-2xl rounded-tl-sm border border-border-col bg-surface px-4 py-3 text-sm leading-relaxed text-primary">
              {dict.before.patientMessage}
            </div>
            <p className="mt-6 text-sm font-medium text-primary">{dict.before.problemsTitle}</p>
            <ul className="mt-3 space-y-2.5">
              {dict.before.problems.map((problem) => (
                <li key={problem} className="flex gap-2.5 text-sm leading-relaxed text-secondary">
                  <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-secondary/60" aria-hidden="true" />
                  <span>{problem}</span>
                </li>
              ))}
            </ul>
          </article>

          {/* Desktop connector between the two states */}
          <div
            className="pointer-events-none absolute left-1/2 top-1/2 z-10 hidden h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border-col bg-surface text-accent shadow-sm md:flex"
            aria-hidden="true"
          >
            <ArrowRight size={18} />
          </div>

          {/* After: the structured request */}
          <article className="flex flex-col rounded-2xl border border-accent/30 bg-accent-soft/40 p-6">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-accent">
              {dict.after.title}
            </h3>
            <dl className="mt-5 space-y-3.5">
              {dict.after.fields.map((field) => (
                <div key={field.label}>
                  <dt className="mb-0.5 text-xs uppercase tracking-wider text-secondary">{field.label}</dt>
                  <dd className="flex items-center gap-1.5 text-sm font-medium text-primary">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
                    {field.value}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-6 rounded-xl border border-accent/25 bg-surface px-4 py-3">
              <p className="text-xs uppercase tracking-wider text-secondary">{dict.after.nextStepLabel}</p>
              <p className="mt-1 text-sm font-medium text-primary">{dict.after.nextStep}</p>
            </div>
          </article>
        </div>
      </div>
    </section>
  )
}
