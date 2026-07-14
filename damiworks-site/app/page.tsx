import type { Metadata } from 'next'
import { getDict } from '@/lib/i18n'
import HomePage from '@/components/HomePage'

export const metadata: Metadata = {
  title: 'DamiWorks | AI Employees for Sales and Support',
  description:
    'AI employees for WhatsApp, Instagram and websites. Reply to customers, qualify leads and hand off warm requests to your team.',
}

export default function Page() {
  const dict = getDict('en')
  return <HomePage locale="en" dict={dict} />
}
