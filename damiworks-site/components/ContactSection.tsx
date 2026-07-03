'use client'

import { useState } from 'react'
import type { DictContact } from '@/lib/i18n'
import { CALENDLY_URL } from '@/lib/calendly'

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
      await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          contact: form.contact,
          businessType: form.businessType || undefined,
          message: form.message || undefined,
        }),
      })
      setSubmitted(true)
    } catch {
      setError(dict.errorMessage ?? 'Что-то пошло не так. Попробуйте ещё раз.')
    } finally {
      setLoading(false)
    }
  }

  const inputClass =
    'w-full bg-surface border border-border-col rounded-xl px-4 py-3 text-sm text-primary placeholder:text-secondary focus:outline-none focus:border-accent transition-colors'

  return (
    <section id="contact" className="scroll-mt-20 py-24 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">

          {/* Left */}
          <div>
            <h2 className="text-3xl lg:text-4xl font-bold text-primary mb-4 whitespace-pre-line">
              {dict.headline}
            </h2>
            <p className="text-secondary mb-2">{dict.description}</p>
            <p className="text-sm text-secondary">{dict.note}</p>
            {/* Calendly is the primary conversion path — hidden when the URL is unset. */}
            {CALENDLY_URL && (
              <div className="mt-6">
                <a
                  href={CALENDLY_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center bg-accent text-white rounded-xl px-6 py-3 font-medium text-sm hover:opacity-90 transition-opacity"
                >
                  {dict.calendlyButton}
                </a>
                <p className="text-sm text-secondary mt-3">{dict.calendlySubtext}</p>
              </div>
            )}
          </div>

          {/* Right */}
          {submitted ? (
            <div className="bg-accent-soft border border-accent/20 rounded-2xl p-8 text-accent font-medium">
              {dict.successMessage}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <input
                  required
                  placeholder={dict.placeholderName}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className={inputClass}
                />
                <input
                  required
                  placeholder={dict.placeholderContact}
                  value={form.contact}
                  onChange={(e) => setForm({ ...form, contact: e.target.value })}
                  className={inputClass}
                />
              </div>
              <select
                required
                value={form.businessType}
                onChange={(e) => setForm({ ...form, businessType: e.target.value })}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                <option value="">{dict.placeholderBusinessType}</option>
                {dict.businessTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <textarea
                rows={4}
                placeholder={dict.placeholderMessage}
                value={form.message}
                onChange={(e) => setForm({ ...form, message: e.target.value })}
                className={`${inputClass} resize-none`}
              />
              {error && (
                <p className="text-xs text-red-500">{error}</p>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-accent text-white rounded-xl py-3 font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? '...' : dict.submitButton}
              </button>
            </form>
          )}

        </div>
      </div>
    </section>
  )
}
