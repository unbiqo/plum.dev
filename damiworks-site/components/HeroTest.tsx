'use client'

import { useCallback, useRef, useState } from 'react'
import { ArrowRight, Zap } from 'lucide-react'
import type { DictHeroTest, DictMedicalChatLabels, DictMedicalSummaryLabels } from '@/lib/i18n'
import HeroFlowBackground from '@/components/HeroFlowBackground'
import MedicalCenterChat, {
  type MedicalMessage,
  type MedicalBackendState,
} from '@/components/MedicalCenterChat'
import MedicalCenterSummaryPanel from '@/components/MedicalCenterSummaryPanel'

type Props = {
  dict: DictHeroTest
  medicalChat: DictMedicalChatLabels
  medicalSummary: DictMedicalSummaryLabels
}

// Test-first hero: the page opens with the product itself, not a pitch. The
// visitor writes as a patient into the live MedNova demo and watches the
// admin-ready заявка assemble on the right. Carries id="demo" so all
// "try the demo" CTAs land here.
export default function HeroTest({ dict, medicalChat, medicalSummary }: Props) {
  const [messages, setMessages] = useState<MedicalMessage[]>([])
  const [backendState, setBackendState] = useState<MedicalBackendState | null>(null)
  const [mobileSummaryOpen, setMobileSummaryOpen] = useState(false)
  const summaryAutoOpenedRef = useRef(false)

  const handleConversationUpdate = useCallback((next: MedicalMessage[]) => {
    setMessages(next)
  }, [])

  const handleStateUpdate = useCallback((state: MedicalBackendState) => {
    setBackendState(state)
    // Auto-open the mobile summary once the заявка starts filling — the
    // visitor should see the result, not just the chat. Only once, so a
    // manual close is respected afterwards.
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

  const hasMobileHeadline = Boolean(dict.mobileHeadlinePart1)

  return (
    <section id="demo" className="scroll-mt-20 relative isolate overflow-hidden bg-bg pt-8 pb-10 sm:pt-14 sm:pb-16 lg:pt-20 lg:pb-24">
      <HeroFlowBackground />
      <div className="hero-test-glow" aria-hidden="true" />

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        {/* Headline — mobile gets its own shorter, tighter-set copy, single h1/p for a11y */}
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-3xl font-bold leading-tight text-primary sm:text-4xl lg:text-5xl">
            {hasMobileHeadline && (
              <span
                className="sm:hidden block mx-auto"
                style={{
                  fontSize: 'clamp(34px, 8.5vw, 42px)',
                  lineHeight: 1.04,
                  letterSpacing: '-0.045em',
                  maxWidth: '370px',
                  textWrap: 'balance',
                }}
              >
                {dict.mobileHeadlinePart1}
                <span className="text-accent">{dict.mobileHeadlineAccent}</span>
              </span>
            )}
            <span className={hasMobileHeadline ? 'hidden sm:inline' : undefined}>
              {dict.headlinePart1}
              <span className="text-accent">{dict.headlineAccent}</span>
            </span>
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-base leading-relaxed text-secondary sm:mt-4 lg:text-lg">
            {dict.mobileSubheadline && <span className="sm:hidden">{dict.mobileSubheadline}</span>}
            <span className={dict.mobileSubheadline ? 'hidden sm:inline' : undefined}>{dict.subheadline}</span>
          </p>
        </div>

        {/* Test surface */}
        <div className="relative mt-6 sm:mt-10">
          {/* Floating context chips — decorative, desktop only */}
          <ul className="pointer-events-none absolute inset-0 hidden xl:block" aria-hidden="true">
            {dict.chips.map((chip, i) => (
              <li
                key={chip}
                className={`hero-test-chip hero-test-chip-${i + 1} absolute rounded-full border border-border-col bg-surface/80 px-3 py-1 text-xs font-medium text-secondary shadow-sm backdrop-blur-sm`}
              >
                {chip}
              </li>
            ))}
          </ul>

          <div className="mx-auto max-w-5xl rounded-3xl p-0 sm:border sm:border-border-col sm:bg-surface/70 sm:p-4 sm:shadow-lg sm:shadow-accent/5 sm:backdrop-blur-sm lg:p-5">
            <div className="mb-3 hidden flex-wrap items-center justify-between gap-2 px-1 sm:flex">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
                <Zap size={12} aria-hidden="true" />
                {dict.liveHint}
              </span>
              <span className="text-xs text-secondary">{dict.scenarioNote}</span>
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.15fr_0.85fr] lg:gap-4">
              {/* Chat */}
              <div className="min-w-0">
                <MedicalCenterChat
                  dict={medicalChat}
                  onConversationUpdate={handleConversationUpdate}
                  onStateUpdate={handleStateUpdate}
                />
              </div>

              {/* Admin summary — always visible on desktop */}
              <div className="hidden lg:flex lg:flex-col">
                <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-secondary">
                  {dict.summaryLabel}
                </p>
                <div className="flex-1 [&>div]:h-full">
                  <MedicalCenterSummaryPanel
                    messages={messages}
                    dict={medicalSummary}
                    backendState={backendState}
                  />
                </div>
              </div>

              {/* Mobile: collapsible summary, auto-opens once the заявка fills */}
              <details
                className="group rounded-2xl border border-accent/25 bg-accent-soft/40 lg:hidden"
                open={mobileSummaryOpen}
                onToggle={(event) => setMobileSummaryOpen((event.target as HTMLDetailsElement).open)}
              >
                <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-primary marker:hidden">
                  {dict.summaryLabel}
                  <span className="text-lg font-normal text-accent transition-transform group-open:rotate-45" aria-hidden="true">+</span>
                </summary>
                <div className="border-t border-accent/15 p-3">
                  <MedicalCenterSummaryPanel
                    messages={messages}
                    dict={medicalSummary}
                    backendState={backendState}
                  />
                </div>
              </details>
            </div>
          </div>

          {/* Under-panel CTA */}
          <div className="mt-5 flex justify-center">
            <a
              href={dict.ctaSecondary.href}
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            >
              {dict.ctaSecondary.label}
              <ArrowRight size={15} aria-hidden="true" />
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
