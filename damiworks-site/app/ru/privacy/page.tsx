import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Уведомление о конфиденциальности | DamiWorks',
  description: 'Как я использую контактные данные, отправленные через сайт.',
}

export default function PrivacyPage() {
  return (
    <main lang="ru" className="min-h-screen bg-bg py-16">
      <article className="mx-auto max-w-3xl px-6">
        <a href="/ru" className="text-sm font-medium text-accent">← Вернуться на сайт</a>
        <h1 className="mt-8 text-3xl font-bold text-primary lg:text-4xl">Уведомление о конфиденциальности</h1>
        <p className="mt-4 text-sm text-secondary">Последнее обновление: 11 июля 2026 года</p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-secondary">
          <section>
            <h2 className="text-lg font-semibold text-primary">Какие данные я получаю</h2>
            <p className="mt-2">Форма передаёт мне ваше имя, контакт в WhatsApp или Telegram, тип бизнеса и необязательный комментарий.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Зачем используются данные</h2>
            <p className="mt-2">Использую данные только для ответа на заявку и обсуждения пилота. Не продаю контакты третьим лицам.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Данные в демочате</h2>
            <p className="mt-2">Демочат предназначен для проверки сценария. Не отправляйте в него реальные медицинские документы, диагнозы, идентификационные данные пациентов и другую чувствительную информацию.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Передача и хранение</h2>
            <p className="mt-2">Заявка попадает в мою рабочую систему. Правила обработки данных для пилота согласуем отдельно до подключения реальных обращений.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Ваши запросы</h2>
            <p className="mt-2">Вы можете попросить уточнить, исправить или удалить контактные данные. Напишите мне через тот же канал, который использовался после заявки.</p>
          </section>
        </div>
      </article>
    </main>
  )
}
