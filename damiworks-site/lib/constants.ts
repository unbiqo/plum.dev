export const SITE = {
  name: 'DamiWorks',
  tagline: 'AI employees for sales and support.',
}

export const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Demo', href: '#demo' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Contact', href: '#contact' },
]

export const HERO = {
  eyebrow: '',
  headlinePart1: 'An AI employee that turns inquiries ',
  headlineAccent: 'into customers',
  subheadline:
    'DamiWorks builds AI agents that reply to customers, qualify leads, follow up, and send ready-to-buy requests to your team.',
  ctaPrimary: { label: 'Try live demo →', href: '#demo' },
  ctaSecondary: { label: 'See pricing', href: '#pricing' },
  trustBadges: [],
  chat: {
    ownerMessage: 'Hi! Do you handle WhatsApp and Instagram automation?',
    aiReply1:
      'Yes! I can reply to customers, qualify leads, follow up, and send ready-to-buy requests to you.',
    aiReply2: 'Our setup starts from 200,000 KZT and takes 3–7 days.',
    lead: {
      label: 'New qualified lead',
      service: 'Facial treatment',
      need: 'Skin consultation',
      time: 'Tomorrow after 17:00',
      status: 'Hot lead',
    },
  },
}

export const HOW_IT_WORKS = {
  headline: 'How it works',
  subheadline: 'A simple process designed for busy business owners.',
  steps: [
    {
      number: '01',
      icon: 'Link2' as const,
      title: 'Connect your channels',
      description:
        'We connect WhatsApp, Instagram and Telegram to your AI platform.',
    },
    {
      number: '02',
      icon: 'BookOpen' as const,
      title: 'Train your AI employee',
      description:
        'We learn about your business, services and customers so the AI speaks like your team.',
    },
    {
      number: '03',
      icon: 'Users' as const,
      title: 'Receive qualified leads',
      description:
        'AI replies, qualifies, follows up and sends ready-to-buy leads straight to you.',
    },
  ],
}

export type DemoScenario = {
  id: string
  label: string
  agentName: string
  messages: { from: 'user' | 'ai'; text: string }[]
  hidden?: boolean
  leadSummary: {
    service: string
    need: string
    time: string
    status: string
  }
}

export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'damiworks',
    label: 'DamiWorks',
    agentName: 'DamiWorks consultant',
    messages: [
      { from: 'user', text: 'What can your AI do for my business?' },
      {
        from: 'ai',
        text: 'I qualify incoming leads, answer FAQs 24/7, book appointments, and send you a clear summary of every conversation.',
      },
    ],
    leadSummary: {
      service: 'Custom AI employee',
      need: 'Lead qualification',
      time: 'ASAP',
      status: 'Discovery',
    },
  },
  {
    id: 'beauty',
    label: 'Beauty salon',
    agentName: 'Beauty salon AI',
    messages: [
      { from: 'user', text: 'Hi, how much does the treatment cost?' },
      {
        from: 'ai',
        text: 'The price starts from 18,000 KZT. I can help choose the right option and book a convenient time.',
      },
    ],
    leadSummary: {
      service: 'Facial treatment',
      need: 'Skin consultation',
      time: 'Tomorrow after 17:00',
      status: 'Hot lead',
    },
  },
  {
    id: 'english',
    label: 'English school',
    agentName: 'English school AI',
    messages: [
      { from: 'user', text: 'Do you have beginner English courses?' },
      {
        from: 'ai',
        text: 'Yes! We have beginner groups starting each month, 3 times a week. I can sign you up for a free trial lesson.',
      },
    ],
    leadSummary: {
      service: 'Beginner English course',
      need: 'Group lessons',
      time: 'This week',
      status: 'Warm lead',
    },
  },
  {
    id: 'dental',
    label: 'Dental clinic',
    agentName: 'Dental clinic AI',
    hidden: true,
    messages: [
      { from: 'user', text: 'How much does teeth whitening cost?' },
      {
        from: 'ai',
        text: 'Professional whitening starts at 35,000 KZT. We also offer a free consultation — I can book you in this week.',
      },
    ],
    leadSummary: {
      service: 'Teeth whitening',
      need: 'Free consultation',
      time: 'This week',
      status: 'Hot lead',
    },
  },
]

export const VISIBLE_DEMO_SCENARIOS = DEMO_SCENARIOS.filter((scenario) => !scenario.hidden)

// The DamiWorks consultant tab is the live chat (instance_id="damiworks_site").
export const DAMIWORKS_TAB_ID = 'damiworks'

// Custom demo is a separate live roleplay chat (instance_id="damiworks_custom_demo").
// It shares the chat UI/route but no state with the consultant.
export const CUSTOM_DEMO_TAB = {
  id: 'custom_demo',
  label: 'Your demo',
  title: 'Test an AI employee on your own business data',
  description:
    'Describe your business and chat as if you were a customer — see how an AI employee would answer. (Document upload coming soon.)',
}

export const TIERS = {
  headline: 'Что может AI-сотрудник',
  subheadline:
    'Начинаем с простых ответов и передачи заявок. Когда бизнес растёт — добавляем квалификацию, follow-up и интеграции.',
  cta: 'Не знаете, что нужно именно вам? Пройдите короткий подбор в DamiWorks-чате.',
  tiers: [
    {
      id: 'start',
      number: '01',
      name: 'Pilot / Start',
      tagline: 'Базовый AI-сотрудник',
      features: [
        { name: 'Ответы на частые вопросы', description: 'Товары, услуги, цены, доставка, запись и условия.' },
        { name: 'База знаний / FAQ', description: 'Собираем основную информацию о бизнесе: прайс, услуги, частые вопросы.' },
        { name: 'Сбор контакта', description: 'Имя, телефон, интересующий товар или услуга.' },
        { name: 'Передача заявки', description: 'Менеджеру, в WhatsApp/Telegram или Google Sheets.' },
        { name: '1 канал', description: 'WhatsApp, Instagram, Telegram или сайт.' },
        { name: 'Первые правки', description: 'Корректировки после реальных диалогов.' },
      ],
      footerText: 'Чтобы быстро проверить AI-сотрудника на реальных диалогах без сложной интеграции.',
    },
    {
      id: 'sales',
      number: '02',
      name: 'Sales Assistant',
      tagline: 'Включает всё из Pilot / Start + помогает продавать',
      features: [
        { name: 'Квалификация лидов', description: 'Понимает, кто готов купить, а кто просто спрашивает.' },
        { name: 'Сбор интереса и потребности', description: 'Товар, бюджет, удобное время связи.' },
        { name: 'Передача тёплых заявок', description: 'Менеджеру, в Google Sheets или CRM с кратким summary.' },
        { name: 'Follow-up', description: 'Мягкие напоминания, если клиент не ответил.' },
        { name: '2–3 канала', description: 'Например WhatsApp + Instagram + сайт.' },
        { name: 'Регулярные улучшения', description: 'Правки базы знаний и сценариев после запуска.' },
      ],
      footerText: 'Когда AI должен не просто отвечать, а отделять тёплых клиентов от случайных вопросов.',
    },
    {
      id: 'integrated',
      number: '03',
      name: 'Integrated AI Employee',
      tagline: 'Включает всё из Sales Assistant + интеграции',
      features: [
        { name: 'CRM/API', description: 'Подключение к внутренним системам бизнеса.' },
        { name: 'Склад, заказы, статусы', description: 'Наличие, этап заказа, доставка или другие данные.' },
        { name: 'Маршрутизация', description: 'Разные менеджеры, отделы или сценарии.' },
        { name: 'Кастомные бизнес-правила', description: 'Логика под реальные процессы компании.' },
        { name: 'Несколько каналов', description: 'Расширение на разные точки контакта.' },
        { name: 'Расширенный мониторинг', description: 'Контроль качества, стабильности и сложных сценариев.' },
      ],
      footerText: 'Когда AI должен работать не только в переписке, но и с данными, правилами и командами внутри бизнеса.',
    },
  ],
}

export const VALUE_PROP = {
  headline: 'Не просто подписка на бота',
  description:
    'SaaS даёт инструмент. DamiWorks помогает внедрить AI-сотрудника под ваш бизнес: собрать базу знаний, настроить сценарии, протестировать ответы и доработать систему после запуска.',
  items: [
    {
      number: '01',
      title: 'Настройка под ваш бизнес',
      description: 'Разбираем ваши товары, услуги, FAQ, цены, доставку и типовые вопросы клиентов.',
    },
    {
      number: '02',
      title: 'Запуск под ключ',
      description: 'Подключаем канал, настраиваем сценарии, сбор контактов и передачу заявок.',
    },
    {
      number: '03',
      title: 'Сопровождение после запуска',
      description: 'Смотрим реальные диалоги, исправляем слабые ответы и обновляем базу знаний.',
    },
  ],
}

export const PRICING = {
  headline: 'Простые цены. Без скрытых платежей.',
  subheadline: 'Прозрачные пакеты под разные задачи: от первого запуска до квалификации лидов, интеграций и сложных сценариев.',
  note: 'Итоговая стоимость зависит от объёма и сложности проекта.',
  plans: [
    {
      id: 'start',
      name: 'Pilot / Start',
      description: 'Для первого запуска на одном канале: ответы на частые вопросы, сбор контакта и передача заявки менеджеру.',
      priceSetup: 'от 150 000 ₸ за запуск',
      priceMonthly: '1 месяц сопровождения в цене',
      priceMonthlyDetail: 'далее от 40 000–60 000 ₸/мес' as string | null,
      badge: null as string | null,
      highlighted: false,
      features: [
        '1 канал',
        'База знаний / FAQ',
        'Ответы на частые вопросы',
        'Сбор контактов',
        'Передача заявки менеджеру или в таблицу',
        'Тестирование',
        'Первые правки по реальным диалогам',
      ],
      supportNote: 'Сопровождение после первого месяца: обновление базы знаний, правки ответов, поддержка работы и базовый контроль качества.' as string | null,
      limitNote: 'Подходит для пилота. Дополнительные каналы, сложные сценарии и интеграции оцениваются отдельно.' as string | null,
      reassurance: 'После первого месяца можно оставить сопровождение, расширить пакет или отключить.' as string | null,
      cta: 'Начать',
    },
    {
      id: 'sales',
      name: 'Sales Assistant',
      description: 'Для бизнеса, которому нужны квалификация лидов, несколько каналов и передача тёплых заявок менеджеру.',
      priceSetup: 'от 350 000 ₸ за запуск',
      priceMonthly: '+ от 120 000 ₸/мес',
      priceMonthlyDetail: null as string | null,
      badge: 'ПОПУЛЯРНЫЙ' as string | null,
      highlighted: true,
      features: [
        '1–3 канала',
        'Квалификация лидов',
        'Сбор контакта и интереса',
        'Передача в WhatsApp / Google Sheets / CRM',
        'Простые follow-up сценарии',
        'Тестирование сценариев продаж',
        'Регулярные правки и улучшения',
      ],
      supportNote: null as string | null,
      limitNote: null as string | null,
      reassurance: null as string | null,
      cta: 'Начать',
    },
    {
      id: 'integrated',
      name: 'Integrated AI Employee',
      description: 'Для сложных процессов: CRM/API, маршрутизация, склад/заказы, несколько команд и кастомная логика.',
      priceSetup: 'от 700 000 ₸ за запуск',
      priceMonthly: '+ от 200 000 ₸/мес',
      priceMonthlyDetail: null as string | null,
      badge: null as string | null,
      highlighted: false,
      features: [
        'Несколько каналов',
        'CRM/API интеграции',
        'Склад, заказы или статусы',
        'Маршрутизация на разных менеджеров',
        'Кастомные бизнес-правила',
        'Расширенный мониторинг',
      ],
      supportNote: null as string | null,
      limitNote: null as string | null,
      reassurance: null as string | null,
      cta: 'Обсудить проект',
    },
  ],
}

export const CONTACT = {
  headline: "Let's talk about\nyour business",
  description: "Tell us a few details and we'll show you how DamiWorks can help.",
  note: 'We usually reply within a few hours.',
  businessTypes: [
    'Beauty / Wellness',
    'Education / Tutoring',
    'Dental / Medical',
    'Retail / E-commerce',
    'Logistics / Delivery',
    'Real Estate',
    'Other',
  ],
  successMessage: "Thanks — we'll contact you soon.",
}

export const FOOTER = {
  tagline: 'AI employees for sales and support.',
  badges: ['Done-for-you implementation', 'Post-launch support', 'Built around your workflow'],
}
