'use client'

import { useRef, useState } from 'react'
import { ArrowDown, ArrowRight, BookOpen, MessagesSquare, Send, ShieldCheck } from 'lucide-react'
import type { DictLaunchKit } from '@/lib/i18n'

// «Что входит в запуск» as an interactive systems walkthrough: three clickable
// nodes (Каналы → AI-администратор → Готовая заявка) and a detail panel for the
// selected node. The first node is selected by default so the section never
// looks empty. Same content as before — channels, the three core layers, the
// handoff destinations — only the packaging changed.
export default function LaunchKitSection({ dict }: { dict: DictLaunchKit }) {
  const [selected, setSelected] = useState(0)
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])

  const nodes = [
    { title: dict.channels.title, summary: dict.channels.items.join(' · ') },
    { title: dict.core.title, summary: dict.core.layers.map((l) => l.title).join(' · ') },
    { title: dict.handoff.title, summary: dict.handoff.items.join(' · ') },
  ]

  // Roving-tabindex arrow navigation between the nodes.
  const onKeyDown = (event: React.KeyboardEvent) => {
    const dir =
      event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1
      : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1
      : 0
    if (dir === 0) return
    event.preventDefault()
    const next = (selected + dir + nodes.length) % nodes.length
    setSelected(next)
    tabRefs.current[next]?.focus()
  }

  const CORE_LAYER_ICONS = [BookOpen, MessagesSquare, ShieldCheck]

  return (
    <section className="border-t border-border-col bg-surface py-20 lg:py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 text-lg leading-relaxed text-secondary">{dict.subheadline}</p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:gap-10">
          {/* The system: three clickable nodes with flow connectors */}
          <div role="tablist" aria-orientation="vertical" className="flex flex-col">
            {nodes.map((node, index) => {
              const isSelected = selected === index
              return (
                <div key={node.title} className="flex flex-col">
                  {index > 0 && (
                    <div className="flex justify-center py-1 text-accent/70" aria-hidden="true">
                      <ArrowDown size={18} />
                    </div>
                  )}
                  <button
                    ref={(el) => {
                      tabRefs.current[index] = el
                    }}
                    type="button"
                    role="tab"
                    id={`launch-kit-tab-${index}`}
                    aria-selected={isSelected}
                    aria-controls="launch-kit-panel"
                    tabIndex={isSelected ? 0 : -1}
                    onClick={() => setSelected(index)}
                    onKeyDown={onKeyDown}
                    className={`group flex items-center justify-between gap-4 rounded-2xl border p-5 text-left transition-all ${
                      isSelected
                        ? 'border-accent/40 bg-accent-soft/50 shadow-lg shadow-accent/10'
                        : 'border-border-col bg-bg hover:border-accent/40 hover:bg-accent-soft/25'
                    } ${index === 1 ? 'border-2' : ''}`}
                  >
                    <span>
                      <span className={`block font-bold ${index === 1 ? 'text-lg' : 'text-base'} text-primary`}>
                        {node.title}
                      </span>
                      <span className="mt-1 block text-sm text-secondary">{node.summary}</span>
                    </span>
                    <ArrowRight
                      size={18}
                      aria-hidden="true"
                      className={`shrink-0 transition-all ${
                        isSelected ? 'translate-x-0 text-accent opacity-100' : '-translate-x-1 text-secondary opacity-40 group-hover:opacity-70'
                      }`}
                    />
                  </button>
                </div>
              )
            })}
          </div>

          {/* Detail panel for the selected node */}
          <div
            role="tabpanel"
            id="launch-kit-panel"
            aria-labelledby={`launch-kit-tab-${selected}`}
            className="rounded-2xl border-2 border-accent/30 bg-gradient-to-b from-accent-soft/60 via-accent-soft/25 to-surface p-6 lg:p-7"
          >
            <h3 className="text-lg font-bold text-primary">{nodes[selected].title}</h3>

            {selected === 1 ? (
              <div key="core" className="mt-4 space-y-3">
                {dict.core.layers.map((layer, i) => {
                  const Icon = CORE_LAYER_ICONS[i] ?? BookOpen
                  return (
                    <div
                      key={layer.title}
                      className="animate-fadeInUp rounded-xl border border-accent/20 bg-surface/90 p-4"
                      style={{ animationDelay: `${i * 70}ms`, animationFillMode: 'backwards' }}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                          <Icon size={16} aria-hidden="true" />
                        </span>
                        <p className="text-sm font-semibold text-primary">{layer.title}</p>
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-secondary">{layer.text}</p>
                    </div>
                  )
                })}
              </div>
            ) : (
              <ul key={selected === 0 ? 'channels' : 'handoff'} className="mt-4 flex flex-wrap gap-2">
                {(selected === 0 ? dict.channels.items : dict.handoff.items).map((item, i) => (
                  <li
                    key={item}
                    className="animate-fadeInUp rounded-full border border-accent/25 bg-surface px-4 py-2 text-sm font-medium text-primary"
                    style={{ animationDelay: `${i * 60}ms`, animationFillMode: 'backwards' }}
                  >
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
