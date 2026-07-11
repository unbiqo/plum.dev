import type { Metadata } from 'next'
import { getDict } from '@/lib/i18n'
import HomePage from '@/components/HomePage'

export const metadata: Metadata = {
  title: 'AI-администратор для клиник и стоматологий — DamiWorks',
  description:
    'AI-администратор отвечает пациентам 24/7, помогает выбрать специалиста и передаёт клинике готовые заявки на запись.',
}

export default function RuPage() {
  const dict = getDict('ru')
  return <HomePage locale="ru" dict={dict} />
}
