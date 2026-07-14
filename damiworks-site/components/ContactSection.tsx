'use client'

import { useState } from 'react'
import { Calendar, CheckCircle2, ChevronDown, MessageCircle } from 'lucide-react'
import type { DictContact } from '@/lib/i18n'
import { CALENDLY_URL } from '@/lib/calendly'
import { WHATSAPP_URL } from '@/lib/whatsapp'

export default function ContactSection({ dict }: { dict: DictContact }) {
  const [form, setForm] = useState({
    name: '',
    contact: '',
    businessType: '',
    message: '',
  })
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          contact: form.contact,
          businessType: form.businessType || undefined,
          message: form.message || undefined,
        }),
      })
      if (!response.ok) throw new Error('contact_delivery_failed')
      setSubmitted(true)
    } catch {
      setError(dict.errorMessage ?? 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const inputClass =
    'w-full bg-bg/60 border border-border-col rounded-xl px-4 py-3 text-sm text-primary placeholder:text-secondary focus:outline-none focus:border-accent focus:bg-surface transition-colors'

  return (
    <section id="contact" className="scroll-mt-20 py-20 lg:py-24 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-10 lg:gap-14 items-start">

          {/* Left */}
          <div className="lg:pt-5">
            <h2 className="text-3xl lg:text-5xl font-bold leading-tight text-primary mb-5 whitespace-pre-line">
              {dict.headline}
            </h2>
            <p className="text-base lg:text-lg leading-relaxed text-secondary max-w-xl">
              {dict.description}
            </p>

            <ul className="mt-6 space-y-3">
              {dict.highlights.map((item) => (
                <li key={item} className="flex gap-3 text-sm lg:text-base text-primary">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            <p className="text-sm text-secondary mt-5">{dict.note}</p>
            {/* Calendly is the primary conversion path, WhatsApp the lowest-friction one — each hidden when its URL is unset. */}
            {(CALENDLY_URL || WHATSAPP_URL) && (
              <div className="mt-8">
                <div className="flex flex-wrap gap-3">
                  {CALENDLY_URL && (
                    <a
                      href={CALENDLY_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-h-12 items-center justify-center gap-2 bg-accent text-white rounded-xl px-6 py-3 font-semibold text-sm hover:opacity-90 transition-opacity"
                    >
                      <Calendar className="h-4 w-4" aria-hidden="true" />
                      {dict.calendlyButton}
                    </a>
                  )}
                  {WHATSAPP_URL && (
                    <a
                      href={WHATSAPP_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-h-12 items-center justify-center gap-2 bg-surface text-primary rounded-xl px-6 py-3 font-semibold text-sm border border-border-col hover:bg-bg transition-colors"
                    >
                      <MessageCircle className="h-4 w-4 text-accent" aria-hidden="true" />
                      {dict.whatsappButton}
                    </a>
                  )}
                </div>
                {CALENDLY_URL && <p className="text-sm text-secondary mt-4">{dict.calendlySubtext}</p>}
              </div>
            )}
          </div>

          {/* Right */}
          {submitted ? (
            <div className="bg-surface border border-accent/20 rounded-2xl p-8 shadow-sm text-accent font-medium">
              {dict.successMessage}
            </div>
          ) : (
            <div className="bg-surface border border-border-col rounded-2xl p-5 sm:p-6 lg:p-8 shadow-sm">
              <div className="mb-6">
                <h3 className="text-xl font-bold text-primary">{dict.formTitle}</h3>
                <p className="mt-2 text-sm text-secondary">{dict.formSubtitle}</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <label>
                    <span className="sr-only">{dict.placeholderName}</span>
                    <input
                      required
                      name="name"
                      autoComplete="name"
                      placeholder={dict.placeholderName}
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className={inputClass}
                    />
                  </label>
                  <label>
                    <span className="sr-only">{dict.placeholderContact}</span>
                    <input
                      required
                      name="contact"
                      autoComplete="tel"
                      placeholder={dict.placeholderContact}
                      value={form.contact}
                      onChange={(e) => setForm({ ...form, contact: e.target.value })}
                      className={inputClass}
                    />
                  </label>
                </div>
                <div className="relative">
                  <label htmlFor="business-type" className="sr-only">{dict.placeholderBusinessType}</label>
                  <select
                    id="business-type"
                    name="businessType"
                    value={form.businessType}
                    onChange={(e) => setForm({ ...form, businessType: e.target.value })}
                    className={`${inputClass} appearance-none cursor-pointer pr-10`}
                  >
                    <option value="">{dict.placeholderBusinessType}</option>
                    {dict.businessTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary"
                    aria-hidden="true"
                  />
                </div>
                <textarea
                  name="message"
                  rows={5}
                  placeholder={dict.placeholderMessage}
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  className={`${inputClass} resize-none`}
                />
                <p className="text-xs leading-relaxed text-secondary">{dict.messageHelp}</p>
                {error && (
                  <p className="text-xs text-red-500">{error}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full min-h-12 bg-accent text-white rounded-xl py-3 font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {loading ? '...' : dict.submitButton}
                </button>
                <p className="text-xs leading-relaxed text-secondary">
                  {dict.consentText}{' '}
                  <a href={dict.privacyHref} className="underline decoration-border-col underline-offset-2 hover:text-primary">
                    {dict.privacyLabel}
                  </a>
                </p>
              </form>
            </div>
          )}

        </div>
      </div>
    </section>
  )
}
