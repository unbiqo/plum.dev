import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy notice | DamiWorks',
  description: 'How DamiWorks uses contact details submitted through the website.',
}

export default function PrivacyPage() {
  return (
    <main lang="en" className="min-h-screen bg-bg py-16">
      <article className="mx-auto max-w-3xl px-6">
        <a href="/" className="text-sm font-medium text-accent">← Back to the website</a>
        <h1 className="mt-8 text-3xl font-bold text-primary lg:text-4xl">Privacy notice</h1>
        <p className="mt-4 text-sm text-secondary">Last updated: July 11, 2026</p>
        <div className="mt-10 space-y-8 text-sm leading-relaxed text-secondary">
          <section><h2 className="text-lg font-semibold text-primary">Data we receive</h2><p className="mt-2">The contact form collects your name, WhatsApp or Telegram contact, business type, and an optional message.</p></section>
          <section><h2 className="text-lg font-semibold text-primary">How it is used</h2><p className="mt-2">We use this information to answer your request and discuss a potential pilot. DamiWorks does not sell submitted contact details.</p></section>
          <section><h2 className="text-lg font-semibold text-primary">Demo chat</h2><p className="mt-2">The demo is intended for scenario testing. Do not submit real patient records, diagnoses, identification data, or other sensitive information.</p></section>
          <section><h2 className="text-lg font-semibold text-primary">Pilot data</h2><p className="mt-2">Data handling rules for a production pilot are agreed with the client before real customer conversations are connected.</p></section>
        </div>
      </article>
    </main>
  )
}
