'use client'

import { useEffect, useRef, useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import type { DictLaunch } from '@/lib/i18n'

// One section that closes one question: "How do we start?" Re-told as a
// scroll story: a vertical timeline of the three steps (highlighted while
// scrolling) with a sticky «От клиники нужно только это» panel beside it,
// then what we track after launch, then the price + CTA (id="pricing").
export default function LaunchSection({ dict, demoHref = '#demo' }: { dict: DictLaunch; demoHref?: string }) {
  const [activeStep, setActiveStep] = useState(0)
  const stepRefs = useRef<Array<HTMLLIElement | null>>([])

  // A step lights up while it crosses the middle band of the viewport.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setActiveStep(dict.steps.length - 1)
      return
    }
    const steps = stepRefs.current.filter((el): el is HTMLLIElement => el !== null)
    if (steps.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const idx = steps.indexOf(entry.target as HTMLLIElement)
          if (idx >= 0) setActiveStep(idx)
        }
      },
      { rootMargin: '-40% 0px -45% 0px' }
    )
    steps.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [dict.steps.length])

  return (
    <section className="border-t border-border-col bg-bg py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 text-lg leading-relaxed text-secondary">{dict.subheadline}</p>
        </div>

        {/* Timeline + sticky need-panel */}
        <div className="mt-12 grid grid-cols-1 gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:gap-14">
          <ol className="space-y-2">
            {dict.steps.map((step, index) => {
              const reached = index <= activeStep
              return (
                <li
                  key={step.number}
                  ref={(el) => {
                    stepRefs.current[index] = el
                  }}
                  className="grid grid-cols-[auto_1fr] gap-x-4"
                >
                  {/* Marker + connector segment */}
                  <div className="flex flex-col items-center">
                    <span
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-colors duration-500 ${
                        reached
                          ? 'border-accent bg-accent text-white'
                          : 'border-border-col bg-surface text-secondary'
                      }`}
                    >
                      {step.number}
                    </span>
                    {index < dict.steps.length - 1 && (
                      <span
                        aria-hidden="true"
                        className={`w-px flex-1 transition-colors duration-500 ${
                          index < activeStep ? 'bg-accent' : 'bg-border-col'
                        }`}
                      />
                    )}
                  </div>

                  <div
                    className={`pb-8 transition-opacity duration-500 motion-reduce:transition-none ${
                      reached ? 'opacity-100' : 'opacity-45'
                    }`}
                  >
                    <h3 className="pt-1.5 text-lg font-bold text-primary">{step.title}</h3>
                    <p className="mt-2 max-w-lg text-sm leading-relaxed text-secondary">{step.description}</p>
                  </div>
                </li>
              )
            })}
          </ol>

          <div>
            <div className="rounded-2xl border border-border-col bg-surface p-6 lg:sticky lg:top-24">
              <h3 className="font-bold text-primary">{dict.needTitle}</h3>
              <ul className="mt-4 space-y-2.5">
                {dict.needItems.map((item) => (
                  <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-primary">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* What we track after launch */}
        <div className="mt-14">
          <h3 className="font-bold text-primary">{dict.measuresTitle}</h3>
          <ul className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
            {dict.measures.map((measure) => (
              <li key={measure} className="flex gap-2.5 text-sm leading-relaxed text-primary">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                <span>{measure}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Price + CTA */}
        <div id="pricing" className="mt-10 scroll-mt-24 rounded-2xl border border-accent/25 bg-accent-soft/45 p-6 lg:p-8">
          <div className="grid grid-cols-1 items-center gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <p className="text-2xl font-bold text-primary">{dict.pricingLine}</p>
              <p className="mt-2 text-sm leading-relaxed text-secondary">{dict.priceNote}</p>
            </div>
            <div className="flex flex-col gap-2.5">
              <a
                href="#contact"
                className="inline-flex min-h-12 items-center justify-center rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              >
                {dict.ctaPrimary}
              </a>
              <a
                href={demoHref}
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
