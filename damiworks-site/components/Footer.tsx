import type { DictFooter, DictSite } from '@/lib/i18n'

export default function Footer({ dict, site }: { dict: DictFooter; site: DictSite }) {
  return (
    <footer className="bg-surface border-t border-border-col py-10">
      <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center md:items-start justify-between gap-6">
        <div>
          <div className="font-semibold text-primary">{site.name}</div>
          <p className="text-sm text-secondary mt-1">{dict.tagline}</p>
        </div>
        <div className="flex flex-wrap gap-2 justify-center md:justify-end">
          {dict.badges.map((badge) => (
            <span
              key={badge}
              className="bg-bg border border-border-col text-secondary text-xs px-3 py-1.5 rounded-full"
            >
              {badge}
            </span>
          ))}
        </div>
      </div>
    </footer>
  )
}
