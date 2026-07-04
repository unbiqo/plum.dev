import {
  Link2,
  BookOpen,
  Users,
  MessageCircle,
  Zap,
  ListChecks,
  Phone,
  ClipboardList,
} from 'lucide-react'
import type { DictHowItWorks } from '@/lib/i18n'

const ICON_MAP = { Link2, BookOpen, Users, MessageCircle, Zap, ListChecks, Phone, ClipboardList } as const

export default function HowItWorks({ dict }: { dict: DictHowItWorks }) {
  return (
    <section
      id="how-it-works"
      className="scroll-mt-20 py-24 bg-surface border-t border-border-col"
    >
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-3">
            {dict.headline}
          </h2>
          <p className="text-secondary text-lg">{dict.subheadline}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
          {dict.steps.map((step) => {
            const Icon = ICON_MAP[step.icon]
            return (
              <div key={step.number} className="bg-bg border border-border-col rounded-2xl p-6">
                <div className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center mb-5">
                  <Icon size={18} className="text-accent" />
                </div>
                <div className="text-2xl font-bold text-accent mb-2">{step.number}</div>
                <h3 className="text-base font-semibold text-primary mb-2">{step.title}</h3>
                <p className="text-secondary text-sm leading-relaxed">{step.description}</p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
