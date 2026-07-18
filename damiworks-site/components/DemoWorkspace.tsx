'use client'

import { useCallback, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Globe, MessageCircle, RotateCcw } from 'lucide-react'
import type { DictDemoWorkspace, DictMedicalChatLabels, DictMedicalSummaryLabels, DictSite } from '@/lib/i18n'
import MedicalCenterChat, {
  type MedicalMessage,
  type MedicalBackendState,
} from '@/components/MedicalCenterChat'
import MedicalCenterSummaryPanel from '@/components/MedicalCenterSummaryPanel'
import StaggerReveal from '@/components/StaggerReveal'
import { WHATSAPP_URL } from '@/lib/whatsapp'

type Props = {
  dict: DictDemoWorkspace
  medicalChat: DictMedicalChatLabels
  medicalSummary: DictMedicalSummaryLabels
  site: DictSite
}

function staggerStyle(index: number): React.CSSProperties {
  return { '--stagger-i': index } as React.CSSProperties
}

// wa.me / api.whatsapp.com links can carry a prefilled message; any other
// WhatsApp URL is opened as is.
function whatsappHrefWithText(base: string, text: string): string {
  try {
    const url = new URL(base)
    if (url.hostname === 'wa.me' || url.hostname.endsWith('.wa.me') || url.hostname === 'api.whatsapp.com') {
      url.searchParams.set('text', text)
      return url.toString()
    }
  } catch {
    // fall through to the untouched base URL
  }
  return base
}

function SectionHeader({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle?: string }) {
  return (
    <div className="max-w-2xl">
      <span className="text-xs font-bold uppercase tracking-wider text-accent">{eyebrow}</span>
      <h2 className="mt-2 text-2xl font-bold leading-tight text-primary lg:text-3xl">{title}</h2>
      {subtitle && <p className="mt-3 leading-relaxed text-secondary">{subtitle}</p>}
    </div>
  )
}

// The /ru/demo workspace: what we understood about the clinic (honest demo
// mock) -> patient test chat with a live summary -> launch-plan assistant
// that turns 5 answers into a draft plan.
export default function DemoWorkspace({ dict, medicalChat, medicalSummary, site }: Props) {
  const searchParams = useSearchParams()
  const siteParam = searchParams.get('site')
  const clinicLabel = siteParam || dict.intake.fallbackClinic

  // ---------- patient test chat state ----------
  const [messages, setMessages] = useState<MedicalMessage[]>([])
  const [backendState, setBackendState] = useState<MedicalBackendState | null>(null)
  const [mobileSummaryOpen, setMobileSummaryOpen] = useState(false)
  const summaryAutoOpenedRef = useRef(false)

  const handleConversationUpdate = useCallback((next: MedicalMessage[]) => {
    setMessages(next)
  }, [])

  const handleStateUpdate = useCallback((state: MedicalBackendState) => {
    setBackendState(state)
    if (
      !summaryAutoOpenedRef.current &&
      (state.specialty ||
        state.symptomsOrGoal ||
        state.preferredTime ||
        (state.leadStatus && state.leadStatus !== 'open'))
    ) {
      summaryAutoOpenedRef.current = true
      setMobileSummaryOpen(true)
    }
  }, [])

  // ---------- launch assistant state ----------
  const questions = dict.assistant.questions
  const [stepIdx, setStepIdx] = useState(0)
  const [answers, setAnswers] = useState<string[][]>(() => questions.map(() => []))
  const [planReady, setPlanReady] = useState(false)
  const planRef = useRef<HTMLDivElement | null>(null)

  const toggleOption = (option: string) => {
    setAnswers((prev) => {
      const next = prev.map((a) => [...a])
      const current = next[stepIdx]
      if (questions[stepIdx].multi) {
        next[stepIdx] = current.includes(option) ? current.filter((o) => o !== option) : [...current, option]
      } else {
        next[stepIdx] = [option]
      }
      return next
    })
  }

  const goNext = () => {
    if (stepIdx < questions.length - 1) {
      setStepIdx(stepIdx + 1)
    } else {
      setPlanReady(true)
      requestAnimationFrame(() => planRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }

  const restart = () => {
    setAnswers(questions.map(() => []))
    setStepIdx(0)
    setPlanReady(false)
  }

  const question = questions[stepIdx]
  const selected = answers[stepIdx]
  const progressLabels = [...questions.map((q) => q.step), dict.assistant.planStepLabel]
  const progressIdx = planReady ? questions.length : stepIdx

  const answerValue = (idx: number) => (answers[idx].length > 0 ? answers[idx].join(', ') : dict.plan.emptyValue)

  const planBlocks = [
    { label: dict.plan.blockChannels, value: answerValue(0) },
    { label: dict.plan.blockKnowledge, value: answerValue(1) },
    { label: dict.plan.blockScenarios, value: answerValue(2) },
    { label: dict.plan.blockHandoff, value: answerValue(3) },
    { label: dict.plan.blockLead, value: answerValue(4), note: dict.plan.leadFieldsNote },
  ]

  const planText = [
    `${dict.plan.title}${siteParam ? ` — ${siteParam}` : ''}`,
    ...planBlocks.map((b) => `• ${b.label}: ${b.value}`),
    dict.plan.priceLine,
  ].join('\n')

  return (
    <div className="min-h-screen bg-bg">
      {/* Minimal workspace header: back to the site + one CTA */}
      <header className="sticky top-0 z-50 border-b border-border-col bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <a href="/ru" className="flex items-center gap-2 text-lg font-semibold text-primary">
            <ArrowLeft size={16} className="text-secondary" aria-hidden="true" />
            {site.name}
          </a>
          <a
            href="/ru#contact"
            className="inline-flex items-center rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            {dict.headerCta}
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-16 px-6 py-12 lg:space-y-20 lg:py-16">
        {/* 01 — what we understood about the clinic (demo mock, honestly labeled) */}
        <section>
          <SectionHeader eyebrow={dict.intake.eyebrow} title={dict.intake.title} />
          <StaggerReveal className="mt-6">
            <div className="rounded-2xl border border-border-col bg-surface p-6 lg:p-7">
              <div className="flex flex-wrap items-center gap-3" data-stagger-item style={staggerStyle(0)}>
                <span className="inline-flex items-center gap-2 rounded-full border border-border-col bg-bg px-4 py-1.5 text-sm font-medium text-primary">
                  <Globe size={14} className="text-accent" aria-hidden="true" />
                  {siteParam ? `${dict.intake.siteLabel}: ${clinicLabel}` : clinicLabel}
                </span>
              </div>

              <p
                className="mt-4 rounded-xl border border-accent/20 bg-accent-soft/40 px-4 py-3 text-sm leading-relaxed text-secondary"
                data-stagger-item
                style={staggerStyle(1)}
              >
                {dict.intake.demoNote}
              </p>

              <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div data-stagger-item style={staggerStyle(2)}>
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-secondary">{dict.intake.foundTitle}</h3>
                  <ul className="mt-3 space-y-2">
                    {dict.intake.foundItems.map((item) => (
                      <li key={item} className="flex gap-2.5 text-sm text-primary">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
                <div data-stagger-item style={staggerStyle(3)}>
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-secondary">{dict.intake.clarifyTitle}</h3>
                  <ul className="mt-3 space-y-2">
                    {dict.intake.clarifyItems.map((item) => (
                      <li key={item} className="flex gap-2.5 text-sm text-secondary">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full border border-secondary/60" aria-hidden="true" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </StaggerReveal>
        </section>

        {/* 02 — try it as a patient */}
        <section>
          <SectionHeader eyebrow={dict.test.eyebrow} title={dict.test.title} subtitle={dict.test.subtitle} />
          <div className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-[1.15fr_0.85fr] lg:gap-4">
            <div className="min-w-0">
              <MedicalCenterChat
                dict={medicalChat}
                onConversationUpdate={handleConversationUpdate}
                onStateUpdate={handleStateUpdate}
              />
            </div>

            <div className="hidden lg:flex lg:flex-col">
              <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-secondary">
                {dict.test.summaryLabel}
              </p>
              <div className="flex-1 [&>div]:h-full">
                <MedicalCenterSummaryPanel messages={messages} dict={medicalSummary} backendState={backendState} />
              </div>
            </div>

            <details
              className="group rounded-2xl border border-accent/25 bg-accent-soft/40 lg:hidden"
              open={mobileSummaryOpen}
              onToggle={(event) => setMobileSummaryOpen((event.target as HTMLDetailsElement).open)}
            >
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-primary marker:hidden">
                {dict.test.summaryLabel}
                <span className="text-lg font-normal text-accent transition-transform group-open:rotate-45" aria-hidden="true">+</span>
              </summary>
              <div className="border-t border-accent/15 p-3">
                <MedicalCenterSummaryPanel messages={messages} dict={medicalSummary} backendState={backendState} />
              </div>
            </details>
          </div>
        </section>

        {/* 03 — launch assistant */}
        <section ref={planRef} className="scroll-mt-20 pb-4">
          <SectionHeader eyebrow={dict.assistant.eyebrow} title={dict.assistant.title} subtitle={dict.assistant.subtitle} />

          {/* Progress */}
          <ol className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2">
            {progressLabels.map((label, i) => (
              <li key={label} className="flex items-center gap-2">
                {i > 0 && <span className="h-px w-4 bg-border-col" aria-hidden="true" />}
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
                    i < progressIdx
                      ? 'border-accent/30 bg-accent-soft text-accent'
                      : i === progressIdx
                        ? 'border-accent bg-accent text-white'
                        : 'border-border-col bg-surface text-secondary'
                  }`}
                >
                  {i < progressIdx && <Check size={11} aria-hidden="true" />}
                  {label}
                </span>
              </li>
            ))}
          </ol>

          {!planReady ? (
            <div className="mt-6 max-w-3xl rounded-2xl border border-border-col bg-surface p-6 lg:p-7">
              <h3 className="text-lg font-bold text-primary">{question.question}</h3>

              <div className="mt-4 flex flex-wrap gap-2">
                {question.options.map((option) => {
                  const isSelected = selected.includes(option)
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => toggleOption(option)}
                      aria-pressed={isSelected}
                      className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                        isSelected
                          ? 'border-accent bg-accent text-white'
                          : 'border-border-col bg-bg text-primary hover:border-accent'
                      }`}
                    >
                      {option}
                    </button>
                  )
                })}
              </div>

              <div className="mt-5 rounded-xl border border-accent/15 bg-accent-soft/35 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-accent">{dict.assistant.whyLabel}</p>
                <p className="mt-1 text-sm leading-relaxed text-secondary">{question.why}</p>
              </div>

              <div className="mt-6 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setStepIdx(Math.max(0, stepIdx - 1))}
                  disabled={stepIdx === 0}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-border-col bg-surface px-4 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-bg disabled:opacity-40"
                >
                  <ArrowLeft size={14} aria-hidden="true" />
                  {dict.assistant.backLabel}
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  disabled={selected.length === 0}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                >
                  {stepIdx === questions.length - 1 ? dict.assistant.finishLabel : dict.assistant.nextLabel}
                  <ArrowRight size={14} aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-6 max-w-3xl rounded-2xl border border-accent/25 bg-surface p-6 lg:p-8">
              <h3 className="text-xl font-bold text-primary lg:text-2xl">{dict.plan.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-secondary">{dict.plan.subtitle}</p>

              <dl className="mt-6 space-y-4">
                {planBlocks.map((block) => (
                  <div key={block.label} className="border-b border-border-col pb-4 last:border-b-0 last:pb-0">
                    <dt className="text-xs font-semibold uppercase tracking-wider text-secondary">{block.label}</dt>
                    <dd className="mt-1 text-sm font-medium text-primary">{block.value}</dd>
                    {block.note && <dd className="mt-1 text-xs text-secondary">{block.note}</dd>}
                  </div>
                ))}
              </dl>

              <div className="mt-6 rounded-xl border border-accent/25 bg-accent-soft/45 px-5 py-4">
                <p className="text-lg font-bold text-primary">{dict.plan.priceLine}</p>
                <p className="mt-1 text-sm leading-relaxed text-secondary">{dict.plan.priceNote}</p>
              </div>

              <div className="mt-6 flex flex-col gap-2.5 sm:flex-row">
                <a
                  href="/ru#contact"
                  className="inline-flex min-h-12 flex-1 items-center justify-center rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                >
                  {dict.plan.ctaPrimary}
                </a>
                {WHATSAPP_URL && (
                  <a
                    href={whatsappHrefWithText(WHATSAPP_URL, planText)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl border border-border-col bg-surface px-6 py-3 text-sm font-medium text-primary transition-colors hover:bg-bg"
                  >
                    <MessageCircle size={15} aria-hidden="true" />
                    {dict.plan.ctaWhatsapp}
                  </a>
                )}
              </div>

              <button
                type="button"
                onClick={restart}
                className="mt-4 inline-flex items-center gap-1.5 text-xs text-secondary transition-colors hover:text-primary"
              >
                <RotateCcw size={12} aria-hidden="true" />
                {dict.plan.restartLabel}
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
