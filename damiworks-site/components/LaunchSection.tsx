'use client'

import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, ListChecks, MessagesSquare, Phone, Send, UserRound } from 'lucide-react'
import type { DictLaunch } from '@/lib/i18n'

const MEASURE_ICONS = [MessagesSquare, Phone, Send, UserRound, ListChecks]

// Animated ordinal counter: counts 01→0N when the card enters the viewport.
// The measures have no public numbers (the site deliberately avoids invented
// stats), so the counting element is the card index, not a fabricated metric.
function MeasureCard({ measure, index }: { measure: string; index: number }) {
  const target = index + 1
  const [value, setValue] = useState(0)
  const ref = useRef<HTMLLIElement | null>(null)
  const startedRef = useRef(false)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setValue(target)
      return
    }
    const node = ref.current
    if (!node) return
    let raf = 0
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || startedRef.current) return
        startedRef.current = true
        observer.disconnect()
        const started = performance.now()
        const duration = 500 + target * 160
        const tick = (now: number) => {
          const t = Math.min(1, (now - started) / duration)
          setValue(Math.round(t * target))
          if (t < 1) raf = requestAnimationFrame(tick)
        }
        raf = requestAnimationFrame(tick)
      },
      { threshold: 0.4 }
    )
    observer.observe(node)
    return () => {
      observer.disconnect()
      if (raf) cancelAnimationFrame(raf)
    }
  }, [target])

  const Icon = MEASURE_ICONS[index] ?? CheckCircle2

  return (
    <li ref={ref} className="rounded-2xl border border-border-col bg-surface p-5">
      <div className="flex items-center justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent">
          <Icon size={17} aria-hidden="true" />
        </span>
        <span className="text-2xl font-bold tabular-nums text-accent/80" aria-hidden="true">
          {String(value).padStart(2, '0')}
        </span>
      </div>
      <p className="mt-3 text-sm font-medium leading-relaxed text-primary">{measure}</p>
    </li>
  )
}

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

        {/* What we track after launch — counter cards */}
        <div className="mt-14">
          <h3 className="text-xl font-bold text-primary">{dict.measuresTitle}</h3>
          <ul className="mt-5 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
            {dict.measures.map((measure, index) => (
              <MeasureCard key={measure} measure={measure} index={index} />
            ))}
          </ul>
        </div>

        {/* Price + what's included accordion + CTA */}
        <div id="pricing" className="mt-10 scroll-mt-24 rounded-2xl border border-accent/25 bg-accent-soft/45 p-6 lg:p-8">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-start">
            <div>
              <p className="text-2xl font-bold text-primary">{dict.pricingLine}</p>
              <details className="group mt-4 rounded-xl border border-accent/20 bg-surface/80">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-sm font-semibold text-primary marker:hidden">
                  {dict.priceDetailsLabel}
                  <span className="text-xl font-normal text-accent transition-transform group-open:rotate-45 motion-reduce:transition-none" aria-hidden="true">
                    +
                  </span>
                </summary>
                <div className="border-t border-accent/15 px-4 py-3.5">
                  <ul className="space-y-2">
                    {dict.priceIncludes.map((item) => (
                      <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-primary">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs leading-relaxed text-secondary">{dict.priceExtraNote}</p>
                </div>
              </details>
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
