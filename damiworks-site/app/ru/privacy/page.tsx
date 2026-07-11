import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Уведомление о конфиденциальности — DamiWorks',
  description: 'Как DamiWorks использует контактные данные, отправленные через сайт.',
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
            <h2 className="text-lg font-semibold text-primary">Какие данные мы получаем</h2>
            <p className="mt-2">Через форму на сайте DamiWorks получает имя, контакт в WhatsApp или Telegram, выбранный тип бизнеса и комментарий, если вы его оставили.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Зачем используются данные</h2>
            <p className="mt-2">Только чтобы ответить на вашу заявку, обсудить возможный пилот и сохранить контекст договорённостей. Мы не продаём контактные данные третьим лицам.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Данные в демочате</h2>
            <p className="mt-2">Демочат предназначен для проверки сценария. Не отправляйте в него реальные медицинские документы, диагнозы, идентификационные данные пациентов и другую чувствительную информацию.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Передача и хранение</h2>
            <p className="mt-2">Контактная заявка передаётся в рабочую систему DamiWorks, необходимую для ответа. Конкретные правила обработки данных для будущего пилота согласуются с клиникой отдельно до подключения реальных обращений.</p>
          </section>
          <section>
            <h2 className="text-lg font-semibold text-primary">Ваши запросы</h2>
            <p className="mt-2">Вы можете попросить уточнить, исправить или удалить отправленные контактные данные, написав DamiWorks через тот же канал связи, который использовался после заявки.</p>
          </section>
        </div>
      </article>
    </main>
  )
}
