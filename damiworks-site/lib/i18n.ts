import type { IntakeField } from '@/lib/intake'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Locale = 'en' | 'ru'

export interface DictSite {
  name: string
  tagline: string
}

export interface DictNavLink {
  label: string
  href: string
}

export interface DictHeroSimMessage {
  from: 'user' | 'ai'
  text: string
  leadStateIndex?: number
}

export interface DictHeroLeadState {
  service: string
  objection: string
  need: string
  time: string
  status: string
}

export interface DictHeroScenario {
  id: string
  messages: DictHeroSimMessage[]
  leadStates: DictHeroLeadState[]
}

export interface DictHeroChat {
  headerTitle: string
  onlineLabel: string
  leadLabel: string
  leadFieldLabels: { service: string; objection: string; need: string; time: string; status: string }
  scenarios: DictHeroScenario[]
}

export interface DictHero {
  eyebrow: string
  headlinePart1: string
  headlineAccent: string
  subheadline: string
  ctaPrimary: { label: string; href: string }
  ctaSecondary: { label: string; href: string }
  trustBadges: string[]
  chat: DictHeroChat
}

export interface DictHowItWorksStep {
  number: string
  icon: 'Link2' | 'BookOpen' | 'Users'
  title: string
  description: string
}

export interface DictHowItWorks {
  headline: string
  subheadline: string
  steps: DictHowItWorksStep[]
}

export interface DictDemoScenario {
  id: string
  label: string
  agentName: string
  messages: { from: 'user' | 'ai'; text: string }[]
  leadSummary: { service: string; need: string; time: string; status: string }
}

export interface DictDemoStaticLabels {
  inputPlaceholder: string
  sendAriaLabel: string
  onlineLabel: string
}

export interface DictLeadSummaryLabels {
  title: string
  service: string
  need: string
  time: string
  status: string
  sendToOwnerButton: string
}

export interface DictPackageSummaryLabels {
  title: string
  channels: string
  tasks: string
  recommendation: string
  nextStep: {
    label: string
    completeAssessment: string
    leaveContact: string
    leadSubmitted: string
  }
  empty: string
  status: {
    beforeIntake: string
    packageSelected: string
    leadSubmitted: string
  }
  packageLabels: {
    start: string
    sales: string
    integrated: string
  }
}

export interface DictCustomSummaryLabels {
  title: string
  text: string
  status: string
}

export interface DictCustomDemoTab {
  id: string
  label: string
  title: string
  description: string
}

export interface DictDemo {
  headline: string
  subheadline: string
  scenarios: DictDemoScenario[]
  customDemoTab: DictCustomDemoTab
  staticChat: DictDemoStaticLabels
  leadSummary: DictLeadSummaryLabels
  packageSummary: DictPackageSummaryLabels
  customSummary: DictCustomSummaryLabels
}

export interface DictTierFeature {
  name: string
  description: string
}

export interface DictTier {
  id: string
  number: string
  name: string
  tagline: string
  features: DictTierFeature[]
  footerText: string
}

export interface DictCapabilities {
  headline: string
  subheadline: string
  cta: string
  ctaLink: string
  tiers: DictTier[]
}

export interface DictValuePropItem {
  number: string
  title: string
  description: string
}

export interface DictValueProp {
  headline: string
  description: string
  items: DictValuePropItem[]
}

export interface DictPricingPlan {
  id: string
  name: string
  description: string
  priceSetup: string
  priceMonthly: string
  priceMonthlyDetail: string | null
  badge: string | null
  highlighted: boolean
  features: string[]
  supportNote: string | null
  limitNote: string | null
  reassurance: string | null
  cta: string
}

export interface DictPricing {
  headline: string
  subheadline: string
  note: string
  plans: DictPricingPlan[]
}

export interface DictContact {
  headline: string
  description: string
  note: string
  placeholderName: string
  placeholderContact: string
  placeholderBusinessType: string
  placeholderMessage: string
  submitButton: string
  successMessage: string
  businessTypes: string[]
}

export interface DictFooter {
  tagline: string
  badges: string[]
}

export interface DictLiveChatSummaryLabels {
  recommendation: string
  editButton: string
  expandButton: string
  collapseButton: string
  channels: string
  tasks: string
  handoff: string
  volume: string
  timeline: string
  price: string
}

export interface DictLiveChat {
  introMessage: string
  introChips: string[]
  sendLeadChipLabel: string
  postIntakeChips: string[]
  stepLabelPattern: string
  optionalLabel: string
  skipLabel: string
  confirmButtonPattern: string
  confirmButtonEmpty: string
  summaryLabels: DictLiveChatSummaryLabels
  packageSelectedPattern: string
  perDayLabel: string
  askQuestionButton: string
  sendToOwnerButton: string
  sentConfirmation: string
  editAnswersButton: string
  intakeStartMessage: string
  intakeCompleteMessage: string
  errorMessage: string
  resetTitle: string
  resetLabel: string
  inputPlaceholder: string
  sendAriaLabel: string
  onlineLabel: string
  leadSentChipLabel: string
  contactClosedPill: string
  contactClosedInputPlaceholder: string
}

export interface DictCustomDemoChat {
  introMessage: string
  headerTitle: string
  inputPlaceholder: string
  errorMessage: string
  resetTitle: string
  resetLabel: string
  sendAriaLabel: string
  onlineLabel: string
}

export interface DictIntakeQuestion {
  id: IntakeField
  text: string
  options: string[]
  // Canonical Russian values stored in IntakeState — must stay Russian until
  // lib/intake.ts scoring logic is refactored. UI displays options[], scoring
  // uses values[]. For ru locale values === options.
  values: string[]
  multi: boolean
  optional?: boolean
}

export interface DictIntake {
  questions: DictIntakeQuestion[]
}

export interface DictLangSwitcher {
  enLabel: string
  ruLabel: string
}

export interface DictMetadata {
  title: string
  description: string
}

export interface Dict {
  locale: Locale
  metadata: DictMetadata
  site: DictSite
  nav: DictNavLink[]
  bookACallLabel: string
  langSwitcher: DictLangSwitcher
  hero: DictHero
  howItWorks: DictHowItWorks
  demo: DictDemo
  capabilities: DictCapabilities
  valueProp: DictValueProp
  pricing: DictPricing
  contact: DictContact
  footer: DictFooter
  liveChat: DictLiveChat
  customDemoChat: DictCustomDemoChat
  intake: DictIntake
}

// ---------------------------------------------------------------------------
// English dictionary
// ---------------------------------------------------------------------------

const en: Dict = {
  locale: 'en',
  metadata: {
    title: 'DamiWorks — AI Employees for Sales and Support',
    description:
      'AI employees for WhatsApp, Instagram and websites. Reply to customers, qualify leads and hand off warm requests to your team.',
  },
  site: {
    name: 'DamiWorks',
    tagline: 'AI employees for sales and support.',
  },
  nav: [
    { label: 'How it works', href: '#how-it-works' },
    { label: 'Demo', href: '#demo' },
    { label: 'Pricing', href: '#pricing' },
    { label: 'Contact', href: '#contact' },
  ],
  bookACallLabel: 'Book a call',
  langSwitcher: { enLabel: 'EN', ruLabel: 'RU' },
  hero: {
    eyebrow: '',
    headlinePart1: 'An AI employee that turns inquiries ',
    headlineAccent: 'into customers',
    subheadline:
      'DamiWorks builds AI employees that reply to customers, qualify leads, follow up, and hand off warm leads to your team.',
    ctaPrimary: { label: 'Try live demo →', href: '#demo' },
    ctaSecondary: { label: 'See pricing', href: '#pricing' },
    trustBadges: [],
    chat: {
      headerTitle: 'AI receptionist',
      onlineLabel: 'Online',
      leadLabel: 'New inquiry',
      leadFieldLabels: { service: 'Service', objection: 'Objection', need: 'Need', time: 'Time', status: 'Status' },
      scenarios: [
        {
          id: 'beauty',
          messages: [
            { from: 'user', text: 'Hi! How much is RF facial lifting?', leadStateIndex: 1 },
            { from: 'ai',   text: 'Hi! RF facial lifting starts from ₸18,000. It helps tighten the skin and improve tone without injections or long downtime.' },
            { from: 'user', text: "That feels a bit expensive. I'm not sure it's right for me.", leadStateIndex: 2 },
            { from: 'ai',   text: "I understand. You can start with a short consultation: a specialist will look at your skin, explain whether RF lifting makes sense for you, and recommend the right option without unnecessary procedures." },
            { from: 'user', text: 'Okay. Do you have any time tomorrow after 5 PM?', leadStateIndex: 3 },
            { from: 'ai',   text: "Yes, there's an opening tomorrow at 6:30 PM. Would you like me to book you for that time?" },
            { from: 'user', text: 'Yes, please book me.', leadStateIndex: 4 },
            { from: 'ai',   text: "Done — you're booked for tomorrow at 6:30 PM. See you then!" },
            { from: 'user', text: 'Thank you, goodbye.' },
          ],
          leadStates: [
            { service: '—', objection: '—', need: '—', time: '—', status: 'New inquiry' },
            { service: 'RF facial lifting', objection: '—', need: 'Interested in procedure', time: '—', status: 'Consultation' },
            { service: 'RF facial lifting', objection: 'Price / hesitation', need: 'Check if procedure fits', time: '—', status: 'Warm lead' },
            { service: 'RF facial lifting', objection: 'Consultation offered', need: 'Requested time after 5 PM', time: 'After 5 PM', status: 'Booking in progress' },
            { service: 'RF facial lifting', objection: 'Consultation offered', need: 'Booking confirmed', time: 'Tomorrow, 6:30 PM', status: 'Booked' },
          ],
        },
        {
          id: 'education',
          messages: [
            { from: 'user', text: 'Hi! Do you have English classes for school students?', leadStateIndex: 1 },
            { from: 'ai',   text: "Hi! Yes, we offer English classes for school students in small groups and one-on-one. We recommend the format based on the child's age, goal, and schedule." },
            { from: 'user', text: "We already tried courses before, but didn't see much progress.", leadStateIndex: 2 },
            { from: 'ai',   text: "I understand. Often the issue is not the child, but the wrong format or a program that is too general. In the trial lesson, the teacher shows how classes work, identifies the child's strengths and weak spots, and explains what plan can lead to clearer progress." },
            { from: 'user', text: 'Okay. Is there any time this week after school?', leadStateIndex: 3 },
            { from: 'ai',   text: "Yes, there's a trial lesson on Thursday at 4:00 PM. Would you like me to book it?" },
            { from: 'user', text: 'Yes, please book it.', leadStateIndex: 4 },
            { from: 'ai',   text: "Done — the trial lesson is booked for Thursday at 4:00 PM. We'll send the details and a reminder before the lesson." },
            { from: 'user', text: 'Thank you!' },
          ],
          leadStates: [
            { service: '—', objection: '—', need: '—', time: '—', status: 'New inquiry' },
            { service: 'English for school students', objection: '—', need: 'Choose learning format', time: '—', status: 'Consultation' },
            { service: 'English for school students', objection: 'No progress before', need: 'Trial lesson and clear plan', time: '—', status: 'Warm lead' },
            { service: 'English for school students', objection: 'Trial lesson offered', need: 'After-school booking', time: 'After school', status: 'Booking in progress' },
            { service: 'English for school students', objection: 'Trial lesson offered', need: 'Trial lesson confirmed', time: 'Thursday, 4:00 PM', status: 'Booked' },
          ],
        },
      ],
    },
  },
  howItWorks: {
    headline: 'How it works',
    subheadline: 'A simple process designed for busy business owners.',
    steps: [
      {
        number: '01',
        icon: 'Link2',
        title: 'Connect your channels',
        description: 'We connect WhatsApp, Instagram and Telegram to your AI platform.',
      },
      {
        number: '02',
        icon: 'BookOpen',
        title: 'Train your AI employee',
        description:
          'We learn about your business, services and customers so the AI speaks like your team.',
      },
      {
        number: '03',
        icon: 'Users',
        title: 'Receive qualified leads',
        description: 'AI replies, qualifies, follows up and sends ready-to-buy leads straight to you.',
      },
    ],
  },
  demo: {
    headline: 'Choose a demo',
    subheadline:
      'Start with the DamiWorks consultant, then explore examples of AI employees for different industries.',
    scenarios: [
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
    ],
    customDemoTab: {
      id: 'custom_demo',
      label: 'Your demo',
      title: 'Test an AI employee on your own business data',
      description:
        'Describe your business and chat as if you were a customer — see how an AI employee would answer. (Document upload coming soon.)',
    },
    staticChat: {
      inputPlaceholder: 'Type a message...',
      sendAriaLabel: 'Send',
      onlineLabel: 'Online',
    },
    leadSummary: {
      title: 'Lead summary',
      service: 'Service',
      need: 'Need',
      time: 'Time',
      status: 'Status',
      sendToOwnerButton: 'Lead ready for handoff',
    },
    packageSummary: {
      title: 'Package selection',
      channels: 'Channels',
      tasks: 'Tasks',
      recommendation: 'Recommendation',
      nextStep: {
        label: 'Next step',
        completeAssessment: 'Complete the short assessment',
        leaveContact: 'Leave a contact to discuss launch',
        leadSubmitted: 'Lead submitted',
      },
      empty: '—',
      status: {
        beforeIntake: 'Takes about 1 minute',
        packageSelected: 'Package selected',
        leadSubmitted: 'Lead submitted',
      },
      packageLabels: {
        start: 'Pilot / Start',
        sales: 'Sales Assistant',
        integrated: 'Integrated AI Employee',
      },
    },
    customSummary: {
      title: 'Your demo',
      text: 'Describe your business or upload materials — the AI will show how it could respond to your customers.',
      status: 'Demo uses your data',
    },
  },
  capabilities: {
    headline: 'What an AI employee can do',
    subheadline:
      'We match the level of automation to your current process: from answers and lead handoff to qualification, follow-up, integrations, and quality control.',
    cta: 'Not sure what you need? Take the short quiz in the DamiWorks chat.',
    ctaLink: 'Find my package →',
    tiers: [
      {
        id: 'start',
        number: '01',
        name: 'Pilot / Start',
        tagline: 'Basic AI employee',
        features: [
          { name: 'FAQ answers', description: 'Products, services, prices, delivery, booking, and terms.' },
          { name: 'Knowledge base / FAQ', description: 'We compile the core business info: price list, services, common questions.' },
          { name: 'Contact collection', description: 'Name, phone number, product or service of interest.' },
          { name: 'Lead handoff', description: 'To manager, WhatsApp/Telegram, or Google Sheets.' },
          { name: '1 channel', description: 'WhatsApp, Instagram, Telegram, or website.' },
          { name: 'First corrections', description: 'Adjustments based on real conversations.' },
        ],
        footerText: 'To quickly test an AI employee on real conversations without a complex integration.',
      },
      {
        id: 'sales',
        number: '02',
        name: 'Sales Assistant',
        tagline: 'Everything in Pilot / Start + helps you sell',
        features: [
          { name: 'Lead qualification', description: 'Understands who is ready to buy vs. just browsing.' },
          { name: 'Interest & need collection', description: 'Product, budget, preferred contact time.' },
          { name: 'Warm lead handoff', description: 'To manager, Google Sheets, or CRM with a brief summary.' },
          { name: 'Follow-up', description: 'Soft reminders if the customer hasn\'t replied.' },
          { name: '2–3 channels', description: 'E.g. WhatsApp + Instagram + website.' },
          { name: 'Regular improvements', description: 'Knowledge base and scenario updates after launch.' },
        ],
        footerText: 'When AI should not just answer, but separate warm leads from casual questions.',
      },
      {
        id: 'integrated',
        number: '03',
        name: 'Integrated AI Employee',
        tagline: 'Everything in Sales Assistant + integrations',
        features: [
          { name: 'CRM/API', description: 'Integration with internal business systems.' },
          { name: 'Warehouse, orders, statuses', description: 'Stock, order stage, delivery, or other data.' },
          { name: 'Routing', description: 'Different managers, departments, or scenarios.' },
          { name: 'Custom business rules', description: 'Logic tailored to real company processes.' },
          { name: 'Multiple channels', description: 'Expansion across different customer touchpoints.' },
          { name: 'Advanced monitoring', description: 'Quality control, stability, and complex scenario oversight.' },
        ],
        footerText:
          'When AI needs to work not only in conversations, but also with business data, rules, and teams.',
      },
    ],
  },
  valueProp: {
    headline: 'Not just access to AI agents',
    description:
      'A platform gives you access to a tool. DamiWorks handles the implementation end to end: we analyze your process, build the knowledge base, design scenarios, connect channels, test responses, and improve the system after launch. You get a configured AI employee ready for real customer conversations — not an empty dashboard.',
    items: [
      {
        number: '01',
        title: 'Business and scenario analysis',
        description:
          'We identify what customers ask, where leads get lost, and what information should be collected before handoff.',
      },
      {
        number: '02',
        title: 'Done-for-you setup and launch',
        description:
          'We build the knowledge base, tone of voice, answer flows, contact capture, qualification logic, and lead handoff.',
      },
      {
        number: '03',
        title: 'Post-launch support',
        description:
          'We review real conversations, fix weak answers, update the knowledge base, and help the AI employee become stable in production.',
      },
    ],
  },
  pricing: {
    headline: 'Simple pricing. No hidden fees.',
    subheadline:
      'Clear packages for different needs: from a first launch to lead qualification, integrations, and advanced workflows.',
    note: 'Final cost depends on project scope and complexity.',
    plans: [
      {
        id: 'start',
        name: 'Pilot / Start',
        description:
          'For a first launch on one channel: FAQ answers, contact collection, and lead handoff to manager.',
        priceSetup: 'from 150,000 ₸ setup',
        priceMonthly: '1 month of support included in the price',
        priceMonthlyDetail: 'then from ₸40,000–60,000/month',
        badge: null,
        highlighted: false,
        features: [
          '1 channel',
          'Knowledge base / FAQ',
          'FAQ answers',
          'Contact collection',
          'Lead handoff to manager or spreadsheet',
          'Testing',
          'First corrections from real conversations',
        ],
        supportNote:
          'During the first month of support, we review real conversations, improve the knowledge base, and stabilize the core flow. Additional channels, advanced qualification, and integrations are estimated separately. After the first month, you can continue support, expand the package, or stop without obligation.',
        limitNote: null,
        reassurance: null,
        cta: 'Get started',
      },
      {
        id: 'sales',
        name: 'Sales Assistant',
        description:
          'For businesses that need lead qualification, multiple channels, and warm lead handoff to manager.',
        priceSetup: 'from 350,000 ₸ setup',
        priceMonthly: '1 month of support included in the price',
        priceMonthlyDetail: 'then from ₸120,000/month',
        badge: 'POPULAR',
        highlighted: true,
        features: [
          '1–3 channels',
          'Lead qualification',
          'Contact & interest collection',
          'Handoff to WhatsApp / Google Sheets / CRM',
          'Simple follow-up scenarios',
          'Sales scenario testing',
          'Regular improvements',
        ],
        supportNote:
          'During the first month of support, we review qualification quality, warm-lead criteria, handoff, and follow-up scenarios. After that, you can continue support, expand channels, add integrations, or keep the current scope.',
        limitNote: null,
        reassurance: null,
        cta: 'Get started',
      },
      {
        id: 'integrated',
        name: 'Integrated AI Employee',
        description:
          'For complex processes: CRM/API, routing, warehouse/orders, multiple teams, and custom logic.',
        priceSetup: 'from 700,000 ₸ setup',
        priceMonthly: '3 months of support included in the price',
        priceMonthlyDetail: 'then from ₸200,000/month',
        badge: null,
        highlighted: false,
        features: [
          'Multiple channels',
          'CRM/API integrations',
          'Warehouse, orders, or statuses',
          'Routing to different managers',
          'Custom business rules',
          'Advanced monitoring',
        ],
        supportNote:
          'During the first 3 months of support, we monitor integration stability, routing, answer quality, and complex business scenarios. Ongoing support is agreed by scope: monitoring, improvements, scenario development, and integration support.',
        limitNote: null,
        reassurance: null,
        cta: 'Discuss project',
      },
    ],
  },
  contact: {
    headline: "Let's talk about\nyour business",
    description: "Tell us a few details and we'll show you how DamiWorks can help.",
    note: 'We usually reply within a few hours.',
    placeholderName: 'Your name',
    placeholderContact: 'WhatsApp / Telegram',
    placeholderBusinessType: 'Select your business type',
    placeholderMessage: 'What do you want to automate? (optional)',
    submitButton: 'Send request',
    successMessage: "Thanks — we'll contact you soon.",
    businessTypes: [
      'Beauty / Wellness',
      'Education / Tutoring',
      'Dental / Medical',
      'Retail / E-commerce',
      'Logistics / Delivery',
      'Real Estate',
      'Other',
    ],
  },
  footer: {
    tagline: 'AI employees for sales and support.',
    badges: ['Done-for-you implementation', 'Post-launch support', 'Built around your workflow'],
  },
  liveChat: {
    introMessage:
      "Hi! I'll help you understand which AI employee fits your business: for answering customers, qualifying leads, and handing off to managers.\n\nYou can ask a question in chat or take a short 1-minute quiz.",
    introChips: [
      'Find an AI employee',
      'How much does it cost?',
      'How does it work?',
      'How is it different from a chatbot?',
    ],
    sendLeadChipLabel: 'Submit inquiry',
    postIntakeChips: [
      'Why this price?',
      "What's included?",
      'Can we start cheaper?',
      'How does launch work?',
      'Submit inquiry',
    ],
    stepLabelPattern: 'Step {n} of {total}',
    optionalLabel: 'Optional',
    skipLabel: 'Skip →',
    confirmButtonPattern: 'Confirm ({n})',
    confirmButtonEmpty: 'Confirm',
    summaryLabels: {
      recommendation: 'Recommendation',
      editButton: 'Edit',
      expandButton: 'Expand',
      collapseButton: 'Collapse',
      channels: 'Channels:',
      tasks: 'Tasks:',
      handoff: 'Handoff:',
      volume: 'Volume:',
      timeline: 'Timeline:',
      price: 'Price',
    },
    packageSelectedPattern: '✅ {pkg} selected',
    perDayLabel: '/day',
    askQuestionButton: 'Ask a question →',
    sendToOwnerButton: 'Send to Damir',
    sentConfirmation: 'Summary sent to Damir. You can ask questions below.',
    editAnswersButton: '← Edit answers',
    intakeStartMessage: "Great, I'll ask 5 short questions and find the right package.",
    intakeCompleteMessage: "Great! Based on your answers — here's my recommendation:",
    errorMessage: 'Something went wrong. Please try again.',
    resetTitle: 'Reset',
    resetLabel: 'Reset',
    inputPlaceholder: 'Ask a question...',
    sendAriaLabel: 'Send',
    onlineLabel: 'Online',
    leadSentChipLabel: '✅ Sent',
    contactClosedPill: '✅ Request sent. We will contact you on WhatsApp/Telegram.',
    contactClosedInputPlaceholder: 'Request sent',
  },
  customDemoChat: {
    introMessage:
      "Upload materials about your business — proposal, presentation, price list, catalog, FAQ, or service description. If you don't have a file, just describe here what you sell, prices, terms, and common customer questions.\n\nThen write a question as if you were a customer — I'll show how an AI employee would respond based on these materials.",
    headerTitle: 'Custom demo',
    inputPlaceholder: 'Describe your business or write a question as a customer...',
    errorMessage: 'Something went wrong. Please try again.',
    resetTitle: 'Reset',
    resetLabel: 'Reset',
    sendAriaLabel: 'Send',
    onlineLabel: 'Online',
  },
  intake: {
    questions: [
      {
        id: 'channels',
        text: 'Where do customers contact you? Select all that apply.',
        options: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Other'],
        values: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Другое'],
        multi: true,
      },
      {
        id: 'tasks',
        text: 'What should the AI employee do first? (select all that apply)',
        options: [
          'Answer questions',
          'Collect contacts',
          'Qualify leads',
          'Hand off to manager',
          'Follow-up',
        ],
        values: [
          'Отвечать на вопросы',
          'Собирать контакты',
          'Квалифицировать лидов',
          'Передавать заявки менеджеру',
          'Делать follow-up',
        ],
        multi: true,
      },
      {
        id: 'handoff',
        text: 'Where should leads be handed off?',
        options: ['Telegram', 'Google Sheets', 'amoCRM', 'Bitrix24', "Don't know yet"],
        values: ['Telegram', 'Google Sheets', 'amoCRM', 'Bitrix24', 'Пока не знаю'],
        multi: false,
      },
      {
        id: 'volume',
        text: 'How many inquiries per day approximately?',
        options: ['1–10', '10–30', '30–100', '100+'],
        values: ['1–10', '10–30', '30–100', '100+'],
        multi: false,
      },
      {
        id: 'timeline',
        text: 'When do you want to launch?',
        options: ['Within days', 'This month', 'Just exploring'],
        values: ['В ближайшие дни', 'В этом месяце', 'Просто изучаю'],
        multi: false,
      },
      {
        id: 'businessType',
        text: 'What type of business? (optional)',
        options: ['Services', 'Online shop', 'Education', 'Clinic / Salon', 'Other'],
        values: ['Услуги', 'Онлайн-магазин', 'Обучение', 'Клиника/салон', 'Другое'],
        multi: false,
        optional: true,
      },
    ],
  },
}

// ---------------------------------------------------------------------------
// Russian dictionary
// ---------------------------------------------------------------------------

const ru: Dict = {
  locale: 'ru',
  metadata: {
    title: 'DamiWorks — AI-сотрудники для продаж и поддержки',
    description:
      'AI-сотрудники для WhatsApp, Instagram и сайта: отвечают клиентам, квалифицируют заявки и передают тёплые лиды менеджеру.',
  },
  site: {
    name: 'DamiWorks',
    tagline: 'AI-сотрудники для продаж и поддержки.',
  },
  nav: [
    { label: 'Как это работает', href: '#how-it-works' },
    { label: 'Демо', href: '#demo' },
    { label: 'Цены', href: '#pricing' },
    { label: 'Контакты', href: '#contact' },
  ],
  bookACallLabel: 'Записаться на звонок',
  langSwitcher: { enLabel: 'EN', ruLabel: 'RU' },
  hero: {
    eyebrow: '',
    headlinePart1: 'AI-сотрудник, который превращает обращения ',
    headlineAccent: 'в клиентов',
    subheadline:
      'DamiWorks создаёт AI-сотрудников, которые отвечают клиентам, квалифицируют лиды, делают follow-up и передают тёплые заявки вашей команде.',
    ctaPrimary: { label: 'Попробовать демо →', href: '#demo' },
    ctaSecondary: { label: 'Посмотреть цены', href: '#pricing' },
    trustBadges: [],
    chat: {
      headerTitle: 'AI-администратор',
      onlineLabel: 'Онлайн',
      leadLabel: 'Новая заявка',
      leadFieldLabels: { service: 'Услуга', objection: 'Возражение', need: 'Потребность', time: 'Время', status: 'Статус' },
      scenarios: [
        {
          id: 'beauty',
          messages: [
            { from: 'user', text: 'Здравствуйте! Сколько стоит RF-лифтинг лица?', leadStateIndex: 1 },
            { from: 'ai',   text: 'Здравствуйте! RF-лифтинг лица стоит от 18 000 ₸. Процедура помогает подтянуть кожу и улучшить тонус без инъекций и длительного восстановления.' },
            { from: 'user', text: 'Дороговато. Я не уверена, что мне подойдёт.', leadStateIndex: 2 },
            { from: 'ai',   text: 'Понимаю. Можно начать с короткой консультации: специалист посмотрит состояние кожи, объяснит, будет ли RF-лифтинг полезен именно вам, и подберёт вариант без лишних процедур.' },
            { from: 'user', text: 'Хорошо. Есть время завтра после 17:00?', leadStateIndex: 3 },
            { from: 'ai',   text: 'Да, есть свободное окно завтра в 18:30. Записать вас на это время?' },
            { from: 'user', text: 'Да, запишите.', leadStateIndex: 4 },
            { from: 'ai',   text: 'Готово, записали вас на завтра в 18:30. До встречи!' },
            { from: 'user', text: 'Спасибо, до свидания.' },
          ],
          leadStates: [
            { service: '—', objection: '—', need: '—', time: '—', status: 'Новая заявка' },
            { service: 'RF-лифтинг лица', objection: '—', need: 'Интерес к процедуре', time: '—', status: 'Консультация' },
            { service: 'RF-лифтинг лица', objection: 'Цена / сомнение', need: 'Понять, подойдёт ли процедура', time: '—', status: 'Тёплый лид' },
            { service: 'RF-лифтинг лица', objection: 'Предложена консультация', need: 'Запрос на время после 17:00', time: 'После 17:00', status: 'Оформление записи' },
            { service: 'RF-лифтинг лица', objection: 'Предложена консультация', need: 'Запись подтверждена', time: 'Завтра, 18:30', status: 'Записан' },
          ],
        },
        {
          id: 'education',
          messages: [
            { from: 'user', text: 'Здравствуйте! У вас есть английский для школьников?', leadStateIndex: 1 },
            { from: 'ai',   text: 'Здравствуйте! Да, есть занятия для школьников: в мини-группах и индивидуально. Подбираем формат под возраст, цель и расписание ребёнка.' },
            { from: 'user', text: 'Мы уже пробовали курсы, особого результата не было.', leadStateIndex: 2 },
            { from: 'ai',   text: 'Понимаю. Часто проблема не в ребёнке, а в неподходящем формате или слишком общей программе. На пробном уроке преподаватель покажет, как проходят занятия, оценит сильные и слабые стороны ребёнка и объяснит, какой план даст более понятный прогресс.' },
            { from: 'user', text: 'Хорошо. Можно на этой неделе после школы?', leadStateIndex: 3 },
            { from: 'ai',   text: 'Да, есть пробный урок в четверг в 16:00. Записать ребёнка на это время?' },
            { from: 'user', text: 'Да, запишите.', leadStateIndex: 4 },
            { from: 'ai',   text: 'Готово, записали на пробный урок в четверг в 16:00. Мы отправим детали и напоминание перед занятием.' },
            { from: 'user', text: 'Спасибо!' },
          ],
          leadStates: [
            { service: '—', objection: '—', need: '—', time: '—', status: 'Новая заявка' },
            { service: 'Английский для школьников', objection: '—', need: 'Подобрать формат обучения', time: '—', status: 'Консультация' },
            { service: 'Английский для школьников', objection: 'Раньше не было результата', need: 'Пробный урок и понятный план', time: '—', status: 'Тёплый лид' },
            { service: 'Английский для школьников', objection: 'Предложен пробный урок', need: 'Запись после школы', time: 'После школы', status: 'Оформление записи' },
            { service: 'Английский для школьников', objection: 'Предложен пробный урок', need: 'Пробный урок подтверждён', time: 'Четверг, 16:00', status: 'Записан' },
          ],
        },
      ],
    },
  },
  howItWorks: {
    headline: 'Как это работает',
    subheadline: 'Запуск без лишней сложности для занятых владельцев бизнеса.',
    steps: [
      {
        number: '01',
        icon: 'Link2',
        title: 'Подключаем каналы',
        description: 'Подключаем WhatsApp, Instagram, Telegram или сайт к AI-сотруднику.',
      },
      {
        number: '02',
        icon: 'BookOpen',
        title: 'Обучаем AI-сотрудника',
        description: 'Собираем базу знаний, изучаем услуги и настраиваем тон общения — AI отвечает в стиле вашей команды.',
      },
      {
        number: '03',
        icon: 'Users',
        title: 'Получаете квалифицированные лиды',
        description: 'AI отвечает на вопросы, квалифицирует лиды, делает follow-up и передаёт тёплые заявки.',
      },
    ],
  },
  demo: {
    headline: 'Выберите демо',
    subheadline:
      'Сначала попробуйте DamiWorks-консультанта, затем посмотрите примеры AI-сотрудников для разных ниш.',
    scenarios: [
      {
        id: 'damiworks',
        label: 'DamiWorks',
        agentName: 'Консультант DamiWorks',
        messages: [
          { from: 'user', text: 'Что может ваш AI для моего бизнеса?' },
          {
            from: 'ai',
            text: 'Квалифицирую входящие заявки, отвечаю на FAQ 24/7, записываю клиентов и отправляю вам краткое резюме по каждому диалогу.',
          },
        ],
        leadSummary: {
          service: 'Кастомный AI-сотрудник',
          need: 'Квалификация лидов',
          time: 'Как можно скорее',
          status: 'Разведка',
        },
      },
      {
        id: 'beauty',
        label: 'Салон красоты',
        agentName: 'AI салона красоты',
        messages: [
          { from: 'user', text: 'Привет, сколько стоит уход?' },
          {
            from: 'ai',
            text: 'Уход начинается от 18 000 ₸. Помогу подобрать подходящий вариант и записать на удобное время.',
          },
        ],
        leadSummary: {
          service: 'Уход за лицом',
          need: 'Консультация по коже',
          time: 'Завтра после 17:00',
          status: 'Горячий лид',
        },
      },
      {
        id: 'english',
        label: 'Школа английского',
        agentName: 'AI школы английского',
        messages: [
          { from: 'user', text: 'У вас есть курсы для начинающих?' },
          {
            from: 'ai',
            text: 'Да! Есть группы для начинающих, которые стартуют каждый месяц, 3 раза в неделю. Могу записать вас на пробный урок бесплатно.',
          },
        ],
        leadSummary: {
          service: 'Курс английского для начинающих',
          need: 'Групповые занятия',
          time: 'На этой неделе',
          status: 'Тёплый лид',
        },
      },
    ],
    customDemoTab: {
      id: 'custom_demo',
      label: 'Своё демо',
      title: 'Протестируйте AI-сотрудника на своих данных',
      description:
        'Опишите бизнес и общайтесь как клиент — посмотрите, как AI ответит. (Загрузка документов скоро.)',
    },
    staticChat: {
      inputPlaceholder: 'Написать сообщение...',
      sendAriaLabel: 'Отправить',
      onlineLabel: 'Онлайн',
    },
    leadSummary: {
      title: 'Сводка по лиду',
      service: 'Услуга',
      need: 'Потребность',
      time: 'Время',
      status: 'Статус',
      sendToOwnerButton: 'Заявка готова к передаче',
    },
    packageSummary: {
      title: 'Подбор пакета',
      channels: 'Каналы',
      tasks: 'Задачи',
      recommendation: 'Рекомендация',
      nextStep: {
        label: 'Следующий шаг',
        completeAssessment: 'Пройти короткий подбор',
        leaveContact: 'Оставить контакт для обсуждения запуска',
        leadSubmitted: 'Заявка отправлена',
      },
      empty: '—',
      status: {
        beforeIntake: 'Подбор займёт около минуты',
        packageSelected: 'Пакет подобран',
        leadSubmitted: 'Заявка отправлена',
      },
      packageLabels: {
        start: 'Pilot / Start',
        sales: 'Sales Assistant',
        integrated: 'Integrated AI Employee',
      },
    },
    customSummary: {
      title: 'Своё демо',
      text: 'Опишите бизнес или загрузите материалы — AI покажет, как мог бы отвечать вашим клиентам.',
      status: 'Демо строится на ваших данных',
    },
  },
  capabilities: {
    headline: 'Что может AI-сотрудник',
    subheadline:
      'Подбираем уровень автоматизации под текущие процессы: от ответов и передачи заявок до квалификации, follow-up, интеграций и контроля качества.',
    cta: 'Не знаете, что нужно именно вам? Пройдите короткий подбор в DamiWorks-чате.',
    ctaLink: 'Подобрать пакет →',
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
          { name: 'Сбор интереса и потребности', description: 'Товар, бюджет, потребность и удобное время связи.' },
          { name: 'Передача тёплых заявок', description: 'Менеджеру, в Google Sheets или CRM с краткой сводкой.' },
          { name: 'Follow-up', description: 'Мягкие напоминания, если клиент не ответил.' },
          { name: '2–3 канала', description: 'Например WhatsApp + Instagram + сайт.' },
          { name: 'Регулярные улучшения', description: 'Правки базы знаний и сценариев после запуска.' },
        ],
        footerText: 'Когда AI должен не просто отвечать, а отличать тёплых клиентов от тех, кто пока просто интересуется.',
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
          { name: 'Индивидуальные бизнес-правила', description: 'Правила под реальные процессы компании.' },
          { name: 'Несколько каналов', description: 'Расширение на разные точки контакта.' },
          { name: 'Расширенный мониторинг', description: 'Контроль качества, стабильности и сложных сценариев.' },
        ],
        footerText:
          'Когда AI должен работать не только в переписке, но и с данными, правилами и командами внутри бизнеса.',
      },
    ],
  },
  valueProp: {
    headline: 'Не просто доступ к AI-агентам',
    description:
      'Платформа даёт доступ к инструменту. DamiWorks берёт на себя внедрение под ключ: разбираем процессы, собираем базу знаний, проектируем сценарии, подключаем каналы, тестируем ответы и дорабатываем систему после запуска. Клиент получает не пустой кабинет, а настроенного AI-сотрудника, готового работать в реальных диалогах.',
    items: [
      {
        number: '01',
        title: 'Разбор бизнеса и сценариев',
        description:
          'Понимаем, какие вопросы задают клиенты, где теряются заявки и какие данные нужно собирать перед передачей менеджеру.',
      },
      {
        number: '02',
        title: 'Настройка и запуск под ключ',
        description:
          'Собираем базу знаний, настраиваем тон общения, сценарии ответов, сбор контактов, квалификацию и передачу заявок в нужный канал.',
      },
      {
        number: '03',
        title: 'Сопровождение после запуска',
        description:
          'Смотрим реальные диалоги, исправляем слабые ответы, обновляем базу знаний и помогаем довести AI-сотрудника до стабильной работы.',
      },
    ],
  },
  pricing: {
    headline: 'Простые цены. Без скрытых платежей.',
    subheadline:
      'Прозрачные пакеты под разные задачи: от первого запуска до квалификации лидов, интеграций и сложных сценариев.',
    note: 'Итоговая стоимость зависит от объёма и сложности проекта.',
    plans: [
      {
        id: 'start',
        name: 'Pilot / Start',
        description:
          'Для первого запуска на одном канале: ответы на частые вопросы, сбор контакта и передача заявки менеджеру.',
        priceSetup: 'от 150 000 ₸ за запуск',
        priceMonthly: '1 месяц сопровождения в цене',
        priceMonthlyDetail: 'далее от 40 000–60 000 ₸/мес',
        badge: null,
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
        supportNote:
          'В первый месяц сопровождения проверяем ответы на реальных диалогах, правим базу знаний и доводим базовый сценарий до стабильной работы. Дополнительные каналы, сложная квалификация и интеграции оцениваются отдельно. После первого месяца можно продолжить сопровождение, расширить пакет или остановиться без обязательств.',
        limitNote: null,
        reassurance: null,
        cta: 'Начать',
      },
      {
        id: 'sales',
        name: 'Sales Assistant',
        description:
          'Для бизнеса, которому нужны квалификация лидов, несколько каналов и передача тёплых заявок менеджеру.',
        priceSetup: 'от 350 000 ₸ за запуск',
        priceMonthly: '1 месяц сопровождения в цене',
        priceMonthlyDetail: 'далее от 120 000 ₸/мес',
        badge: 'ПОПУЛЯРНЫЙ',
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
        supportNote:
          'В первый месяц сопровождения проверяем качество квалификации, критерии тёплого лида, передачу заявок и follow-up сценарии. После первого месяца можно продолжить сопровождение, расширить каналы, добавить интеграции или зафиксировать текущий объём.',
        limitNote: null,
        reassurance: null,
        cta: 'Начать',
      },
      {
        id: 'integrated',
        name: 'Integrated AI Employee',
        description:
          'Для сложных процессов: CRM/API, маршрутизация, склад/заказы, несколько команд и индивидуальная логика.',
        priceSetup: 'от 700 000 ₸ за запуск',
        priceMonthly: '3 месяца сопровождения в цене',
        priceMonthlyDetail: 'далее от 200 000 ₸/мес',
        badge: null,
        highlighted: false,
        features: [
          'Несколько каналов',
          'CRM/API интеграции',
          'Склад, заказы или статусы',
          'Маршрутизация на разных менеджеров',
          'Индивидуальные бизнес-правила',
          'Расширенный мониторинг',
        ],
        supportNote:
          'В первые 3 месяца сопровождения контролируем стабильность интеграций, маршрутизацию, качество ответов и сложные бизнес-сценарии. Дальнейшее сопровождение согласуется по объёму: мониторинг, правки, развитие сценариев и поддержка интеграций.',
        limitNote: null,
        reassurance: null,
        cta: 'Обсудить проект',
      },
    ],
  },
  contact: {
    headline: 'Обсудим ваш\nбизнес',
    description: 'Расскажите о бизнесе — покажем, как DamiWorks может помочь.',
    note: 'Обычно отвечаем в течение нескольких часов.',
    placeholderName: 'Ваше имя',
    placeholderContact: 'WhatsApp / Telegram',
    placeholderBusinessType: 'Выберите тип бизнеса',
    placeholderMessage: 'Что хотите автоматизировать? Например: ответы в WhatsApp, заявки, запись, follow-up. (необязательно)',
    submitButton: 'Отправить заявку',
    successMessage: 'Спасибо — скоро свяжемся с вами.',
    businessTypes: [
      'Красота / Оздоровление',
      'Образование / Репетиторство',
      'Стоматология / Медицина',
      'Розница / Интернет-магазин',
      'Логистика / Доставка',
      'Недвижимость',
      'Другое',
    ],
  },
  footer: {
    tagline: 'AI-сотрудники для продаж и поддержки.',
    badges: [
      'Внедрение под ключ',
      'Сопровождение после запуска',
      'Под задачи бизнеса',
    ],
  },
  liveChat: {
    introMessage:
      'Привет! Я помогу понять, какой AI-сотрудник подойдёт вашему бизнесу: для ответов клиентам, квалификации заявок и передачи лидов менеджерам.\n\nМожете задать вопрос в чат или пройти короткий подбор за 1 минуту.',
    introChips: [
      'Подобрать AI-сотрудника',
      'Сколько стоит?',
      'Как это работает?',
      'Чем отличается от чат-бота?',
    ],
    sendLeadChipLabel: 'Оставить заявку',
    postIntakeChips: [
      'Почему такая цена?',
      'Что входит в запуск?',
      'Можно начать дешевле?',
      'Как проходит запуск?',
      'Оставить заявку',
    ],
    stepLabelPattern: 'Шаг {n} из {total}',
    optionalLabel: 'Необязательно',
    skipLabel: 'Пропустить →',
    confirmButtonPattern: 'Подтвердить ({n})',
    confirmButtonEmpty: 'Подтвердить',
    summaryLabels: {
      recommendation: 'Рекомендация',
      editButton: 'Изменить',
      expandButton: 'Развернуть',
      collapseButton: 'Свернуть',
      channels: 'Каналы:',
      tasks: 'Задачи:',
      handoff: 'Передача:',
      volume: 'Объём:',
      timeline: 'Запуск:',
      price: 'Стоимость',
    },
    packageSelectedPattern: '✅ {pkg} подобран',
    perDayLabel: '/день',
    askQuestionButton: 'Задать вопрос →',
    sendToOwnerButton: 'Отправить Дамиру',
    sentConfirmation: 'Сводка отправлена команде. Можно задать вопрос ниже.',
    editAnswersButton: '← Изменить ответы',
    intakeStartMessage: 'Отлично, задам 5 коротких вопросов и подберу подходящий пакет.',
    intakeCompleteMessage: 'Отлично! На основе ваших ответов — вот что рекомендую:',
    errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
    resetTitle: 'Сбросить',
    resetLabel: 'Сброс',
    inputPlaceholder: 'Задайте вопрос...',
    sendAriaLabel: 'Отправить',
    onlineLabel: 'Online',
    leadSentChipLabel: '✅ Отправлено',
    contactClosedPill: '✅ Заявка отправлена. Мы свяжемся с вами в WhatsApp/Telegram.',
    contactClosedInputPlaceholder: 'Заявка отправлена',
  },
  customDemoChat: {
    introMessage:
      'Загрузите материалы о бизнесе — КП, презентацию, прайс, каталог, FAQ или описание услуг. Если файла нет, просто опишите здесь, что продаёте, цены, условия и частые вопросы клиентов.\n\nЗатем напишите вопрос как будто вы клиент — я покажу, как AI-сотрудник ответит на основе этих материалов.',
    headerTitle: 'Custom demo',
    inputPlaceholder: 'Опишите бизнес или напишите вопрос как клиент...',
    errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
    resetTitle: 'Сбросить',
    resetLabel: 'Сброс',
    sendAriaLabel: 'Отправить',
    onlineLabel: 'Online',
  },
  intake: {
    questions: [
      {
        id: 'channels',
        text: 'Где вам пишут клиенты? Можно выбрать несколько.',
        options: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Другое'],
        values: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Другое'],
        multi: true,
      },
      {
        id: 'tasks',
        text: 'Что AI-сотрудник должен делать в первую очередь? (можно выбрать несколько)',
        options: [
          'Отвечать на вопросы',
          'Собирать контакты',
          'Квалифицировать лидов',
          'Передавать заявки менеджеру',
          'Делать follow-up',
        ],
        values: [
          'Отвечать на вопросы',
          'Собирать контакты',
          'Квалифицировать лидов',
          'Передавать заявки менеджеру',
          'Делать follow-up',
        ],
        multi: true,
      },
      {
        id: 'handoff',
        text: 'Куда передавать заявки?',
        options: ['Telegram', 'Google Sheets', 'amoCRM', 'Bitrix24', 'Пока не знаю'],
        values: ['Telegram', 'Google Sheets', 'amoCRM', 'Bitrix24', 'Пока не знаю'],
        multi: false,
      },
      {
        id: 'volume',
        text: 'Сколько примерно обращений в день?',
        options: ['1–10', '10–30', '30–100', '100+'],
        values: ['1–10', '10–30', '30–100', '100+'],
        multi: false,
      },
      {
        id: 'timeline',
        text: 'Когда хотите запустить?',
        options: ['В ближайшие дни', 'В этом месяце', 'Просто изучаю'],
        values: ['В ближайшие дни', 'В этом месяце', 'Просто изучаю'],
        multi: false,
      },
      {
        id: 'businessType',
        text: 'Какой у вас бизнес? (необязательно)',
        options: ['Услуги', 'Онлайн-магазин', 'Обучение', 'Клиника/салон', 'Другое'],
        values: ['Услуги', 'Онлайн-магазин', 'Обучение', 'Клиника/салон', 'Другое'],
        multi: false,
        optional: true,
      },
    ],
  },
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const dictionaries: Record<Locale, Dict> = { en, ru }

export function getDict(locale: Locale): Dict {
  return dictionaries[locale]
}
