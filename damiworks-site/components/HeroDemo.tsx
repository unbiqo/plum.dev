import { ArrowRight } from 'lucide-react'
import type { DictHeroDemo } from '@/lib/i18n'
import HeroNetworkBackground from '@/components/HeroNetworkBackground'

// Light, CTA-first hero: one claim, one button straight into the demo
// workspace (/ru/demo). No URL input — the site can't scrape a clinic's
// pages yet, so asking for one only promised a personalization we don't
// deliver. Keeps the page in the same light rhythm as the rest of the site.
export default function HeroDemo({ dict }: { dict: DictHeroDemo }) {
  return (
    <section className="relative isolate overflow-hidden bg-bg">
      <HeroNetworkBackground />

      <div className="relative z-10 mx-auto max-w-3xl px-6 py-20 text-center sm:py-24 lg:py-32">
        <h1 className="text-3xl font-bold leading-tight text-primary sm:text-4xl lg:text-5xl" style={{ textWrap: 'balance' }}>
          <span className="block">{dict.headlineLine1}</span>
          <span className="block text-accent">{dict.headlineLine2}</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-secondary lg:text-lg">
          {dict.subheadline}
        </p>

        <div className="mt-9 flex justify-center">
          <a
            href="/ru/demo"
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-accent px-7 py-3 text-base font-semibold text-white transition-opacity hover:opacity-90"
          >
            {dict.ctaLabel}
            <ArrowRight size={17} aria-hidden="true" />
          </a>
        </div>
      </div>
    </section>
  )
}
