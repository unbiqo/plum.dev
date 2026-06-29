'use client'

import { useCallback, useState } from 'react'
import { Send } from 'lucide-react'
import type { DictDemo, DictDemoScenario, DictLiveChat, DictCustomDemoChat, DictIntake, Locale } from '@/lib/i18n'
import LiveChat, { type LiveChatSnapshot } from '@/components/LiveChat'
import CustomDemoChat from '@/components/CustomDemoChat'
import type { IntakeField, PackageId } from '@/lib/intake'

// Functional identifier — not copy, not locale-specific
const DAMIWORKS_TAB_ID = 'damiworks'

function StaticChatWindow({
  scenario,
  staticChat,
}: {
  scenario: DictDemoScenario
  staticChat: DictDemo['staticChat']
}) {
  return (
    <div className="bg-surface border border-border-col rounded-2xl flex flex-col min-h-[400px] overflow-hidden">
      <div className="px-4 py-3 border-b border-border-col flex items-center gap-3">
        <div className="w-7 h-7 rounded-full bg-accent-soft flex items-center justify-center text-accent text-[10px] font-bold flex-shrink-0">
          AI
        </div>
        <div>
          <div className="text-sm font-medium text-primary">{scenario.agentName}</div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            <span className="text-xs text-secondary">{staticChat.onlineLabel}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 p-4 space-y-3">
        {scenario.messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`text-sm px-4 py-2.5 rounded-2xl max-w-[78%] leading-relaxed ${
                msg.from === 'user'
                  ? 'bg-accent-soft text-primary rounded-tr-sm'
                  : 'bg-bg border border-border-col text-primary rounded-tl-sm'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {/* Decorative typing indicator */}
        <div className="flex justify-start">
          <div className="bg-bg border border-border-col rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:300ms]" />
          </div>
        </div>
      </div>

      <div className="px-4 py-3 border-t border-border-col flex items-center gap-2">
        <div className="flex-1 bg-bg border border-border-col rounded-xl px-4 py-2 text-sm text-secondary">
          {staticChat.inputPlaceholder}
        </div>
        <button
          className="w-9 h-9 bg-accent rounded-xl flex items-center justify-center text-white hover:opacity-90 transition-opacity flex-shrink-0"
          aria-label={staticChat.sendAriaLabel}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  )
}

function LeadSummaryPanel({
  scenario,
  leadSummary,
}: {
  scenario: DictDemoScenario
  leadSummary: DictDemo['leadSummary']
}) {
  return (
    <div className="bg-surface border border-border-col rounded-2xl p-6 flex flex-col">
      <div className="flex items-center gap-2 mb-5">
        <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
        <span className="text-sm font-semibold text-primary">{leadSummary.title}</span>
      </div>

      <dl className="space-y-4 flex-1">
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{leadSummary.service}</dt>
          <dd className="text-sm text-primary font-medium">{scenario.leadSummary.service}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{leadSummary.need}</dt>
          <dd className="text-sm text-primary font-medium">{scenario.leadSummary.need}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{leadSummary.time}</dt>
          <dd className="text-sm text-primary font-medium">{scenario.leadSummary.time}</dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{leadSummary.status}</dt>
          <dd className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
            <span className="text-sm text-primary font-medium">{scenario.leadSummary.status}</span>
          </dd>
        </div>
      </dl>

      <div className="mt-6 rounded-xl border border-accent/20 bg-accent-soft/60 px-3 py-2.5 text-center text-sm font-medium text-accent">
        {leadSummary.sendToOwnerButton}
      </div>
    </div>
  )
}

function PackageSelectionPanel({
  dict,
  intake,
  snapshot,
}: {
  dict: DictDemo
  intake: DictIntake
  snapshot: LiveChatSnapshot | null
}) {
  const summary = dict.packageSummary
  const intakeState = snapshot?.intake
  const completed = intakeState?.completed ?? false
  const contactClosed = snapshot?.contactClosed ?? false

  const displayValues = (field: IntakeField, values: string[] | null | undefined) => {
    if (!values || values.length === 0) return summary.empty
    const question = intake.questions.find((q) => q.id === field)
    if (!question) return values.join(', ')
    return values
      .map((value) => {
        const idx = question.values.indexOf(value)
        return idx >= 0 ? question.options[idx] : value
      })
      .join(', ')
  }

  const packageLabel = (pkg: PackageId | null | undefined) => {
    if (!pkg) return summary.empty
    if (pkg === 'Start') return summary.packageLabels.start
    if (pkg === 'Sales Assistant') return summary.packageLabels.sales
    return summary.packageLabels.integrated
  }

  const status = contactClosed
    ? summary.status.leadSubmitted
    : completed
      ? summary.status.packageSelected
      : summary.status.beforeIntake

  const nextStep = contactClosed
    ? summary.nextStep.leadSubmitted
    : completed
      ? summary.nextStep.leaveContact
      : summary.nextStep.completeAssessment

  return (
    <div className="bg-surface border border-border-col rounded-2xl p-6 flex flex-col">
      <div className="flex items-center gap-2 mb-5">
        <span className="w-2 h-2 rounded-full bg-accent flex-shrink-0" />
        <span className="text-sm font-semibold text-primary">{summary.title}</span>
      </div>

      <dl className="space-y-4 flex-1">
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{summary.channels}</dt>
          <dd className="text-sm text-primary font-medium">
            {displayValues('channels', intakeState?.channels)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{summary.tasks}</dt>
          <dd className="text-sm text-primary font-medium">
            {displayValues('tasks', intakeState?.tasks)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{summary.recommendation}</dt>
          <dd className="text-sm text-primary font-medium">
            {completed ? packageLabel(snapshot?.recommendedPackage) : summary.empty}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-secondary uppercase tracking-wider mb-0.5">{summary.nextStep.label}</dt>
          <dd className="text-sm text-primary font-medium">{nextStep}</dd>
        </div>
      </dl>

      <div className="mt-6 rounded-xl border border-accent/20 bg-accent-soft/60 px-3 py-2.5 text-center text-sm font-medium text-accent">
        {status}
      </div>
    </div>
  )
}

function CustomDemoSummaryPanel({ dict }: { dict: DictDemo }) {
  const summary = dict.customSummary

  return (
    <div className="bg-surface border border-border-col rounded-2xl p-6 flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <span className="w-2 h-2 rounded-full bg-accent flex-shrink-0" />
        <span className="text-sm font-semibold text-primary">{summary.title}</span>
      </div>
      <p className="text-sm text-secondary leading-relaxed flex-1">{summary.text}</p>
      <div className="mt-6 rounded-xl border border-accent/20 bg-accent-soft/60 px-3 py-2.5 text-center text-sm font-medium text-accent">
        {summary.status}
      </div>
    </div>
  )
}

type Props = {
  dict: DictDemo
  locale: Locale
  liveChat: DictLiveChat
  customDemoChat: DictCustomDemoChat
  intake: DictIntake
}

export default function DemoSection({ dict, locale, liveChat, customDemoChat, intake }: Props) {
  const [selectedId, setSelectedId] = useState(DAMIWORKS_TAB_ID)
  const [liveSnapshot, setLiveSnapshot] = useState<LiveChatSnapshot | null>(null)
  const handleLiveStateChange = useCallback((state: LiveChatSnapshot) => {
    setLiveSnapshot(state)
  }, [])
  const isConsultant = selectedId === DAMIWORKS_TAB_ID
  const isCustomDemo = selectedId === dict.customDemoTab.id
  const scenario = dict.scenarios.find((s) => s.id === selectedId)

  const tabs = [
    ...dict.scenarios.map((s) => ({ id: s.id, label: s.label })),
    { id: dict.customDemoTab.id, label: dict.customDemoTab.label },
  ]

  return (
    <section id="demo" className="scroll-mt-20 py-24 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-3">{dict.headline}</h2>
          <p className="text-secondary text-lg">{dict.subheadline}</p>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[200px_1fr_260px]">
          {/* Left: scenario selector */}
          <div className="flex flex-row lg:flex-col gap-2 overflow-x-auto lg:overflow-visible pb-1 lg:pb-0">
            {tabs.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={`flex-shrink-0 text-left px-4 py-3 rounded-xl text-sm font-medium transition-colors whitespace-nowrap ${
                  selectedId === s.id
                    ? 'bg-accent-soft text-accent'
                    : 'text-secondary hover:bg-surface hover:text-primary'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Center: live consultant chat, custom demo chat, or static demo */}
          {isConsultant ? (
            <LiveChat dict={liveChat} intake={intake} onStateChange={handleLiveStateChange} />
          ) : isCustomDemo ? (
            <CustomDemoChat dict={customDemoChat} />
          ) : (
            <StaticChatWindow scenario={scenario!} staticChat={dict.staticChat} />
          )}

          {/* Right: context-aware summary */}
          {isConsultant ? (
            <PackageSelectionPanel dict={dict} intake={intake} snapshot={liveSnapshot} />
          ) : isCustomDemo ? (
            <CustomDemoSummaryPanel dict={dict} />
          ) : (
            <LeadSummaryPanel scenario={scenario!} leadSummary={dict.leadSummary} />
          )}
        </div>
      </div>
    </section>
  )
}
