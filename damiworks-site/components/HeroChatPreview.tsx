'use client'

import { useEffect, useRef, useState } from 'react'
import type { DictHeroChat, DictHeroSimMessage, DictHeroLeadState } from '@/lib/i18n'

function rand(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

const LEAD_FIELDS = ['service', 'objection', 'need', 'time', 'status'] as const
type LeadField = (typeof LEAD_FIELDS)[number]

export default function HeroChatPreview({ dict }: { dict: DictHeroChat }) {
  const [scenarioIdx, setScenarioIdx] = useState(0)
  const firstMessage = dict.scenarios[0]?.messages[0]
  const [visibleMessages, setVisibleMessages] = useState<DictHeroSimMessage[]>(() => firstMessage ? [firstMessage] : [])
  const [showTyping, setShowTyping] = useState(false)
  const [leadIdx, setLeadIdx] = useState(firstMessage?.leadStateIndex ?? 0)
  const [highlighted, setHighlighted] = useState<Set<LeadField>>(new Set())

  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([])
  const messagesContainerRef = useRef<HTMLDivElement | null>(null)

  function schedule(fn: () => void, delay: number): void {
    const id = setTimeout(fn, delay)
    timersRef.current.push(id)
  }

  function clearAll(): void {
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []
  }

  function applyHighlight(leadStates: DictHeroLeadState[], nextIdx: number): void {
    const prev = leadStates[nextIdx - 1]
    const curr = leadStates[nextIdx]
    setLeadIdx(nextIdx)
    const changed = new Set(LEAD_FIELDS.filter((f) => prev[f] !== curr[f]))
    if (changed.size > 0) {
      setHighlighted(changed)
      schedule(() => setHighlighted(new Set()), 600)
    }
  }

  function runScenario(scenIdx: number, startAt = 0): void {
    const scenario = dict.scenarios[scenIdx]

    function step(msgIdx: number): void {
      if (msgIdx >= scenario.messages.length) {
        if (scenIdx < dict.scenarios.length - 1) {
          schedule(() => {
            setScenarioIdx(scenIdx + 1)
            setVisibleMessages([])
            setLeadIdx(0)
            setHighlighted(new Set())
            runScenario(scenIdx + 1)
          }, 3000)
        }
        // last scenario: stop, keep final state visible
        return
      }

      const msg = scenario.messages[msgIdx]

      if (msg.from === 'user') {
        schedule(() => {
          setVisibleMessages((prev) => [...prev, msg])
          if (msg.leadStateIndex !== undefined) {
            applyHighlight(scenario.leadStates, msg.leadStateIndex)
          }
          step(msgIdx + 1)
        }, rand(1400, 2200))
      } else {
        schedule(() => {
          setShowTyping(true)
          schedule(() => {
            setShowTyping(false)
            setVisibleMessages((prev) => [...prev, msg])
            if (msg.leadStateIndex !== undefined) {
              applyHighlight(scenario.leadStates, msg.leadStateIndex)
            }
            step(msgIdx + 1)
          }, rand(1400, 2000))
        }, rand(600, 1000))
      }
    }

    step(startAt)
  }

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (mq.matches) {
      const lastScenario = dict.scenarios[dict.scenarios.length - 1]
      setScenarioIdx(dict.scenarios.length - 1)
      setVisibleMessages(lastScenario.messages)
      setLeadIdx(lastScenario.leadStates.length - 1)
      return
    }
    runScenario(0, firstMessage ? 1 : 0)
    return () => clearAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const el = messagesContainerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [visibleMessages, showTyping])

  const lead = dict.scenarios[scenarioIdx].leadStates[leadIdx]
  const lbl = dict.leadFieldLabels

  function fieldClass(field: LeadField): string {
    return highlighted.has(field)
      ? 'transition-colors duration-500 bg-accent-soft/60 rounded px-1 -mx-1'
      : 'transition-colors duration-500'
  }

  return (
    <div className="bg-surface border border-border-col rounded-2xl p-5 shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 pb-4 border-b border-border-col">
        <div className="w-8 h-8 rounded-full bg-accent-soft flex items-center justify-center text-accent text-[10px] font-bold flex-shrink-0">
          AI
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium text-primary">{dict.headerTitle}</div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
            <span className="text-xs text-secondary">{dict.onlineLabel}</span>
          </div>
        </div>
        <span className="ml-auto text-xs text-secondary flex-shrink-0">11:42</span>
      </div>

      {/* Messages — fixed height, scrolls internally */}
      <div
        ref={messagesContainerRef}
        className="h-[240px] overflow-y-auto overscroll-contain space-y-2.5 mb-4 pr-1"
      >
        {visibleMessages.map((msg, i) => (
          <div
            key={`${scenarioIdx}-${i}`}
            className={`flex animate-fadeInUp ${msg.from === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`text-sm px-4 py-2.5 rounded-2xl max-w-[85%] leading-relaxed ${
                msg.from === 'user'
                  ? 'bg-accent-soft text-primary rounded-tr-sm'
                  : 'bg-gray-100 text-primary rounded-tl-sm'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {showTyping && (
          <div className="flex justify-start animate-fadeInUp">
            <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary/60 animate-pulse [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-secondary/60 animate-pulse [animation-delay:200ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-secondary/60 animate-pulse [animation-delay:400ms]" />
            </div>
          </div>
        )}
      </div>

      {/* Lead card */}
      <div className="bg-bg border border-border-col rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
          <span className="text-xs font-semibold text-primary">{dict.leadLabel}</span>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <div className={fieldClass('service')}>
            <dt className="text-secondary mb-0.5">{lbl.service}</dt>
            <dd className="text-primary font-medium">{lead.service}</dd>
          </div>
          <div className={fieldClass('objection')}>
            <dt className="text-secondary mb-0.5">{lbl.objection}</dt>
            <dd className="text-primary font-medium">{lead.objection}</dd>
          </div>
          <div className={fieldClass('need')}>
            <dt className="text-secondary mb-0.5">{lbl.need}</dt>
            <dd className="text-primary font-medium">{lead.need}</dd>
          </div>
          <div className={fieldClass('time')}>
            <dt className="text-secondary mb-0.5">{lbl.time}</dt>
            <dd className="text-primary font-medium">{lead.time}</dd>
          </div>
          <div className={`col-span-2 ${fieldClass('status')}`}>
            <dt className="text-secondary mb-0.5">{lbl.status}</dt>
            <dd className="text-accent font-semibold">{lead.status}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
