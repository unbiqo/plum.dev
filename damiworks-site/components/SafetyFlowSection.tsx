'use client'

import { useRef, useState } from 'react'
import { ShieldCheck, Siren } from 'lucide-react'
import type { DictSafetyFlow } from '@/lib/i18n'

// Fixed tones by tab order: answers (green), clarifies (amber), hands off
// (brand accent — a deliberate feature, not a fail state, so no alarm red)
// and the alarming-symptoms tab (red is honest here: the AI stops and points
// to urgent care).
const TAB_TONES = [
  { dot: 'bg-green-500', active: 'border-green-500/40 bg-green-500/10 text-primary' },
  { dot: 'bg-amber-400', active: 'border-amber-400/50 bg-amber-400/10 text-primary' },
  { dot: 'bg-accent', active: 'border-accent/40 bg-accent-soft/60 text-primary' },
  { dot: 'bg-red-500', active: 'border-red-500/40 bg-red-500/10 text-primary' },
]

// «AI знает, где отвечать, а где передать человеку» — the three decision
// states plus «Тревожные симптомы» as tabs, each with a mini example exchange.
export default function SafetyFlowSection({ dict }: { dict: DictSafetyFlow }) {
  const [selected, setSelected] = useState(0)
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])

  // 4 panels: the 3 states + the alarming-symptoms tab built from the note.
  const alertNote = dict.states.find((s) => s.note)?.note ?? ''
  const panels = [
    ...dict.states.map((s) => ({ title: s.title, description: s.description })),
    { title: dict.alertTabTitle, description: alertNote },
  ]

  const onKeyDown = (event: React.KeyboardEvent) => {
    const dir = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (dir === 0) return
    event.preventDefault()
    const next = (selected + dir + panels.length) % panels.length
    setSelected(next)
    tabRefs.current[next]?.focus()
  }

  const example = dict.examples[selected]
  const tone = TAB_TONES[selected] ?? TAB_TONES[TAB_TONES.length - 1]

  return (
    <section id="trust" className="scroll-mt-20 border-t border-border-col bg-bg py-20">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-6 lg:grid-cols-[1fr_1.1fr] lg:items-center lg:gap-14">
        {/* Left: the claim + guarantees */}
        <div>
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 leading-relaxed text-secondary">{dict.subheadline}</p>
          <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2">
            {dict.guarantees.map((guarantee) => (
              <li key={guarantee} className="flex items-center gap-1.5 text-sm font-medium text-primary">
                <ShieldCheck size={15} className="shrink-0 text-accent" aria-hidden="true" />
                {guarantee}
              </li>
            ))}
          </ul>
        </div>

        {/* Right: the decision tabs with a mini example per state */}
        <div>
          <div role="tablist" aria-orientation="horizontal" className="flex flex-wrap gap-2">
            {panels.map((panel, index) => {
              const isSelected = selected === index
              const t = TAB_TONES[index] ?? TAB_TONES[TAB_TONES.length - 1]
              return (
                <button
                  key={panel.title}
                  ref={(el) => {
                    tabRefs.current[index] = el
                  }}
                  type="button"
                  role="tab"
                  id={`safety-tab-${index}`}
                  aria-selected={isSelected}
                  aria-controls="safety-panel"
                  tabIndex={isSelected ? 0 : -1}
                  onClick={() => setSelected(index)}
                  onKeyDown={onKeyDown}
                  className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-medium transition-colors ${
                    isSelected ? t.active : 'border-border-col bg-surface text-secondary hover:border-accent/40 hover:text-primary'
                  }`}
                >
                  {index === panels.length - 1 ? (
                    <Siren size={13} className="shrink-0 text-red-500" aria-hidden="true" />
                  ) : (
                    <span className={`h-2 w-2 shrink-0 rounded-full ${t.dot}`} aria-hidden="true" />
                  )}
                  {panel.title}
                </button>
              )
            })}
          </div>

          <div
            role="tabpanel"
            id="safety-panel"
            aria-labelledby={`safety-tab-${selected}`}
            className="mt-4 rounded-2xl border border-border-col bg-surface p-5 lg:p-6"
          >
            <p className="text-sm leading-relaxed text-secondary">{panels[selected].description}</p>

            {example && (
              <div key={selected} className="mt-5 space-y-2.5">
                <div className="flex animate-fadeInUp justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent-soft px-4 py-2.5 text-sm leading-relaxed text-primary">
                    {example.user}
                  </div>
                </div>
                <div
                  className="flex animate-fadeInUp justify-start"
                  style={{ animationDelay: '120ms', animationFillMode: 'backwards' }}
                >
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-border-col bg-bg px-4 py-2.5 text-sm leading-relaxed text-primary">
                    {example.ai}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
