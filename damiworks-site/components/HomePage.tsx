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
import { EvidenceSection, FaqSection, FounderSection } from '@/components/TrustFirstSections'
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

  if (locale === 'ru') {
    return (
      <main lang="ru">
        <Header
          locale={locale}
          nav={dict.nav}
          site={dict.site}
          bookACallLabel={dict.bookACallLabel}
          langSwitcher={dict.langSwitcher}
        />
        <Hero dict={dict.hero} />
        <DemoSection
          dict={dict.demo}
          locale={locale}
          liveChat={dict.liveChat}
          customDemoChat={dict.customDemoChat}
          intake={dict.intake}
        />
        <EvidenceSection dict={dict.evidence} />
        <HowItWorks dict={dict.howItWorks} />
        <AutomateSection dict={dict.automate} />
        <PricingSection dict={pricing} />
        <ValuePropSection dict={dict.valueProp} />
        <WhatWeNeedSection dict={dict.whatWeNeed} />
        <TrustSection dict={dict.trust} />
        <FounderSection dict={dict.founder} />
        <FaqSection dict={dict.faq} />
        <ContactSection dict={dict.contact} />
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
