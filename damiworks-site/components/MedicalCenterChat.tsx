'use client'

import { useEffect, useRef, useState } from 'react'
import { Send, RotateCcw } from 'lucide-react'
import type { DictMedicalChatLabels } from '@/lib/i18n'
import MessageFeedback from '@/components/MessageFeedback'
import { createMessageId, ensureMessageIds } from '@/lib/qualityFeedback'
import {
  MEDICAL_CENTER_SESSION_TTL_MS,
  loadChatSession,
  resetChatSession,
  touchChatSession,
} from '@/lib/chatSession'

// ---------------------------------------------------------------------------
// MedicalCenterChat — live chat for the Medical Center (MedNova Clinic) demo.
//
// Uses instance_id="damiworks_medical_center_demo" — separate from the DamiWorks
// consultant, English School and custom demos. The backend serves answers from
// a preloaded static clinic knowledge base with deterministic medical guardrails.
// ---------------------------------------------------------------------------

const MEDICAL_INSTANCE_ID = 'damiworks_medical_center_demo'
const MESSAGES_SESSION_KEY = 'damiworks_medical_center_messages'

export type MedicalMessage = { id?: string; from: 'user' | 'ai'; text: string }

export type MedicalBackendState = {
  leadStatus: 'open' | 'contact_requested' | 'contact_collected' | 'closed' | null
  specialty: string | null
  symptomsOrGoal: string | null
  preferredTime: string | null
  selectedSlot: string | null
  urgencyFlag: string | null
  conversationStatus: string | null
  conversationStatusLabel: string | null
}

type Props = {
  dict: DictMedicalChatLabels
  onConversationUpdate?: (messages: MedicalMessage[]) => void
  onStateUpdate?: (state: MedicalBackendState) => void
}

// Rotates through dict.loadingStages while the backend thinks — the wait
// itself narrates the product ("AI reads the question… builds the summary…").
function LoadingStages({ stages }: { stages: string[] }) {
  const [stageIdx, setStageIdx] = useState(0)

  useEffect(() => {
    if (stageIdx >= stages.length - 1) return
    const id = setTimeout(() => setStageIdx((i) => i + 1), 1600)
    return () => clearTimeout(id)
  }, [stageIdx, stages.length])

  return <span className="text-xs text-secondary">{stages[stageIdx]}</span>
}

export default function MedicalCenterChat({ dict, onConversationUpdate, onStateUpdate }: Props) {
  const [messages, setMessages] = useState<MedicalMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chatId, setChatId] = useState('')

  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const initDone = useRef(false)

  // ------------ initialization ------------

  useEffect(() => {
    if (initDone.current) return
    initDone.current = true

    const { session, expired } = loadChatSession(MEDICAL_INSTANCE_ID, MEDICAL_CENTER_SESSION_TTL_MS)
    setChatId(session.chat_id)
    if (expired) sessionStorage.removeItem(MESSAGES_SESSION_KEY)

    const stored = expired ? null : sessionStorage.getItem(MESSAGES_SESSION_KEY)
    if (stored) {
      try {
        const parsed = ensureMessageIds(JSON.parse(stored) as MedicalMessage[], 'medical')
        if (parsed.length > 0) {
          setMessages(parsed)
          return
        }
      } catch {
        // ignore corrupt storage
      }
    }
    setMessages([{ id: createMessageId('medical'), from: 'ai', text: dict.introMessage }])
  }, [dict.introMessage])

  // ------------ sessionStorage persistence ------------

  useEffect(() => {
    if (messages.length > 0) {
      sessionStorage.setItem(MESSAGES_SESSION_KEY, JSON.stringify(messages))
    }
  }, [messages])

  // ------------ notify parent of conversation state ------------

  useEffect(() => {
    onConversationUpdate?.(messages)
  }, [messages, onConversationUpdate])

  // ------------ auto-scroll ------------

  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  // ------------ send ------------

  const sendMessage = async (userText: string) => {
    if (!userText.trim() || loading || !chatId) return

    touchChatSession(MEDICAL_INSTANCE_ID)
    setInput('')
    setError(null)

    const priorHistory = messages.map((m) => ({
      role: m.from === 'user' ? ('user' as const) : ('assistant' as const),
      content: m.text,
    }))
    const userMessageId = createMessageId('medical')
    const assistantMessageId = createMessageId('medical')

    setMessages((prev) => [...prev, { id: userMessageId, from: 'user', text: userText }])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userText,
          chat_id: chatId,
          instance_id: MEDICAL_INSTANCE_ID,
          message_id: userMessageId,
          response_message_id: assistantMessageId,
          source: 'web_chat',
          chat_history: priorHistory,
          reset_context: false,
        }),
      })

      if (!res.ok) {
        setError(dict.errorMessage)
        return
      }
      const data = (await res.json()) as {
        answer: string
        lead_status?: string | null
        metadata?: {
          state?: Record<string, string | undefined>
          conversation_status?: string | null
          conversation_status_label?: string | null
        }
      }
      setMessages((prev) => [...prev, { id: assistantMessageId, from: 'ai', text: data.answer }])
      if (onStateUpdate) {
        const s = data.metadata?.state ?? {}
        onStateUpdate({
          leadStatus: (data.lead_status ?? null) as MedicalBackendState['leadStatus'],
          specialty: s.specialty || null,
          symptomsOrGoal: s.symptoms_or_goal || null,
          preferredTime: s.preferred_time || null,
          selectedSlot: s.selected_slot || null,
          urgencyFlag: s.urgency_flag || null,
          conversationStatus: data.metadata?.conversation_status ?? null,
          conversationStatusLabel: data.metadata?.conversation_status_label ?? null,
        })
      }
    } catch {
      setError(dict.errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const send = () => {
    const userText = input.trim()
    if (!userText) return
    void sendMessage(userText)
  }

  const reset = () => {
    const session = resetChatSession(MEDICAL_INSTANCE_ID)
    sessionStorage.removeItem(MESSAGES_SESSION_KEY)
    setChatId(session.chat_id)
    setMessages([{ id: createMessageId('medical'), from: 'ai', text: dict.introMessage }])
    setInput('')
    setError(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  // Quick replies are shown until the visitor sends their first message.
  const showQuickReplies = !messages.some((m) => m.from === 'user')

  // ------------ render ------------

  return (
    <div className="bg-surface border border-border-col rounded-2xl flex flex-col min-h-[480px] sm:min-h-[400px] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-col flex items-center gap-3">
        <div className="w-7 h-7 rounded-full bg-accent-soft flex items-center justify-center text-accent text-[10px] font-bold flex-shrink-0">
          AI
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-primary">{dict.headerTitle}</div>
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
      <div
        ref={messagesContainerRef}
        className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[460px] sm:max-h-[380px]"
      >
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className="max-w-[78%]">
              <div
                className={`text-sm px-4 py-2.5 rounded-2xl leading-relaxed whitespace-pre-wrap ${
                  msg.from === 'user'
                    ? 'bg-accent-soft text-primary rounded-tr-sm'
                    : 'bg-bg border border-border-col text-primary rounded-tl-sm'
                }`}
              >
                {msg.text}
              </div>
              {msg.from === 'ai' && (
                <MessageFeedback
                  instanceId={MEDICAL_INSTANCE_ID}
                  chatId={chatId}
                  message={msg}
                  messages={messages}
                  metadata={{ component: 'MedicalCenterChat' }}
                />
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-bg border border-border-col rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-bounce [animation-delay:300ms]" />
              </span>
              {dict.loadingStages && dict.loadingStages.length > 0 && (
                <LoadingStages stages={dict.loadingStages} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Quick replies */}
      {showQuickReplies && (
        <div className="px-4 pb-2 flex flex-wrap gap-2">
          {dict.quickReplies.map((chip) => (
            <button
              key={chip}
              onClick={() => void sendMessage(chip)}
              disabled={loading || !chatId}
              className="text-xs px-3 py-1.5 rounded-full border border-border-col text-secondary hover:text-primary hover:border-accent transition-colors disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="px-4 pb-1">
          <p className="text-xs text-red-500">{error}</p>
        </div>
      )}

      {/* Input */}
      <div className="px-4 py-3 border-t border-border-col flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={2000}
          rows={2}
          placeholder={dict.inputPlaceholder}
          disabled={loading}
          className="flex-1 bg-bg border border-border-col rounded-xl px-4 py-2 text-sm text-primary placeholder:text-secondary focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-60"
          style={{ minHeight: '58px', maxHeight: '120px' }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim() || !chatId}
          aria-label={dict.sendAriaLabel}
          className="w-9 h-9 bg-accent rounded-xl flex items-center justify-center text-white hover:opacity-90 transition-opacity flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  )
}
