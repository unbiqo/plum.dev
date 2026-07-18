import type { Metadata } from 'next'
import { Suspense } from 'react'
import { getDict } from '@/lib/i18n'
import DemoWorkspace from '@/components/DemoWorkspace'

export const metadata: Metadata = {
  title: 'Демо AI-администратора | DamiWorks',
  description:
    'Проверьте, как AI-администратор отвечает пациенту, собирает заявку и превращает ваши ответы в черновик плана запуска.',
  // Personalized demo workspace (carries ?site=<domain>) — keep out of search.
  robots: { index: false },
}

export default function RuDemoPage() {
  const dict = getDict('ru')
  return (
    // Suspense boundary is required: DemoWorkspace reads useSearchParams().
    <Suspense fallback={null}>
      <DemoWorkspace
        dict={dict.demoWorkspace}
        medicalChat={dict.demo.medicalChat}
        medicalSummary={dict.demo.medicalSummary}
        site={dict.site}
      />
    </Suspense>
  )
}
