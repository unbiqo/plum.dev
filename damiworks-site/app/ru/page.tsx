import type { Metadata } from 'next'
import { getDict } from '@/lib/i18n'
import HomePage from '@/components/HomePage'

export const metadata: Metadata = {
  title: 'DamiWorks — AI-сотрудники для продаж и поддержки',
  description:
    'AI-сотрудники для WhatsApp, Instagram и сайта: отвечают клиентам, квалифицируют заявки и передают тёплые лиды менеджеру.',
}

export default function RuPage() {
  const dict = getDict('ru')
  return <HomePage locale="ru" dict={dict} />
}
