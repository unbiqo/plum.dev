'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Send, RotateCcw, CheckCircle2 } from 'lucide-react'
import { SHOW_DAMIWORKS_CHAT_PRICES } from '@/lib/constants'
import { CALENDLY_URL } from '@/lib/calendly'
import {
  DAMIWORKS_SESSION_TTL_MS,
  loadChatSession,
  resetChatSession,
  touchChatSession,
} from '@/lib/chatSession'
import {
  INITIAL_INTAKE,
  PACKAGE_PRICES,
  applyIntakeAnswer,
  buildIntakeContextString,
  getInterestLevel,
  recommendPackage,
  scoreIntake,
  type IntakeState,
  type LeadContact,
  type LeadSummary,
  type PackageId,
} from '@/lib/intake'
import {
  extractFreeformIntake,
  filterUnusedChips,
  mergeFreeformIntake,
} from '@/lib/freeform'
import type { DictLiveChat, DictIntake, DictIntakeQuestion } from '@/lib/i18n'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TextMessage = { kind: 'text'; from: 'user' | 'ai'; text: string; isIntake: boolean }
type SummaryMessage = { kind: 'summary' }
type Message = TextMessage | SummaryMessage

export type LiveChatSnapshot = {
  intake: IntakeState
  recommendedPackage: PackageId
  leadSent: boolean
  contactClosed: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatToken(pattern: string, tokens: Record<string, string | number>): string {
  return Object.entries(tokens).reduce(
    (s, [k, v]) => s.replace(`{${k}}`, String(v)),
    pattern,
  )
}

// ---------------------------------------------------------------------------
// SummaryCard
// ---------------------------------------------------------------------------

type SummaryCardProps = {
  intake: IntakeState
  pkg: PackageId
  leadSent: boolean
  collapsed: boolean
  onToggleCollapse: () => void
  onAskQuestion: () => void
  onSendLead: () => void
  onEditAnswers: () => void
  dict: DictLiveChat
}

function SummaryCard({
  intake,
  pkg,
  leadSent,
  collapsed,
  onToggleCollapse,
  onAskQuestion,
  onSendLead,
  onEditAnswers,
  dict,
}: SummaryCardProps) {
  const prices = PACKAGE_PRICES[pkg]
  const setupDisplay = prices.setup.includes('–') ? prices.setup : `от ${prices.setup}`

  if (collapsed) {
    const detail = [
      intake.channels[0] ?? '',
      intake.volume ? `${intake.volume}${dict.perDayLabel}` : '',
      intake.timeline ?? '',
    ]
      .filter(Boolean)
      .join(' · ')
    return (
      <div className="bg-accent-soft/60 border border-accent/15 rounded-xl p-3 max-w-[90%] space-y-0.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-primary">
            {formatToken(dict.packageSelectedPattern, { pkg })}
          </span>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={onEditAnswers}
              className="text-[11px] text-secondary hover:text-primary transition-colors"
            >
              {dict.summaryLabels.editButton}
            </button>
            <button
              onClick={onToggleCollapse}
              className="text-[11px] text-accent hover:opacity-80 transition-opacity"
            >
              {dict.summaryLabels.expandButton}
            </button>
          </div>
        </div>
        {detail && <div className="text-[11px] text-secondary">{detail}</div>}
        <div className="text-xs font-medium text-accent">
          {SHOW_DAMIWORKS_CHAT_PRICES
            ? `${setupDisplay} + ${prices.monthly}`
            : dict.summaryLabels.priceDiscovery}
        </div>
      </div>
    )
  }

  const channelText = intake.channels.join(', ') || '—'
  const tasksText = intake.tasks.join(', ') || '—'

  return (
    <div className="bg-accent-soft border border-accent/20 rounded-xl p-4 space-y-3 max-w-[90%]">
      <div className="flex items-center justify-between">
        <div className="text-[10px] text-accent font-semibold uppercase tracking-widest">
          {dict.summaryLabels.recommendation}
        </div>
        <button
          onClick={onToggleCollapse}
          className="text-[11px] text-secondary hover:text-primary transition-colors"
        >
          {dict.summaryLabels.collapseButton}
        </button>
      </div>

      <div className="text-sm font-semibold text-primary">{pkg}</div>

      <dl className="space-y-1 text-sm">
        <div className="flex gap-1">
          <dt className="text-secondary shrink-0">{dict.summaryLabels.channels}</dt>
          <dd className="text-primary">{channelText}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="text-secondary shrink-0">{dict.summaryLabels.tasks}</dt>
          <dd className="text-primary">{tasksText}</dd>
        </div>
        {intake.handoff && (
          <div className="flex gap-1">
            <dt className="text-secondary shrink-0">{dict.summaryLabels.handoff}</dt>
            <dd className="text-primary">{intake.handoff}</dd>
          </div>
        )}
        {intake.volume && (
          <div className="flex gap-1">
            <dt className="text-secondary shrink-0">{dict.summaryLabels.volume}</dt>
            <dd className="text-primary">{intake.volume}{dict.perDayLabel}</dd>
          </div>
        )}
        {intake.timeline && (
          <div className="flex gap-1">
            <dt className="text-secondary shrink-0">{dict.summaryLabels.timeline}</dt>
            <dd className="text-primary">{intake.timeline}</dd>
          </div>
        )}
      </dl>

      <div className="pt-1 border-t border-accent/10">
        <div className="text-xs text-secondary mb-0.5">{dict.summaryLabels.price}</div>
        {SHOW_DAMIWORKS_CHAT_PRICES ? (
          <>
            <div className="text-sm font-semibold text-accent">{setupDisplay}</div>
            <div className="text-xs text-secondary">+ {prices.monthly}</div>
          </>
        ) : (
          <div className="text-sm font-medium text-accent">{dict.summaryLabels.priceDiscovery}</div>
        )}
      </div>

      <div className="flex flex-col gap-2 pt-1">
        <button
          onClick={onAskQuestion}
          className="w-full bg-accent text-white rounded-xl py-2 text-sm font-medium hover:opacity-90 transition-opacity"
        >
          {dict.askQuestionButton}
        </button>

        {leadSent ? (
          <div className="flex items-center gap-1.5 text-xs text-secondary py-1">
            <CheckCircle2 size={12} className="text-green-500 flex-shrink-0" />
            <span>{dict.sentConfirmation}</span>
          </div>
        ) : (
          <button
            onClick={onSendLead}
            className="w-full border border-border-col text-secondary rounded-xl py-2 text-sm hover:text-primary hover:border-accent/40 transition-colors"
          >
            {dict.sendToOwnerButton}
          </button>
        )}

        <button
          onClick={onEditAnswers}
          className="text-xs text-secondary hover:text-primary transition-colors"
        >
          {dict.editAnswersButton}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ChipsPanel — renders current intake question options
// ---------------------------------------------------------------------------

type ChipsPanelProps = {
  question: DictIntakeQuestion
  questionIndex: number
  requiredStepCount: number
  multiBuffer: string[]
  transitioning: boolean
  onSingleAnswer: (displayLabel: string) => void
  onToggleBuffer: (displayLabel: string) => void
  onConfirmMulti: () => void
  onSkip: () => void
  dict: Pick<DictLiveChat, 'stepLabelPattern' | 'optionalLabel' | 'skipLabel' | 'confirmButtonPattern' | 'confirmButtonEmpty'>
}

function ChipsPanel({
  question,
  questionIndex,
  requiredStepCount,
  multiBuffer,
  transitioning,
  onSingleAnswer,
  onToggleBuffer,
  onConfirmMulti,
  onSkip,
  dict,
}: ChipsPanelProps) {
  const stepLabel = question.optional
    ? dict.optionalLabel
    : formatToken(dict.stepLabelPattern, { n: questionIndex + 1, total: requiredStepCount })

  return (
    <div className="px-4 py-3 border-t border-border-col space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-secondary">{stepLabel}</span>
        {question.optional && (
          <button
            onClick={onSkip}
            className="text-[11px] text-secondary hover:text-primary transition-colors"
          >
            {dict.skipLabel}
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {question.options.map((opt) => {
          const active = question.multi && multiBuffer.includes(opt)
          return (
            <button
              key={opt}
              disabled={transitioning}
              onClick={() => (question.multi ? onToggleBuffer(opt) : onSingleAnswer(opt))}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all disabled:opacity-50 ${
                active
                  ? 'bg-accent text-white border-accent'
                  : 'bg-bg border-border-col text-primary hover:border-accent/50 hover:text-accent'
              }`}
            >
              {opt}
            </button>
          )
        })}
      </div>

      {question.multi && (
        <button
          onClick={onConfirmMulti}
          disabled={multiBuffer.length === 0 || transitioning}
          className="text-xs bg-accent text-white rounded-xl px-4 py-1.5 hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {multiBuffer.length > 0
            ? formatToken(dict.confirmButtonPattern, { n: multiBuffer.length })
            : dict.confirmButtonEmpty}
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// LiveChat — main component
// ---------------------------------------------------------------------------

const SITE_INSTANCE_ID = 'damiworks_site'
const LEAD_SENT_KEY = 'damiworks_lead_sent_for_chat_id'
const LEAD_CONTACT_KEY = 'damiworks_lead_contact_for_chat_id'

type Props = {
  dict: DictLiveChat
  intake: DictIntake
  locale: string
  onStateChange?: (state: LiveChatSnapshot) => void
}

export default function LiveChat({ dict, intake: intakeDict, locale, onStateChange }: Props) {
  const MESSAGES_SESSION_KEY = `damiworks_messages_${locale}`
  const INTAKE_SESSION_KEY = `damiworks_intake_state_${locale}`
  const USED_CHIPS_SESSION_KEY = `damiworks_used_chips_${locale}`
  const intakeQuestions = intakeDict.questions
  const requiredStepCount = intakeQuestions.filter((q) => !q.optional).length

  // Intake state
  const [intakeStep, setIntakeStep] = useState(0)
  const [intake, setIntake] = useState<IntakeState>(INITIAL_INTAKE)
  const [multiBuffer, setMultiBuffer] = useState<string[]>([])
  const [transitioning, setTransitioning] = useState(false)

  // Post-intake results
  const [recPkg, setRecPkg] = useState<PackageId>('Start')
  const [score, setScore] = useState(0)
  const [summaryCollapsed, setSummaryCollapsed] = useState(false)

  // Chat state
  const [messages, setMessages] = useState<Message[]>([])
  const [chatMode, setChatMode] = useState<'intro' | 'intake' | 'chat'>('intro')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chatId, setChatId] = useState('')
  const [leadSent, setLeadSent] = useState(false)
  const [contactClosed, setContactClosed] = useState(false)
  const [leadStatus, setLeadStatus] = useState<string | null>(null)
  // Clicked predefined quick replies disappear for the rest of the session.
  const [usedChips, setUsedChips] = useState<string[]>([])

  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const initDone = useRef(false)
  const chatIdRef = useRef('')
  const intakeRef = useRef(intake)
  intakeRef.current = intake

  useEffect(() => {
    onStateChange?.({
      intake,
      recommendedPackage: recPkg,
      leadSent,
      contactClosed,
    })
  }, [intake, recPkg, leadSent, contactClosed, onStateChange])

  // ------------ initialization ------------

  useEffect(() => {
    if (initDone.current) return
    initDone.current = true

    const { session, expired } = loadChatSession(SITE_INSTANCE_ID, DAMIWORKS_SESSION_TTL_MS)
    const id = session.chat_id
    chatIdRef.current = id
    setChatId(id)

    if (expired) {
      // Session aged past its TTL — drop stale local history and lead flags so
      // the user starts clean instead of resuming an abandoned intake.
      sessionStorage.removeItem(MESSAGES_SESSION_KEY)
      sessionStorage.removeItem(INTAKE_SESSION_KEY)
      sessionStorage.removeItem(USED_CHIPS_SESSION_KEY)
      localStorage.removeItem(LEAD_SENT_KEY)
      localStorage.removeItem(LEAD_CONTACT_KEY)
    }

    const storedChips = sessionStorage.getItem(USED_CHIPS_SESSION_KEY)
    if (storedChips) {
      try {
        const parsedChips = JSON.parse(storedChips) as string[]
        if (Array.isArray(parsedChips)) setUsedChips(parsedChips)
      } catch {
        // ignore corrupt storage
      }
    }

    if (localStorage.getItem(LEAD_CONTACT_KEY) === id) {
      setContactClosed(true)
      setLeadSent(true)
    }

    const storedMessages = sessionStorage.getItem(MESSAGES_SESSION_KEY)
    if (storedMessages) {
      try {
        const parsed = JSON.parse(storedMessages) as Message[]
        if (parsed.length > 0) {
          setMessages(parsed)
          setChatMode('chat')

          // Restore intake so post-intake chips show and intake_context is sent after reload
          const storedIntake = sessionStorage.getItem(INTAKE_SESSION_KEY)
          let restoredCompleted = false
          if (storedIntake) {
            try {
              const si = JSON.parse(storedIntake) as { intake: IntakeState; recPkg: PackageId; score: number }
              if (si?.intake?.completed) {
                restoredCompleted = true
                setIntake(si.intake)
                setRecPkg(si.recPkg ?? 'Start')
                setScore(si.score ?? 0)
              }
            } catch {
              // ignore corrupt storage
            }
          }

          if (!restoredCompleted) {
            // Rebuild the free-form summary from restored user messages.
            const userTexts = parsed
              .filter((m): m is TextMessage => m.kind === 'text' && !m.isIntake && m.from === 'user')
              .map((m) => m.text)
            if (userTexts.length > 0) {
              const merged = mergeFreeformIntake(INITIAL_INTAKE, extractFreeformIntake(userTexts))
              setIntake(merged)
              setRecPkg(recommendPackage(merged))
            }
          }

          return
        }
      } catch {
        // ignore corrupt storage
      }
    }
    setMessages([
      { kind: 'text', from: 'ai', text: dict.introMessage, isIntake: false },
    ])
  }, [dict.introMessage])

  // ------------ sessionStorage persistence ------------

  useEffect(() => {
    if (messages.length > 0) {
      sessionStorage.setItem(MESSAGES_SESSION_KEY, JSON.stringify(messages))
    }
  }, [messages])

  useEffect(() => {
    if (intake.completed) {
      sessionStorage.setItem(INTAKE_SESSION_KEY, JSON.stringify({ intake, recPkg, score }))
    }
  }, [intake, recPkg, score])

  useEffect(() => {
    if (usedChips.length > 0) {
      sessionStorage.setItem(USED_CHIPS_SESSION_KEY, JSON.stringify(usedChips))
    }
  }, [usedChips])

  // ------------ auto-scroll — scrolls only the message container, not the page ------------

  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  // ------------ lead send ------------

  // A lead is one evolving entity emitted as events. `buildLead` assembles the
  // shared payload; `sendLead` emits LeadCreated (idempotent), and
  // `sendContactUpdate` emits LeadUpdated once the contact is captured.
  const buildLead = useCallback(
    (
      currentChatId: string,
      finalIntake: IntakeState,
      finalPkg: PackageId,
      finalScore: number,
      chatMsgs: Message[],
      userClickedSend: boolean,
    ): LeadSummary => {
      const level = getInterestLevel(finalScore + (userClickedSend ? 1 : 0))
      const prices = PACKAGE_PRICES[finalPkg]
      const lastMsgs = chatMsgs
        .filter((m): m is TextMessage => m.kind === 'text' && !m.isIntake)
        .slice(-5)
        .map((m) => ({
          role: m.from === 'user' ? ('user' as const) : ('assistant' as const),
          content: m.text,
        }))
      return {
        chat_id: currentChatId,
        interest_level: level,
        channels: finalIntake.channels,
        tasks: finalIntake.tasks,
        handoff: finalIntake.handoff,
        volume: finalIntake.volume,
        timeline: finalIntake.timeline,
        business_type: finalIntake.businessType,
        recommended_package: finalPkg,
        estimated_price: `от ${prices.setup} + ${prices.monthly}`,
        conversation_summary: buildIntakeContextString(finalIntake, !SHOW_DAMIWORKS_CHAT_PRICES),
        last_messages: lastMsgs,
        created_at: new Date().toISOString(),
      }
    },
    [],
  )

  const postLead = useCallback(async (lead: LeadSummary) => {
    try {
      await fetch('/api/lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead),
      })
    } catch {
      // Silent — never surface lead delivery errors to user
    }
  }, [])

  // LeadCreated: intake done, recommendation shown, waiting for contact.
  const sendLead = useCallback(
    async (
      finalIntake: IntakeState,
      finalPkg: PackageId,
      finalScore: number,
      chatMsgs: Message[],
      userClickedSend: boolean,
    ) => {
      const currentChatId = chatIdRef.current || chatId
      if (localStorage.getItem(LEAD_SENT_KEY) === currentChatId) return
      const lead = buildLead(currentChatId, finalIntake, finalPkg, finalScore, chatMsgs, userClickedSend)
      await postLead({ ...lead, event: 'created', contact: null, status: 'Waiting for contact' })
      localStorage.setItem(LEAD_SENT_KEY, currentChatId)
    },
    [chatId, buildLead, postLead],
  )

  // LeadUpdated: contact captured, ready for follow-up. Ensures a LeadCreated
  // exists first so the owner always has context; sent at most once per chat.
  const sendContactUpdate = useCallback(
    async (
      contact: LeadContact,
      finalIntake: IntakeState,
      finalPkg: PackageId,
      finalScore: number,
      chatMsgs: Message[],
    ) => {
      const currentChatId = chatIdRef.current || chatId
      if (localStorage.getItem(LEAD_SENT_KEY) !== currentChatId) {
        await sendLead(finalIntake, finalPkg, finalScore, chatMsgs, true)
      }
      if (localStorage.getItem(LEAD_CONTACT_KEY) === currentChatId) return
      const lead = buildLead(currentChatId, finalIntake, finalPkg, finalScore, chatMsgs, true)
      await postLead({ ...lead, event: 'updated', contact, status: 'Ready for follow-up' })
      localStorage.setItem(LEAD_CONTACT_KEY, currentChatId)
    },
    [chatId, buildLead, postLead, sendLead],
  )

  // ------------ intake answer ------------

  const sendIntakeAnswer = useCallback(
    (displayAnswers: string[]) => {
      const answers = displayAnswers.filter(Boolean)
      if (answers.length === 0 || transitioning) return
      setTransitioning(true)

      const q = intakeQuestions[intakeStep]

      // Map display labels → canonical Russian values for scoring functions.
      // Intake scoring currently expects canonical Russian option values.
      // question.values[] holds canonical strings; question.options[] holds localized display labels.
      // values[] must stay Russian until lib/intake.ts scoring logic is refactored.
      const canonicalAnswers = answers.map((display) => {
        const idx = q.options.indexOf(display)
        return idx >= 0 ? q.values[idx] : display
      })

      const newIntake = applyIntakeAnswer(intake, q.id, canonicalAnswers)
      setIntake(newIntake)
      setMultiBuffer([])

      const userText = answers.join(', ')
      setMessages((prev) => [...prev, { kind: 'text', from: 'user', text: userText, isIntake: true }])

      const nextStep = intakeStep + 1

      setTimeout(() => {
        if (nextStep < intakeQuestions.length) {
          setIntakeStep(nextStep)
          setMessages((prev) => [
            ...prev,
            { kind: 'text', from: 'ai', text: intakeQuestions[nextStep].text, isIntake: true },
          ])
          setTransitioning(false)
        } else {
          const finalIntake = { ...newIntake, completed: true }
          setIntake(finalIntake)
          const finalPkg = recommendPackage(finalIntake)
          const initialScore = scoreIntake(finalIntake, [], false)
          setRecPkg(finalPkg)
          setScore(initialScore)

          setMessages((prev) => [
            ...prev,
            {
              kind: 'text',
              from: 'ai',
              text: dict.intakeCompleteMessage,
              isIntake: true,
            },
            { kind: 'summary' },
          ])
          setTransitioning(false)

          if (getInterestLevel(initialScore) !== 'cold') {
            void sendLead(finalIntake, finalPkg, initialScore, [], false)
          }
        }
      }, 420)
    },
    [intake, intakeStep, intakeQuestions, transitioning, sendLead, dict.intakeCompleteMessage],
  )

  const skipOptionalQuestion = useCallback(() => {
    if (transitioning) return
    setTransitioning(true)
    setMultiBuffer([])
    const nextStep = intakeStep + 1

    setTimeout(() => {
      if (nextStep < intakeQuestions.length) {
        setIntakeStep(nextStep)
        setMessages((prev) => [
          ...prev,
          { kind: 'text', from: 'ai', text: intakeQuestions[nextStep].text, isIntake: true },
        ])
        setTransitioning(false)
      } else {
        const finalIntake = { ...intake, completed: true }
        setIntake(finalIntake)
        const finalPkg = recommendPackage(finalIntake)
        const initialScore = scoreIntake(finalIntake, [], false)
        setRecPkg(finalPkg)
        setScore(initialScore)

        setMessages((prev) => [
          ...prev,
          {
            kind: 'text',
            from: 'ai',
            text: dict.intakeCompleteMessage,
            isIntake: true,
          },
          { kind: 'summary' },
        ])
        setTransitioning(false)

        if (getInterestLevel(initialScore) !== 'cold') {
          void sendLead(finalIntake, finalPkg, initialScore, [], false)
        }
      }
    }, 420)
  }, [intake, intakeStep, intakeQuestions, transitioning, sendLead, dict.intakeCompleteMessage])

  // ------------ message send core ------------

  const sendMessage = async (userText: string) => {
    if (!userText || loading || !chatId) return

    // Keep the session's sliding TTL window fresh while the user is active.
    touchChatSession(SITE_INSTANCE_ID)
    setInput('')
    setError(null)

    const priorHistory = messages
      .filter((m): m is TextMessage => m.kind === 'text' && !m.isIntake)
      .map((m) => ({
        role: m.from === 'user' ? ('user' as const) : ('assistant' as const),
        content: m.text,
      }))

    setMessages((prev) => [
      ...prev,
      { kind: 'text', from: 'user', text: userText, isIntake: false },
    ])

    // Free-form summary: extract channels/tasks/CRM/business from natural
    // messages so the package summary fills without the questionnaire.
    if (!intakeRef.current.completed) {
      const allUserTexts = [
        ...messages
          .filter((m): m is TextMessage => m.kind === 'text' && !m.isIntake && m.from === 'user')
          .map((m) => m.text),
        userText,
      ]
      const merged = mergeFreeformIntake(intakeRef.current, extractFreeformIntake(allUserTexts))
      setIntake(merged)
      setRecPkg(recommendPackage(merged))
    }

    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userText,
          chat_id: chatId,
          chat_history: priorHistory,
          reset_context: false,
          intake_context: intake.completed ? buildIntakeContextString(intake, !SHOW_DAMIWORKS_CHAT_PRICES) : undefined,
        }),
      })

      if (!res.ok) throw new Error('server_error')
      const data = (await res.json()) as {
        answer: string
        lead_status?: string | null
        lead_sent?: boolean
      }

      const aiMsg: Message = { kind: 'text', from: 'ai', text: data.answer, isIntake: false }
      setMessages((prev) => [...prev, aiMsg])

      // Lead status applies on both paths — free-form conversations collect
      // contacts too, not only the questionnaire flow.
      const currentChatId = chatIdRef.current || chatId
      if (data.lead_status) setLeadStatus(data.lead_status)
      if (data.lead_status === 'contact_collected') {
        setContactClosed(true)
        setLeadSent(true)
        localStorage.setItem(LEAD_CONTACT_KEY, currentChatId)
      } else if (intake.completed) {
        if (localStorage.getItem(LEAD_SENT_KEY) !== currentChatId) {
          // Intake data not yet sent — score and send if warm/hot. Idempotent.
          const allUserTexts = [
            ...messages
              .filter(
                (m): m is TextMessage => m.kind === 'text' && !m.isIntake && m.from === 'user',
              )
              .map((m) => m.text),
            userText,
          ]
          const newScore = scoreIntake(intake, allUserTexts, false)
          setScore(newScore)
          if (getInterestLevel(newScore) !== 'cold') {
            void sendLead(intake, recPkg, newScore, messages, false)
          }
        }
      }
    } catch {
      setError(dict.errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // ------------ intake start ------------

  const startIntake = () => {
    setMultiBuffer([])
    setIntakeStep(0)
    setChatMode('intake')
    setMessages((prev) => [
      ...prev,
      {
        kind: 'text',
        from: 'ai',
        text: dict.intakeStartMessage,
        isIntake: true,
      },
      { kind: 'text', from: 'ai', text: intakeQuestions[0].text, isIntake: true },
    ])
  }

  const handleIntroChip = (chip: string) => {
    // A clicked predefined quick reply disappears for the rest of the session.
    setUsedChips((prev) => (prev.includes(chip) ? prev : [...prev, chip]))
    // First chip in introChips is always the "start intake" action
    if (chip === dict.introChips[0]) {
      startIntake()
      return
    }
    setChatMode('chat')
    void sendMessage(chip)
  }

  // ------------ free chat & quick replies ------------

  const send = () => {
    const userText = input.trim()
    if (!userText) return
    if (chatMode === 'intro') setChatMode('chat')
    void sendMessage(userText)
  }

  const handlePostIntakeChip = (chip: string) => {
    setSummaryCollapsed(true)
    setChatMode('chat')
    void sendMessage(chip)
  }

  // ------------ reset ------------

  const reset = () => {
    const newId = resetChatSession(SITE_INSTANCE_ID).chat_id
    chatIdRef.current = newId
    localStorage.removeItem(LEAD_SENT_KEY)
    localStorage.removeItem(LEAD_CONTACT_KEY)
    sessionStorage.removeItem(MESSAGES_SESSION_KEY)
    sessionStorage.removeItem(INTAKE_SESSION_KEY)
    sessionStorage.removeItem(USED_CHIPS_SESSION_KEY)
    setChatId(newId)
    setMessages([{ kind: 'text', from: 'ai', text: dict.introMessage, isIntake: false }])
    setIntakeStep(0)
    setIntake(INITIAL_INTAKE)
    setMultiBuffer([])
    setTransitioning(false)
    setChatMode('intro')
    setInput('')
    setError(null)
    setLeadSent(false)
    setContactClosed(false)
    setLeadStatus(null)
    setScore(0)
    setRecPkg('Start')
    setSummaryCollapsed(false)
    setUsedChips([])
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send()
    }
  }

  // ------------ derived ------------

  const showIntakeChips = chatMode === 'intake' && !intake.completed && !transitioning
  const visibleIntroChips = filterUnusedChips(dict.introChips, usedChips)
  const showPreIntakeChips =
    !intake.completed &&
    chatMode !== 'intake' &&
    visibleIntroChips.length > 0 &&
    !contactClosed &&
    leadStatus !== 'contact_requested'
  // Hide chips once the user expressed intent (contact_requested) or contact is collected.
  const showPostIntakeChips = intake.completed && !contactClosed && leadStatus !== 'contact_requested'
  const showInput = chatMode === 'chat' || chatMode === 'intro' || intake.completed

  // ------------ render ------------

  return (
    <div className="bg-surface border border-border-col rounded-2xl flex flex-col min-h-[400px] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-col flex items-center gap-3">
        <div className="w-7 h-7 rounded-full bg-accent-soft flex items-center justify-center text-accent text-[10px] font-bold flex-shrink-0">
          AI
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-primary">DamiWorks AI</div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            <span className="text-xs text-secondary">{dict.onlineLabel}</span>
          </div>
        </div>
        <button
          onClick={reset}
          className="flex items-center gap-1 text-xs text-secondary hover:text-primary transition-colors flex-shrink-0"
          title={dict.resetTitle}
        >
          <RotateCcw size={12} />
          {dict.resetLabel}
        </button>
      </div>

      {/* Messages */}
      <div ref={messagesContainerRef} className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[380px]">
        {messages.map((msg, i) => {
          if (msg.kind === 'summary') {
            return (
              <SummaryCard
                key={i}
                intake={intake}
                pkg={recPkg}
                leadSent={leadSent}
                collapsed={summaryCollapsed}
                onToggleCollapse={() => setSummaryCollapsed((v) => !v)}
                onAskQuestion={() => {
                  setSummaryCollapsed(true)
                  setChatMode('chat')
                  setTimeout(() => inputRef.current?.focus(), 50)
                }}
                onSendLead={() => void sendLead(intake, recPkg, score, messages, true)}
                onEditAnswers={reset}
                dict={dict}
              />
            )
          }
          return (
            <div
              key={i}
              className={`flex ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`text-sm px-4 py-2.5 rounded-2xl max-w-[78%] leading-relaxed whitespace-pre-wrap ${
                  msg.from === 'user'
                    ? 'bg-accent-soft text-primary rounded-tr-sm'
                    : 'bg-bg border border-border-col text-primary rounded-tl-sm'
                }`}
              >
                {msg.text}
              </div>
            </div>
          )
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-bg border border-border-col rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        )}

      </div>

      {/* Error */}
      {error && (
        <div className="px-4 pb-1">
          <p className="text-xs text-red-500">{error}</p>
        </div>
      )}

      {/* Pre-intake chips (intro + chat mode, before intake completed) */}
      {showPreIntakeChips && (
        <div className="px-4 py-3 border-t border-border-col space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {visibleIntroChips.map((chip) => (
              <button
                key={chip}
                onClick={() => handleIntroChip(chip)}
                disabled={loading}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all disabled:opacity-50 ${
                  chip === dict.introChips[0]
                    ? 'bg-accent text-white border-accent hover:opacity-90'
                    : 'bg-bg border-border-col text-primary hover:border-accent/50 hover:text-accent'
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Intake chips */}
      {showIntakeChips && (
        <ChipsPanel
          question={intakeQuestions[intakeStep]}
          questionIndex={intakeStep}
          requiredStepCount={requiredStepCount}
          multiBuffer={multiBuffer}
          transitioning={transitioning}
          onSingleAnswer={(opt) => sendIntakeAnswer([opt])}
          onToggleBuffer={(opt) =>
            setMultiBuffer((prev) =>
              prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt],
            )
          }
          onConfirmMulti={() => sendIntakeAnswer(multiBuffer)}
          onSkip={skipOptionalQuestion}
          dict={dict}
        />
      )}

      {/* Post-intake chips (persistent after intake completed, until lead closed) */}
      {showPostIntakeChips && (
        <div className="px-4 py-3 border-t border-border-col space-y-2">
          {/* Calendly conversion row: booking is primary, leaving a contact stays
              available via the existing chat flow. Hidden when the URL is unset. */}
          {CALENDLY_URL && (
            <div className="flex flex-wrap gap-1.5">
              <a
                href={CALENDLY_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-full text-xs font-medium border bg-accent text-white border-accent hover:opacity-90 transition-all"
              >
                {dict.bookCallButton}
              </a>
              <button
                onClick={() => handlePostIntakeChip(dict.sendLeadChipLabel)}
                disabled={loading}
                className="px-3 py-1.5 rounded-full text-xs font-medium border border-accent/30 text-accent bg-accent-soft/40 hover:bg-accent-soft hover:border-accent/60 transition-all disabled:opacity-50"
              >
                {dict.leaveContactButton}
              </button>
            </div>
          )}
          <div className="flex flex-wrap gap-1.5">
            {dict.postIntakeChips
              .filter((chip) => !CALENDLY_URL || chip !== dict.sendLeadChipLabel)
              .map((chip) => (
                <button
                  key={chip}
                  onClick={() => handlePostIntakeChip(chip)}
                  disabled={loading}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all disabled:opacity-50 ${
                    chip === dict.sendLeadChipLabel
                      ? 'bg-accent text-white border-accent hover:opacity-90'
                      : 'border-accent/30 text-accent bg-accent-soft/40 hover:bg-accent-soft hover:border-accent/60'
                  }`}
                >
                  {chip}
                </button>
              ))}
          </div>
        </div>
      )}

      {/* Contact requested — assistant asked for contact info. Offer booking a
          call as the primary path; the secondary button focuses the input so the
          user can type their contact as before. Never changes lead state. */}
      {!contactClosed && leadStatus === 'contact_requested' && CALENDLY_URL && (
        <div className="px-4 py-3 border-t border-border-col">
          <div className="flex flex-wrap gap-1.5">
            <a
              href={CALENDLY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded-full text-xs font-medium border bg-accent text-white border-accent hover:opacity-90 transition-all"
            >
              {dict.bookCallButton}
            </a>
            <button
              onClick={() => inputRef.current?.focus()}
              className="px-3 py-1.5 rounded-full text-xs font-medium border border-accent/30 text-accent bg-accent-soft/40 hover:bg-accent-soft hover:border-accent/60 transition-all"
            >
              {dict.leaveContactButton}
            </button>
          </div>
        </div>
      )}

      {/* Lead closed — contact collected. Show only a status pill. */}
      {contactClosed && (
        <div className="px-4 py-3 border-t border-border-col">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-green-500/10 text-green-600 border border-green-500/30">
            <CheckCircle2 size={12} className="flex-shrink-0" />
            {dict.contactClosedPill}
          </span>
        </div>
      )}

      {/* Free chat input — read-only once the lead is closed */}
      {showInput && (
        <div className="px-4 py-3 border-t border-border-col flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={2000}
            rows={1}
            placeholder={contactClosed ? dict.contactClosedInputPlaceholder : dict.inputPlaceholder}
            disabled={loading || contactClosed}
            className="flex-1 bg-bg border border-border-col rounded-xl px-4 py-2 text-sm text-primary placeholder:text-secondary focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-60"
            style={{ minHeight: '38px', maxHeight: '120px' }}
          />
          <button
            onClick={() => void send()}
            disabled={loading || contactClosed || !input.trim() || !chatId}
            aria-label={dict.sendAriaLabel}
            className="w-9 h-9 bg-accent rounded-xl flex items-center justify-center text-white hover:opacity-90 transition-opacity flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
