'use client'

import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import type { DictNavLink, DictSite, DictLangSwitcher, Locale } from '@/lib/i18n'

function LangSwitcher({ locale, labels }: { locale: Locale; labels: DictLangSwitcher }) {
  const handleSwitch = (v: Locale) => {
    // Set cookie before navigation so middleware respects user choice immediately
    document.cookie = `damiworks_locale=${v};path=/;max-age=31536000;SameSite=Lax`
  }
  return (
    <div className="flex items-center gap-1 text-xs font-medium">
      <a
        href="/"
        onClick={() => handleSwitch('en')}
        className={locale === 'en' ? 'text-accent' : 'text-secondary hover:text-primary transition-colors'}
      >
        {labels.enLabel}
      </a>
      <span className="text-border-col">/</span>
      <a
        href="/ru"
        onClick={() => handleSwitch('ru')}
        className={locale === 'ru' ? 'text-accent' : 'text-secondary hover:text-primary transition-colors'}
      >
        {labels.ruLabel}
      </a>
    </div>
  )
}

type Props = {
  locale: Locale
  nav: DictNavLink[]
  site: DictSite
  bookACallLabel: string
  langSwitcher: DictLangSwitcher
  // Minimal (demo-first) header: pass nav={[]} plus a demoLink — no menu and
  // no hamburger on any breakpoint, just brand + demo link + lang + CTA.
  demoLink?: DictNavLink
}

export default function Header({ locale, nav, site, bookACallLabel, langSwitcher, demoLink }: Props) {
  const [open, setOpen] = useState(false)
  const hasNav = nav.length > 0

  return (
    <header className="sticky top-0 z-50 bg-surface border-b border-border-col">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href={locale === 'ru' ? '/ru' : '/'} className="font-semibold text-lg text-primary">
          {site.name}
        </a>

        {hasNav && (
          <nav className="hidden md:flex items-center gap-8">
            {nav.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-sm text-secondary hover:text-primary transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>
        )}

        <div className={`${hasNav ? 'hidden md:flex' : 'flex'} items-center gap-3 md:gap-4`}>
          {demoLink && (
            <a
              href={demoLink.href}
              className="hidden sm:inline text-sm font-medium text-secondary hover:text-primary transition-colors"
            >
              {demoLink.label}
            </a>
          )}
          <LangSwitcher locale={locale} labels={langSwitcher} />
          <a
            href="#contact"
            className="inline-flex items-center bg-accent text-white text-sm font-medium px-4 py-2 rounded-xl hover:opacity-90 transition-opacity"
          >
            {bookACallLabel}
          </a>
        </div>

        {hasNav && (
          <button
            className="md:hidden text-secondary p-1"
            onClick={() => setOpen(!open)}
            aria-label={locale === 'ru' ? 'Открыть меню' : 'Toggle menu'}
            aria-expanded={open}
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        )}
      </div>

      {hasNav && open && (
        <div className="md:hidden bg-surface border-t border-border-col px-6 py-4 flex flex-col gap-4">
          {nav.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-secondary hover:text-primary transition-colors"
              onClick={() => setOpen(false)}
            >
              {link.label}
            </a>
          ))}
          <div className="flex items-center gap-3">
            <LangSwitcher locale={locale} labels={langSwitcher} />
          </div>
          <a
            href="#contact"
            className="inline-flex items-center justify-center bg-accent text-white text-sm font-medium px-4 py-2.5 rounded-xl hover:opacity-90 transition-opacity"
            onClick={() => setOpen(false)}
          >
            {bookACallLabel}
          </a>
        </div>
      )}
    </header>
  )
}
