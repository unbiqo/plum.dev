'use client'

import { useEffect, useRef, useState } from 'react'
import { Send, RotateCcw } from 'lucide-react'
import type { DictCustomDemoChat } from '@/lib/i18n'

// ---------------------------------------------------------------------------
// CustomDemoChat — separate live roleplay/simulation chat.
//
// Independent from the DamiWorks consultant (LiveChat): its own chat_id (fresh per
// page load via module singleton), sessionStorage for messages, its own
// instance_id ("damiworks_custom_demo"), and NO guided
// intake / lead collection / package pricing. The backend separates behavior by
// instance_id; here the AI plays the user's future AI employee answering customers.
// ---------------------------------------------------------------------------

const CUSTOM_DEMO_INSTANCE_ID = 'damiworks_custom_demo'
const MESSAGES_SESSION_KEY = 'damiworks_custom_demo_messages'

// Fresh UUID per page load (module var resets on reload). Shared across tab
// mounts in the same page session so tab switches don't break the chat session.
let _sessionChatId: string | null = null
function getSessionChatId(): string {
  if (!_sessionChatId) _sessionChatId = crypto.randomUUID()
  return _sessionChatId
}

type Message = { from: 'user' | 'ai'; text: string }

export default function CustomDemoChat({ dict }: { dict: DictCustomDemoChat }) {
  const [messages, setMessages] = useState<Message[]>([])
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

    setChatId(getSessionChatId())

    const stored = sessionStorage.getItem(MESSAGES_SESSION_KEY)
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as Message[]
        if (parsed.length > 0) {
          setMessages(parsed)
          return
        }
      } catch {
        // ignore corrupt storage
      }
    }
    setMessages([{ from: 'ai', text: dict.introMessage }])
  }, [dict.introMessage])

  // ------------ sessionStorage persistence ------------

  useEffect(() => {
    if (messages.length > 0) {
      sessionStorage.setItem(MESSAGES_SESSION_KEY, JSON.stringify(messages))
    }
  }, [messages])

  // ------------ auto-scroll — scrolls only the message container, not the page ------------

  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  // ------------ send ------------

  const sendMessage = async (userText: string) => {
    if (!userText || loading || !chatId) return

    setInput('')
    setError(null)

    const priorHistory = messages.map((m) => ({
      role: m.from === 'user' ? ('user' as const) : ('assistant' as const),
      content: m.text,
    }))

    setMessages((prev) => [...prev, { from: 'user', text: userText }])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userText,
          chat_id: chatId,
          instance_id: CUSTOM_DEMO_INSTANCE_ID,
          chat_history: priorHistory,
          reset_context: false,
        }),
      })

      if (!res.ok) throw new Error('server_error')
      const data = (await res.json()) as { answer: string }
      setMessages((prev) => [...prev, { from: 'ai', text: data.answer }])
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
    _sessionChatId = crypto.randomUUID()
    sessionStorage.removeItem(MESSAGES_SESSION_KEY)
    setChatId(_sessionChatId)
    setMessages([{ from: 'ai', text: dict.introMessage }])
    setInput('')
    setError(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  // ------------ render ------------

  return (
    <div className="bg-surface border border-border-col rounded-2xl flex flex-col min-h-[400px] overflow-hidden">
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
      <div ref={messagesContainerRef} className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[380px]">
        {messages.map((msg, i) => (
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
        ))}

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

      {/* Free chat input */}
      <div className="px-4 py-3 border-t border-border-col flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={2000}
          rows={1}
          placeholder={dict.inputPlaceholder}
          disabled={loading}
          className="flex-1 bg-bg border border-border-col rounded-xl px-4 py-2 text-sm text-primary placeholder:text-secondary focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-60"
          style={{ minHeight: '38px', maxHeight: '120px' }}
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
