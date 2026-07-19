'use client'

import { useState } from 'react'
import type { DictFaq } from '@/lib/i18n'

// FAQ as a controlled accordion: one item open at a time, smooth height
// transition via the grid-rows trick (animates with grid-template-rows only).
export default function FaqSection({ dict }: { dict: DictFaq }) {
  const [openIdx, setOpenIdx] = useState<number | null>(0)

  return (
    <section id="faq" className="scroll-mt-20 border-t border-border-col bg-surface py-20">
      <div className="mx-auto max-w-3xl px-6">
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-bold text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-3 text-secondary">{dict.subheadline}</p>
        </div>
        <div className="space-y-3">
          {dict.items.map((item, index) => {
            const isOpen = openIdx === index
            return (
              <div
                key={item.question}
                className={`rounded-2xl border bg-bg px-5 transition-colors ${
                  isOpen ? 'border-accent/30' : 'border-border-col'
                }`}
              >
                <h3>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={`faq-answer-${index}`}
                    onClick={() => setOpenIdx(isOpen ? null : index)}
                    className="flex w-full cursor-pointer items-center justify-between gap-4 py-4 text-left font-semibold text-primary"
                  >
                    {item.question}
                    <span
                      className={`text-xl font-normal text-accent transition-transform motion-reduce:transition-none ${
                        isOpen ? 'rotate-45' : ''
                      }`}
                      aria-hidden="true"
                    >
                      +
                    </span>
                  </button>
                </h3>
                <div
                  id={`faq-answer-${index}`}
                  role="region"
                  className={`grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none ${
                    isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                  }`}
                >
                  <div className="overflow-hidden">
                    <p className="pb-4 pr-8 text-sm leading-relaxed text-secondary">{item.answer}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
