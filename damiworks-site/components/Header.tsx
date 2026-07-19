'use client'

import { useEffect, useRef, useState } from 'react'
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
  // Scroll-story mode: a reading-progress bar along the header's bottom edge
  // and scrollspy highlighting of the nav link whose section is in view.
  withProgress?: boolean
}

export default function Header({ locale, nav, site, bookACallLabel, langSwitcher, demoLink, withProgress = false }: Props) {
  const [open, setOpen] = useState(false)
  const [activeHash, setActiveHash] = useState('')
  const progressRef = useRef<HTMLDivElement | null>(null)
  const hasNav = nav.length > 0

  // Reading progress: mutate the bar's transform directly (no re-renders).
  useEffect(() => {
    if (!withProgress) return
    let raf = 0
    const update = () => {
      raf = 0
      const doc = document.documentElement
      const max = doc.scrollHeight - window.innerHeight
      const p = max > 0 ? Math.min(1, window.scrollY / max) : 0
      if (progressRef.current) progressRef.current.style.transform = `scaleX(${p})`
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [withProgress])

  // Scrollspy: a nav section is active while it crosses the middle of the viewport.
  useEffect(() => {
    if (!withProgress || nav.length === 0) return
    const targets = nav
      .map((link) => link.href)
      .filter((href) => href.startsWith('#'))
      .map((href) => document.getElementById(href.slice(1)))
      .filter((el): el is HTMLElement => el !== null)
    if (targets.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveHash(`#${entry.target.id}`)
        }
      },
      { rootMargin: '-40% 0px -55% 0px' }
    )
    targets.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [withProgress, nav])

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
                aria-current={withProgress && activeHash === link.href ? 'true' : undefined}
                className={`text-sm transition-colors ${
                  withProgress && activeHash === link.href
                    ? 'text-accent font-medium'
                    : 'text-secondary hover:text-primary'
                }`}
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

      {withProgress && (
        <div
          ref={progressRef}
          aria-hidden="true"
          className="absolute bottom-0 left-0 h-0.5 w-full origin-left scale-x-0 bg-accent"
        />
      )}

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
