import { ArrowRight } from 'lucide-react'
import type { DictAdminHandoff, DictHeroChat, DictHeroDemo } from '@/lib/i18n'
import HeroNetworkBackground from '@/components/HeroNetworkBackground'
import HeroDialogSim, { HeroDialogCta } from '@/components/HeroDialogSim'

// Two-column hero: the existing claim + CTA on the left, a self-playing
// AI↔patient dialog on the right (scripted, no backend). The dialog ends with
// the same «Новая заявка» card that the AdminHandoff section explains below.
// The live demo itself stays at /ru/demo — both CTAs lead there.
type Props = {
  dict: DictHeroDemo
  chat: Pick<DictHeroChat, 'headerTitle' | 'onlineLabel'>
  card: DictAdminHandoff['card']
  tryDemoLabel: string
}

export default function HeroDemo({ dict, chat, card, tryDemoLabel }: Props) {
  return (
    <section className="relative isolate overflow-hidden bg-bg">
      <HeroNetworkBackground />

      <div className="relative z-10 mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 py-16 sm:py-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14 lg:py-24">
        {/* Left: claim + CTA */}
        <div>
          <h1 className="text-3xl font-bold leading-tight text-primary sm:text-4xl lg:text-5xl" style={{ textWrap: 'balance' }}>
            <span className="block">{dict.headlineLine1}</span>
            <span className="block text-accent">{dict.headlineLine2}</span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-secondary lg:text-lg">
            {dict.subheadline}
          </p>

          <div className="mt-9">
            <a
              href="/ru/demo"
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-accent px-7 py-3 text-base font-semibold text-white transition-opacity hover:opacity-90"
            >
              {dict.ctaLabel}
              <ArrowRight size={17} aria-hidden="true" />
            </a>
          </div>
        </div>

        {/* Right: the self-playing dialog + a bridge into the live demo */}
        <div>
          <HeroDialogSim chat={chat} card={card} />
          <HeroDialogCta label={tryDemoLabel} />
        </div>
      </div>
    </section>
  )
}
