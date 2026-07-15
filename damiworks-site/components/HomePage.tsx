import type { Dict, Locale } from '@/lib/i18n'
import Header from '@/components/Header'
import Hero from '@/components/Hero'
import HowItWorks from '@/components/HowItWorks'
import DemoSection from '@/components/DemoSection'
import TieredCapabilitiesSection from '@/components/TieredCapabilitiesSection'
import ValuePropSection from '@/components/ValuePropSection'
import PricingSection from '@/components/PricingSection'
import ContactSection from '@/components/ContactSection'
import Footer from '@/components/Footer'
import ScrollReveal from '@/components/ScrollReveal'
import HeroTest from '@/components/HeroTest'
import BackstageStrip from '@/components/BackstageStrip'
import AdminHandoffSection from '@/components/AdminHandoffSection'
import LaunchKitSection from '@/components/LaunchKitSection'
import SafetyFlowSection from '@/components/SafetyFlowSection'
import LaunchSection from '@/components/LaunchSection'
import { FaqSection, FounderSection } from '@/components/TrustFirstSections'
import {
  AutomateSection,
  PainSection,
  TrustSection,
  VsChatbotSection,
  WhatWeNeedSection,
} from '@/components/StorySections'
import { SHOW_PUBLIC_PRICING } from '@/lib/constants'

type Props = { locale: Locale; dict: Dict }

// Narrative order: pain -> customer journey -> live demo -> objection
// (vs chatbot) -> what to automate -> how we implement -> launch formats ->
// pilot example -> what we need -> trust -> final CTA.
export default function HomePage({ locale, dict }: Props) {
  const pricing = SHOW_PUBLIC_PRICING ? dict.pricing : { ...dict.pricing, plans: [] }

  // RU narrative (test-first): the live demo IS the hero — the visitor writes
  // as a patient and watches the заявка assemble. Then: what just happened ->
  // what the administrator receives (dark) -> what a launch includes ->
  // safety decision-flow -> turnkey launch with price -> trust block
  // (founder, FAQ) -> final CTA.
  if (locale === 'ru') {
    return (
      <main lang="ru">
        <Header
          locale={locale}
          nav={[]}
          demoLink={{ label: dict.headerDemoLabel, href: '#demo' }}
          site={dict.site}
          bookACallLabel={dict.bookACallLabel}
          langSwitcher={dict.langSwitcher}
        />
        <HeroTest
          dict={dict.heroTest}
          medicalChat={dict.demo.medicalChat}
          medicalSummary={dict.demo.medicalSummary}
        />
        <BackstageStrip dict={dict.backstage} />
        <ScrollReveal>
          <AdminHandoffSection dict={dict.adminHandoff} />
        </ScrollReveal>
        <ScrollReveal>
          <LaunchKitSection dict={dict.launchKit} />
        </ScrollReveal>
        <ScrollReveal>
          <SafetyFlowSection dict={dict.safetyFlow} />
        </ScrollReveal>
        <ScrollReveal>
          <LaunchSection dict={dict.launch} />
        </ScrollReveal>
        <ScrollReveal>
          <FounderSection dict={dict.founder} />
        </ScrollReveal>
        <ScrollReveal>
          <FaqSection dict={dict.faq} />
        </ScrollReveal>
        <ScrollReveal>
          <ContactSection dict={dict.contact} />
        </ScrollReveal>
        <Footer dict={dict.footer} site={dict.site} />
      </main>
    )
  }

  return (
    <main lang="en">
      <Header
        locale={locale}
        nav={dict.nav}
        site={dict.site}
        bookACallLabel={dict.bookACallLabel}
        langSwitcher={dict.langSwitcher}
      />
      <Hero dict={dict.hero} />
      <ScrollReveal>
        <PainSection dict={dict.pain} />
      </ScrollReveal>
      <ScrollReveal>
        <HowItWorks dict={dict.howItWorks} />
      </ScrollReveal>
      <ScrollReveal>
        <DemoSection
          dict={dict.demo}
          locale={locale}
          liveChat={dict.liveChat}
          customDemoChat={dict.customDemoChat}
          intake={dict.intake}
        />
      </ScrollReveal>
      <ScrollReveal>
        <VsChatbotSection dict={dict.vsChatbot} />
      </ScrollReveal>
      <ScrollReveal>
        <AutomateSection dict={dict.automate} />
      </ScrollReveal>
      <ScrollReveal>
        <ValuePropSection dict={dict.valueProp} />
      </ScrollReveal>
      <ScrollReveal>
        <TieredCapabilitiesSection dict={dict.capabilities} />
      </ScrollReveal>
      <ScrollReveal>
        <PricingSection dict={pricing} />
      </ScrollReveal>
      <ScrollReveal>
        <WhatWeNeedSection dict={dict.whatWeNeed} />
      </ScrollReveal>
      <ScrollReveal>
        <TrustSection dict={dict.trust} />
      </ScrollReveal>
      <ScrollReveal>
        <ContactSection dict={dict.contact} />
      </ScrollReveal>
      <Footer dict={dict.footer} site={dict.site} />
    </main>
  )
}
