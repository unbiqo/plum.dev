import { ArrowRight } from 'lucide-react'
import type { DictBackstage } from '@/lib/i18n'

// One compact row right under the hero test: names what the visitor just saw
// happen. A connector, not a full section — no cards, no grid.
export default function BackstageStrip({ dict }: { dict: DictBackstage }) {
  return (
    <section className="border-t border-border-col bg-surface py-8">
      <div className="mx-auto max-w-6xl px-6">
        <h2 className="text-center text-xs font-semibold uppercase tracking-[0.16em] text-secondary">
          {dict.title}
        </h2>
        <ol className="mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
          {dict.steps.map((step, i) => (
            <li key={step} className="flex items-center gap-3 text-sm font-medium text-primary">
              {i > 0 && <ArrowRight size={14} className="shrink-0 text-accent" aria-hidden="true" />}
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
