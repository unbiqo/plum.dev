import fs from 'node:fs'
import path from 'node:path'
import Image from 'next/image'
import { ArrowRight, CheckCircle2, Eye, ShieldCheck, UserRound, Workflow } from 'lucide-react'
import type { DictEvidence, DictFaq, DictFounder } from '@/lib/i18n'

const EVIDENCE_ICONS = [Eye, ShieldCheck, Workflow, CheckCircle2]

// A real photo builds more trust than a letter avatar. Drop founder.jpg/png/webp
// into public/ and it replaces the fallback (dev server restart required).
const FOUNDER_PHOTO = ['founder.jpg', 'founder.png', 'founder.webp'].find((name) =>
  fs.existsSync(path.join(process.cwd(), 'public', name)),
)

export function EvidenceSection({ dict }: { dict: DictEvidence }) {
  return (
    <section className="border-t border-border-col bg-surface py-20">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-3xl">
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-accent">
            {dict.eyebrow}
          </p>
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">
            {dict.headline}
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-secondary">{dict.subheadline}</p>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {dict.cards.map((card, index) => {
            const Icon = EVIDENCE_ICONS[index] ?? CheckCircle2
            return (
              <article key={card.title} className="rounded-2xl border border-border-col bg-bg p-5">
                <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent">
                  <Icon size={18} aria-hidden="true" />
                </div>
                <h3 className="font-semibold text-primary">{card.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary">{card.text}</p>
              </article>
            )
          })}
        </div>

        <div className="mt-8 rounded-2xl border border-accent/25 bg-accent-soft/50 px-5 py-4 text-sm font-medium leading-relaxed text-primary">
          {dict.bottomLine}
        </div>
      </div>
    </section>
  )
}

export function FounderSection({ dict }: { dict: DictFounder }) {
  return (
    <section className="border-t border-border-col bg-bg py-20">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 lg:grid-cols-[0.75fr_1.25fr] lg:items-center">
        <div className="rounded-2xl border border-border-col bg-surface p-7">
          <div className="flex items-center gap-4">
            {FOUNDER_PHOTO ? (
              <Image
                src={`/${FOUNDER_PHOTO}`}
                alt={dict.name}
                width={56}
                height={56}
                className="h-14 w-14 shrink-0 rounded-2xl object-cover"
              />
            ) : (
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-xl font-bold text-accent">
                Д
              </div>
            )}
            <div>
              <p className="font-bold text-primary">{dict.name}</p>
              <p className="mt-1 text-sm text-secondary">{dict.role}</p>
            </div>
          </div>
          <p className="mt-6 text-sm leading-relaxed text-secondary">{dict.personalNote}</p>
        </div>

        <div>
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-accent">
            {dict.eyebrow}
          </p>
          <h2 className="text-3xl font-bold leading-tight text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-4 max-w-2xl leading-relaxed text-secondary">{dict.description}</p>
          <ul className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {dict.points.map((point) => (
              <li key={point} className="flex gap-2.5 text-sm leading-relaxed text-primary">
                <UserRound className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
          <a href="#contact" className="mt-7 inline-flex items-center gap-2 font-semibold text-accent">
            {dict.cta}
            <ArrowRight size={16} aria-hidden="true" />
          </a>
        </div>
      </div>
    </section>
  )
}

export function FaqSection({ dict }: { dict: DictFaq }) {
  return (
    <section id="faq" className="scroll-mt-20 border-t border-border-col bg-surface py-20">
      <div className="mx-auto max-w-3xl px-6">
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-bold text-primary lg:text-4xl">{dict.headline}</h2>
          <p className="mt-3 text-secondary">{dict.subheadline}</p>
        </div>
        <div className="space-y-3">
          {dict.items.map((item, index) => (
            <details
              key={item.question}
              className="group rounded-2xl border border-border-col bg-bg px-5 py-4 open:border-accent/30"
              open={index === 0}
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-primary marker:hidden">
                {item.question}
                <span className="text-xl font-normal text-accent transition-transform group-open:rotate-45" aria-hidden="true">
                  +
                </span>
              </summary>
              <p className="pr-8 pt-3 text-sm leading-relaxed text-secondary">{item.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
