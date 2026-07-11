'use client'

import { useState } from 'react'
import { AlertCircle, Check, X } from 'lucide-react'
import type { DictPain, DictVsChatbot, DictAutomate, DictWhatWeNeed, DictTrust } from '@/lib/i18n'

// Simple copy-driven sections for the homepage narrative:
// pain -> vs-chatbot -> what to automate -> what we need -> trust.

export function PainSection({ dict }: { dict: DictPain }) {
  return (
    <section className="py-20 bg-surface border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-10 text-center">
          {dict.headline}
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-[0.95fr_1.05fr] gap-8 items-start">
          <div className="bg-bg border border-accent/25 rounded-2xl p-6 lg:p-8">
            <p className="text-sm font-semibold uppercase tracking-wide text-accent mb-4">
              {dict.emphasisTitle}
            </p>
            <p className="text-2xl lg:text-3xl font-bold leading-tight text-primary">
              {dict.emphasisText}
            </p>
          </div>
          <div className="space-y-3">
            {dict.items.map((item) => (
              <div
                key={item}
                className="flex items-start gap-3 bg-bg border border-border-col rounded-xl px-5 py-3.5"
              >
                <AlertCircle size={16} className="text-accent mt-0.5 flex-shrink-0" />
                <span className="text-sm text-primary leading-relaxed">{item}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="text-center text-secondary max-w-3xl mx-auto mt-10 leading-relaxed">
          {dict.bottomLine}
        </p>
      </div>
    </section>
  )
}

export function VsChatbotSection({ dict }: { dict: DictVsChatbot }) {
  return (
    <section className="py-20 bg-surface border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mx-auto text-center mb-12">
          <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-4">{dict.headline}</h2>
          <p className="text-secondary leading-relaxed mb-2">{dict.description1}</p>
          <p className="text-secondary leading-relaxed">{dict.description2}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
          <div className="bg-bg border border-border-col rounded-2xl p-6">
            <h3 className="text-base font-semibold text-secondary mb-4">{dict.chatbotCard.title}</h3>
            <ul className="space-y-3">
              {dict.chatbotCard.items.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-secondary">
                  <X size={15} className="text-secondary/50 mt-0.5 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-bg border-2 border-accent/40 rounded-2xl p-6">
            <h3 className="text-base font-semibold text-primary mb-4">{dict.aiCard.title}</h3>
            <ul className="space-y-3">
              {dict.aiCard.items.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-primary">
                  <Check size={15} className="text-accent mt-0.5 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}

export function AutomateSection({ dict }: { dict: DictAutomate }) {
  const [activeIdx, setActiveIdx] = useState(0)
  const active = dict.items[activeIdx]

  return (
    <section className="py-20 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-12 text-center">
          {dict.headline}
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-[0.8fr_1.2fr] gap-6 items-start">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-1 gap-2">
            {dict.items.map((item, idx) => {
              const isActive = idx === activeIdx
              return (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => setActiveIdx(idx)}
                  className={`min-h-12 rounded-xl border px-4 py-3 text-left text-sm font-semibold transition-colors ${
                    isActive
                      ? 'border-accent bg-accent-soft text-accent'
                      : 'border-border-col bg-surface text-primary hover:border-accent/40'
                  }`}
                  aria-pressed={isActive}
                >
                  {item.title}
                </button>
              )
            })}
          </div>

          <div className="bg-surface border border-border-col rounded-2xl p-6 lg:p-8 shadow-sm">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-accent mb-2">
                  {dict.actionLabel}
                </p>
                <p className="text-sm text-secondary leading-relaxed">{active.description}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-accent mb-2">
                  {dict.outcomeLabel}
                </p>
                <p className="text-sm text-primary font-medium leading-relaxed">{active.outcome}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-accent mb-2">
                  {dict.exampleLabel}
                </p>
                <p className="text-sm text-secondary leading-relaxed">{active.example}</p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-sm text-secondary mt-10">{dict.bottomLine}</p>
      </div>
    </section>
  )
}

export function WhatWeNeedSection({ dict }: { dict: DictWhatWeNeed }) {
  return (
    <section className="py-20 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-12 text-center">
          {dict.headline}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {dict.items.map((item) => (
            <div key={item.number} className="bg-surface border border-border-col rounded-2xl p-6">
              <div className="text-xs font-semibold text-accent tracking-widest mb-3">
                {item.number}
              </div>
              <h3 className="text-base font-semibold text-primary mb-2">{item.title}</h3>
              <p className="text-sm text-secondary leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-primary font-medium mt-10">{dict.bottomLine}</p>
      </div>
    </section>
  )
}

export function TrustSection({ dict }: { dict: DictTrust }) {
  return (
    <section id="trust" className="scroll-mt-20 py-20 bg-surface border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mx-auto text-center mb-12">
          <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-4">{dict.headline}</h2>
          <p className="text-secondary leading-relaxed mb-2">{dict.description1}</p>
          <p className="text-secondary leading-relaxed">{dict.description2}</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-4xl mx-auto">
          {dict.cards.map((card) => (
            <div
              key={card}
              className="flex items-start gap-2.5 bg-bg border border-border-col rounded-xl px-4 py-3.5"
            >
              <Check size={15} className="text-accent mt-0.5 flex-shrink-0" />
              <span className="text-sm text-primary leading-relaxed">{card}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
