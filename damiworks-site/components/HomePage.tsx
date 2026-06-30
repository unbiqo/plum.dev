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
import { SHOW_PUBLIC_PRICING } from '@/lib/constants'

type Props = { locale: Locale; dict: Dict }

export default function HomePage({ locale, dict }: Props) {
  const pricing = SHOW_PUBLIC_PRICING ? dict.pricing : { ...dict.pricing, plans: [] }

  return (
    <main>
      <Header
        locale={locale}
        nav={dict.nav}
        site={dict.site}
        bookACallLabel={dict.bookACallLabel}
        langSwitcher={dict.langSwitcher}
      />
      <Hero dict={dict.hero} />
      <HowItWorks dict={dict.howItWorks} />
      <DemoSection
        dict={dict.demo}
        locale={locale}
        liveChat={dict.liveChat}
        customDemoChat={dict.customDemoChat}
        intake={dict.intake}
      />
      <TieredCapabilitiesSection dict={dict.capabilities} />
      <ValuePropSection dict={dict.valueProp} />
      <PricingSection dict={pricing} />
      <ContactSection dict={dict.contact} />
      <Footer dict={dict.footer} site={dict.site} />
    </main>
  )
}
