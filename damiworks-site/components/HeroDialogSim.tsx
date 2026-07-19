'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import type { DictAdminHandoff, DictHeroChat } from '@/lib/i18n'

// ---------------------------------------------------------------------------
// HeroDialogSim — self-playing scripted AI↔patient dialog for the RU hero.
// No backend: a hardcoded scenario plays in a loop (typing indicator, bubbles
// appear one by one, AI answers in multiple bubbles — the multi-bubble UX).
// The dialog ends with the same «Новая заявка» card the AdminHandoff section
// shows below — the hero literally hands the visitor over to section 2.
// ---------------------------------------------------------------------------

type SimMessage = { from: 'user' | 'ai'; text: string }

// Scripted scenario. Mirrors dict.adminHandoff.card (стоматология, сегодня
// после 17:00, masked phone) so the final card matches the story told below.
const SCRIPT: SimMessage[] = [
  { from: 'user', text: 'Здравствуйте! Болит зуб, хочу попасть к врачу сегодня.' },
  { from: 'ai', text: 'Здравствуйте! Помогу записаться к стоматологу. Подскажите, в какое время вам удобно подойти?' },
  { from: 'user', text: 'Лучше вечером, после 17:00.' },
  { from: 'ai', text: 'Хорошо, передам администратору, что вам удобно сегодня после 17:00.' },
  { from: 'ai', text: 'Оставьте, пожалуйста, номер телефона — с вами свяжутся и подтвердят время.' },
  { from: 'user', text: '+7 707 ••• •• 44' },
  { from: 'ai', text: 'Спасибо! Передаю заявку администратору — с вами свяжутся, чтобы подтвердить запись.' },
]

const CARD_HOLD_MS = 5200
const RESTART_FADE_MS = 400

function rand(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

type Props = {
  chat: Pick<DictHeroChat, 'headerTitle' | 'onlineLabel'>
  card: DictAdminHandoff['card']
}

export default function HeroDialogSim({ chat, card }: Props) {
  const [visibleCount, setVisibleCount] = useState(0)
  const [showTyping, setShowTyping] = useState(false)
  const [showCard, setShowCard] = useState(false)
  const [fadingOut, setFadingOut] = useState(false)

  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([])
  const messagesContainerRef = useRef<HTMLDivElement | null>(null)

  function schedule(fn: () => void, delay: number): void {
    timersRef.current.push(setTimeout(fn, delay))
  }

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setVisibleCount(SCRIPT.length)
      setShowCard(true)
      return
    }

    const timers = timersRef.current

    function step(idx: number): void {
      if (idx >= SCRIPT.length) {
        schedule(() => setShowCard(true), 700)
        schedule(() => setFadingOut(true), 700 + CARD_HOLD_MS)
        schedule(() => {
          setVisibleCount(0)
          setShowCard(false)
          setFadingOut(false)
          step(0)
        }, 700 + CARD_HOLD_MS + RESTART_FADE_MS)
        return
      }

      const msg = SCRIPT[idx]
      if (msg.from === 'user') {
        schedule(() => {
          setVisibleCount(idx + 1)
          step(idx + 1)
        }, rand(1300, 1900))
      } else {
        schedule(() => {
          setShowTyping(true)
          schedule(() => {
            setShowTyping(false)
            setVisibleCount(idx + 1)
            step(idx + 1)
          }, rand(1100, 1600))
        }, rand(500, 900))
      }
    }

    step(0)
    return () => timers.forEach(clearTimeout)
  }, [])

  useEffect(() => {
    const el = messagesContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [visibleCount, showTyping, showCard])

  return (
    <div className="rounded-2xl border border-border-col bg-surface p-5 shadow-lg shadow-accent/5">
      {/* Chat header */}
      <div className="mb-4 flex items-center gap-3 border-b border-border-col pb-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[10px] font-bold text-accent">
          AI
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-primary">{chat.headerTitle}</div>
          <div className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />
            <span className="text-xs text-secondary">{chat.onlineLabel}</span>
          </div>
        </div>
      </div>

      {/* Messages + final card — fixed height, scrolls internally */}
      <div
        ref={messagesContainerRef}
        aria-hidden="true"
        className={`h-[300px] space-y-2.5 overflow-y-auto overscroll-contain pr-1 transition-opacity motion-reduce:transition-none sm:h-[340px] ${
          fadingOut ? 'opacity-0 duration-300' : 'opacity-100 duration-500'
        }`}
      >
        {SCRIPT.slice(0, visibleCount).map((msg, i) => (
          <div key={i} className={`flex animate-fadeInUp ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.from === 'user'
                  ? 'rounded-tr-sm bg-accent-soft text-primary'
                  : 'rounded-tl-sm border border-border-col bg-bg text-primary'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {showTyping && (
          <div className="flex animate-fadeInUp justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-border-col bg-bg px-4 py-3">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary/60 [animation-delay:0ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary/60 [animation-delay:200ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary/60 [animation-delay:400ms]" />
            </div>
          </div>
        )}

        {/* The outcome: the same заявка card the page explains right below */}
        {showCard && (
          <div className="animate-fadeInUp rounded-xl border border-accent/25 bg-accent-soft/40 p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-green-500 motion-reduce:animate-none" />
              <span className="text-xs font-semibold text-primary">{card.title}</span>
            </div>
            <dl className="grid grid-cols-2 gap-x-5 gap-y-2 text-xs">
              {card.fields.map((field) => (
                <div key={field.label} className="last:col-span-2">
                  <dt className="mb-0.5 text-secondary">{field.label}</dt>
                  <dd className="font-medium text-primary">{field.value}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 rounded-lg border border-accent/30 bg-surface px-3 py-1.5 text-center text-xs font-medium text-accent">
              {card.pill}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export function HeroDialogCta({ label }: { label: string }) {
  return (
    <a
      href="/ru/demo"
      className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-accent transition-opacity hover:opacity-80"
    >
      {label}
      <ArrowRight size={15} aria-hidden="true" />
    </a>
  )
}
