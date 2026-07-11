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
  icon: 'Link2' | 'BookOpen' | 'Users' | 'MessageCircle' | 'Zap' | 'ListChecks' | 'Phone' | 'ClipboardList'
  title: string
  description: string
}

export interface DictHowItWorks {
  headline: string
  subheadline: string
  steps: DictHowItWorksStep[]
}

// «Где обычно теряются заявки» — pain section right after the hero.
export interface DictPain {
  headline: string
  emphasisTitle: string
  emphasisText: string
  items: string[]
  bottomLine: string
}

// «Это не обычный чат-бот» — objection-handling comparison section.
export interface DictVsChatbot {
  headline: string
  description1: string
  description2: string
  chatbotCard: { title: string; items: string[] }
  aiCard: { title: string; items: string[] }
}

// «Что можно автоматизировать» — tasks, not tiers.
export interface DictAutomate {
  headline: string
  actionLabel: string
  outcomeLabel: string
  exampleLabel: string
  items: { title: string; description: string; outcome: string; example: string }[]
  bottomLine: string
}

// «Что нужно от вас» — lowers the implementation fear.
export interface DictWhatWeNeed {
  headline: string
  items: { number: string; title: string; description: string }[]
  bottomLine: string
}

// «AI работает в рамках правил бизнеса» — trust/safety section.
export interface DictTrust {
  headline: string
  description1: string
  description2: string
  cards: string[]
}

export interface DictEvidence {
  eyebrow: string
  headline: string
  subheadline: string
  cards: { title: string; text: string }[]
  bottomLine: string
}

export interface DictFounder {
  eyebrow: string
  headline: string
  description: string
  name: string
  role: string
  personalNote: string
  points: string[]
  cta: string
}

export interface DictFaq {
  headline: string
  subheadline: string
  items: { question: string; answer: string }[]
}

export interface DictDemoScenario {
  id: string
  label: string
  agentName: string
  hidden?: boolean
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
  hidden?: boolean
}

export interface DictSchoolChatLabels {
  headerTitle: string
  onlineLabel: string
  inputPlaceholder: string
  sendAriaLabel: string
  resetTitle: string
  resetLabel: string
  errorMessage: string
  introMessage: string
}

export interface DictSchoolSummaryLabels {
  title: string
  format: string
  goal: string
  time: string
  status: string
  statusValues: {
    consultation: string
    exploring: string
    intent_detected: string
    objection: string
    agreed_next_step: string
    not_ready: string
    contact_requested: string
    contact_collected: string
    off_topic: string
    // Legacy keys kept for fallback compatibility
    interested: string
    wantsTrialLesson: string
    contactRequested: string
    contactReceived: string
  }
  pillReady: string
  pillAwaiting: string
  pillContact: string
}

export interface DictMedicalChatLabels {
  headerTitle: string
  onlineLabel: string
  inputPlaceholder: string
  sendAriaLabel: string
  resetTitle: string
  resetLabel: string
  errorMessage: string
  introMessage: string
  quickReplies: string[]
}

export interface DictMedicalSummaryLabels {
  title: string
  specialty: string
  complaint: string
  time: string
  status: string
  statusValues: {
    new_dialog: string
    consultation: string
    exploring: string
    doctor_selection: string
    intent_detected: string
    objection: string
    agreed_next_step: string
    slots_offered: string
    awaiting_contact: string
    booking_created: string
    contact_requested: string
    contact_collected: string
    off_topic: string
    emergency: string
  }
  pillReady: string
  pillAwaiting: string
  pillContact: string
  pillEmergency: string
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
  schoolChat: DictSchoolChatLabels
  schoolSummary: DictSchoolSummaryLabels
  medicalChat: DictMedicalChatLabels
  medicalSummary: DictMedicalSummaryLabels
  scenarioSelectLabel: string
  mobileSummaryLabel: string
  conversionTitle: string
  conversionText: string
  conversionPrimary: string
  conversionSecondary: string
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

export interface DictPilotOffer {
  eyebrow: string
  title: string
  subtitle: string
  body: string
  includesTitle: string
  bullets: string[]
  cards: { label: string; title: string; text: string }[]
  pricingLine: string
  // One example, not the whole brand: how the same approach adapts to other niches.
  adaptNote: string
  ctaPrimary: string
  ctaSecondary: string
}

export interface DictPricing {
  headline: string
  subheadline: string
  note: string
  pilotOffer: DictPilotOffer
  plans: DictPricingPlan[]
}

export interface DictContact {
  headline: string
  description: string
  note: string
  highlights: string[]
  formTitle: string
  formSubtitle: string
  // Calendly primary CTA — rendered only when NEXT_PUBLIC_CALENDLY_URL is set.
  calendlyButton: string
  calendlySubtext: string
  placeholderName: string
  placeholderContact: string
  placeholderBusinessType: string
  placeholderMessage: string
  messageHelp: string
  submitButton: string
  successMessage: string
  errorMessage: string
  businessTypes: string[]
  consentText: string
  privacyLabel: string
  privacyHref: string
}

export interface DictFooter {
  tagline: string
  badges: string[]
  privacyLabel: string
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
  priceDiscovery: string
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
  // Calendly conversion CTA — rendered only when NEXT_PUBLIC_CALENDLY_URL is set.
  bookCallButton: string
  leaveContactButton: string
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
  attachAriaLabel: string
  removeFileAriaLabel: string
  fileTooBig: string
  fileTypeError: string
  fileUploadError: string
  materialsUploadedMessage: string
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
  pain: DictPain
  howItWorks: DictHowItWorks
  demo: DictDemo
  vsChatbot: DictVsChatbot
  automate: DictAutomate
  capabilities: DictCapabilities
  valueProp: DictValueProp
  whatWeNeed: DictWhatWeNeed
  trust: DictTrust
  evidence: DictEvidence
  founder: DictFounder
  faq: DictFaq
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
    { label: 'Formats', href: '#formats' },
    { label: 'Contact', href: '#contact' },
  ],
  bookACallLabel: 'Book a call',
  langSwitcher: { enLabel: 'EN', ruLabel: 'RU' },
  hero: {
    eyebrow: '',
    headlinePart1: 'An AI employee that keeps you from ',
    headlineAccent: 'losing leads',
    subheadline:
      'DamiWorks helps your business reply to customers 24/7, qualify leads, follow up, and hand warm requests to your team.',
    ctaPrimary: { label: 'Try live demo →', href: '#demo' },
    ctaSecondary: { label: 'Review my requests →', href: '#contact' },
    trustBadges: [],
    chat: {
      headerTitle: 'AI receptionist',
      onlineLabel: 'Online',
      leadLabel: 'New inquiry',
      leadFieldLabels: { service: 'Client', objection: 'Task', need: 'Handoff', time: 'Time', status: 'Status' },
      scenarios: [
        {
          id: 'outcome',
          messages: [
            { from: 'user', text: 'Can I book a consultation?', leadStateIndex: 1 },
            { from: 'ai', text: 'Of course. What would you like to automate, and what time is convenient for you?', leadStateIndex: 2 },
            { from: 'user', text: 'Instagram requests. After 5 PM works best.', leadStateIndex: 3 },
          ],
          leadStates: [
            { service: '—', objection: '—', need: '—', time: '—', status: 'New inquiry' },
            { service: 'Aliya', objection: 'Consultation', need: '—', time: '—', status: 'New message' },
            { service: 'Aliya', objection: 'Instagram requests', need: 'Telegram', time: 'After 5 PM', status: 'Warm lead' },
            { service: 'Aliya', objection: 'Instagram requests', need: 'Telegram', time: 'After 5 PM', status: 'Sent to team' },
          ],
        },
      ],
    },
  },
  pain: {
    headline: 'Where businesses lose leads',
    emphasisTitle: 'The cost of waiting',
    emphasisText:
      'Every unanswered request is not just a message. It is a potential customer who has already shown interest.',
    items: [
      'A customer writes in the evening and nobody replies.',
      'The manager is busy and answers hours later.',
      'The same questions repeat every day.',
      'No follow-up after the first reply.',
      'Requests are handed over without context.',
    ],
    bottomLine:
      'The problem is not that the team works badly. Manual request handling simply does not scale when customers expect a fast reply.',
  },
  howItWorks: {
    headline: 'How an inquiry becomes a lead',
    subheadline: 'The customer journey: from first message to a clear request for your team.',
    steps: [
      {
        number: '01',
        icon: 'MessageCircle',
        title: 'Customer writes',
        description: 'On Instagram, WhatsApp, Telegram, your website or a form.',
      },
      {
        number: '02',
        icon: 'Zap',
        title: 'AI replies instantly',
        description: 'Even in the evening, at night, or when the team is busy.',
      },
      {
        number: '03',
        icon: 'ListChecks',
        title: 'AI clarifies the need',
        description: 'Asks the right questions and collects the details.',
      },
      {
        number: '04',
        icon: 'Phone',
        title: 'AI collects contact info',
        description: 'Name, phone, messenger, or a good time to call.',
      },
      {
        number: '05',
        icon: 'ClipboardList',
        title: 'Team gets a summary',
        description: 'Who wrote, what they need, when to contact them, and the next step.',
      },
    ],
  },
  vsChatbot: {
    headline: 'This is not a regular chatbot',
    description1:
      'A chatbot answers by script. An AI employee holds a conversation.',
    description2:
      'An AI employee understands free text, asks clarifying questions, collects data, and hands your team a clear request.',
    chatbotCard: {
      title: 'Chatbot',
      items: ['Waits for buttons', 'Gets lost in free text', 'Often calls a human too early'],
    },
    aiCard: {
      title: 'AI employee',
      items: ['Understands the question', 'Clarifies details', 'Collects contact info', 'Hands off the request'],
    },
  },
  automate: {
    headline: 'What you can automate',
    actionLabel: 'What AI does',
    outcomeLabel: 'Business outcome',
    exampleLabel: 'Example',
    items: [
      { title: 'Requests', description: 'Clarifies the need, contact details, and a convenient time.', outcome: 'Managers receive a warm request, not a raw conversation.', example: 'Customer wants a consultation, prefers after 5 PM, contact via Telegram.' },
      { title: 'Answers', description: 'Replies to repeated questions about services, price, terms, schedule, delivery, or access.', outcome: 'The team spends less time on routine messages.', example: 'AI explains the program, start date, payment options, and what is included.' },
      { title: 'Follow-up', description: 'Sends a careful reminder when a customer goes silent after the first answer.', outcome: 'Warm requests do not disappear after one reply.', example: '“Would you like me to send available times for a consultation?”' },
      { title: 'Handoff', description: 'Collects the key details and sends a short summary to your team.', outcome: 'The team sees context and the next step in one place.', example: 'Name, task, channel, preferred time, and lead status.' },
      { title: 'Integrations', description: 'Connects to CRM, spreadsheets, Telegram, WhatsApp, or internal tools when needed.', outcome: 'AI works with your real process instead of creating another place your team has to check.', example: 'A qualified request goes to Telegram and Google Sheets automatically.' },
    ],
    bottomLine: 'The launch format is chosen after a short scoping call.',
  },
  whatWeNeed: {
    headline: 'What we need from you to launch',
    items: [
      { number: '01', title: 'Services and terms', description: 'What you sell, your constraints, prices, schedule, or rules.' },
      { number: '02', title: 'Common customer questions', description: 'What people usually ask before buying or booking.' },
      { number: '03', title: 'Communication channels', description: 'Where requests come from: website, Instagram, Telegram, WhatsApp.' },
      { number: '04', title: 'Where to send requests', description: 'To a manager, an administrator, a spreadsheet, or a CRM.' },
    ],
    bottomLine: "You don't need to understand AI. We handle the setup. If something is missing, we'll help collect it during scoping.",
  },
  trust: {
    headline: 'AI works within your business rules',
    description1:
      'The AI employee does not make complex decisions for a person. It answers routine questions, collects data, and hands the request to your team.',
    description2:
      'If a question is complex, sensitive, or needs a specialist, the AI hands the conversation to a human.',
    cards: [
      'No medical, legal, or financial conclusions',
      'No promises beyond the knowledge base',
      'No terms you have not confirmed',
      'Complex cases go to your team',
    ],
  },
  evidence: {
    eyebrow: 'Verifiable before you buy',
    headline: 'Do not take our promises on faith — test the workflow yourself',
    subheadline:
      'The live demo shows both sides of the process: what a customer sees and what your team receives after the conversation.',
    cards: [
      { title: 'Live conversation', text: 'Ask your own question instead of watching a pre-recorded ideal script.' },
      { title: 'Clear guardrails', text: 'Test a sensitive or complex question and see when the AI hands it to a human.' },
      { title: 'Visible outcome', text: 'Watch the request summary fill with the need, timing, contact, and next step.' },
      { title: 'Measured pilot', text: 'Agree on success criteria before launch and review real conversations together.' },
    ],
    bottomLine:
      'We do not replace evidence with invented logos or unsupported numbers. Before any contract, you can test the product, its limits, and the pilot criteria directly.',
  },
  founder: {
    eyebrow: 'Who is responsible',
    headline: 'Direct contact with the person who designs and launches the system',
    description:
      'You are not handed to an anonymous support queue. The founder reviews your workflow, defines the first scenario, and stays involved while the AI is tested on real conversations.',
    name: 'Damir',
    role: 'Founder, DamiWorks',
    personalNote:
      'I focus on one measurable workflow first, show the limits honestly, and improve the system from reviewed conversations rather than generic promises.',
    points: ['Direct communication throughout the pilot', 'A staged launch with a human handoff', 'Transparent scope and limitations', 'Post-launch conversation review'],
    cta: 'Discuss the workflow directly',
  },
  faq: {
    headline: 'Questions before a pilot',
    subheadline: 'Straight answers to the objections that usually matter before a launch.',
    items: [
      { question: 'Does the AI replace a manager?', answer: 'No. It handles repeatable first-line conversations, collects context, and hands complex or high-value cases to a person.' },
      { question: 'What if it does not know the answer?', answer: 'It is instructed not to invent terms outside the approved knowledge base. The safe path is to acknowledge the limit and hand the conversation to your team.' },
      { question: 'What do you need from us?', answer: 'Services, prices and rules, common questions, the first communication channel, and a clear destination for qualified requests.' },
      { question: 'How do we judge the pilot?', answer: 'Before launch we agree on measurable criteria such as response speed, contact collection, handoff quality, and the share of conversations that need correction.' },
      { question: 'How much does a pilot cost?', answer: 'A basic one-channel pilot starts from ₸150,000. The final scope depends on integrations, conversation complexity, and the number of workflows.' },
    ],
  },
  demo: {
    headline: 'Try the AI employee live',
    subheadline:
      'Ask a question in chat, take the short assessment, or see an example AI employee for a specific niche.',
    scenarios: [
      {
        id: 'damiworks',
        label: 'DamiWorks consultant',
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
        id: 'medical',
        label: 'Medical center',
        agentName: 'MedNova Clinic',
        messages: [
          { from: 'user', text: 'How much is a cardiologist consultation?' },
          {
            from: 'ai',
            text: 'A primary cardiologist visit is 16,000 KZT. I can also help choose a specialist or pass your contact to the administrator.',
          },
        ],
        leadSummary: {
          service: 'Medical consultation',
          need: 'Specialist selection',
          time: 'This week',
          status: 'Appointment lead',
        },
      },
      {
        id: 'english',
        label: 'English school',
        agentName: 'Alem English Academy',
        messages: [
          { from: 'user', text: 'Do you have English courses?' },
          {
            from: 'ai',
            text: 'Yes! We have groups for children, teens, and adults, offline and online. I can help find the right format.',
          },
        ],
        leadSummary: {
          service: 'English course',
          need: 'Group lessons',
          time: 'This week',
          status: 'Warm lead',
        },
      },
      {
        id: 'beauty',
        label: 'Beauty salon',
        agentName: 'Beauty salon AI',
        hidden: true,
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
    ],
    customDemoTab: {
      id: 'custom_demo',
      label: 'Your demo',
      title: 'Test an AI employee on your own business data',
      description:
        'Upload materials or describe your business, then chat as if you were a customer and see how an AI employee would answer.',
      hidden: true,
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
        packageSelected: 'Summary ready. Ask a question or leave a contact.',
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
      text: 'Describe your business or upload materials, and the AI will show how it could respond to your customers.',
      status: 'Demo uses your data',
    },
    schoolChat: {
      headerTitle: 'Alem English Academy',
      onlineLabel: 'Online',
      inputPlaceholder: 'Type a message...',
      sendAriaLabel: 'Send',
      resetTitle: 'Reset chat',
      resetLabel: 'Reset',
      errorMessage: 'Something went wrong. Please try again.',
      introMessage:
        'Hello! I\'m the Alem English Academy assistant. I can tell you about our programs, prices, schedules, and help you sign up for a trial lesson. What brings you here?',
    },
    schoolSummary: {
      title: 'Lead summary',
      format: 'Format',
      goal: 'Goal',
      time: 'Convenient time',
      status: 'Status',
      statusValues: {
        consultation:     'Consultation',
        exploring:        'Exploring options',
        intent_detected:  'Showed interest',
        objection:        'Has objection',
        agreed_next_step: 'Ready to book',
        not_ready:        'Not ready yet',
        contact_requested:'Contact requested',
        contact_collected:'Contact received',
        off_topic:        'Off-topic',
        // Legacy
        interested:       'Interested',
        wantsTrialLesson: 'Wants trial lesson',
        contactRequested: 'Contact requested',
        contactReceived:  'Contact received',
      },
      pillReady: 'Lead ready for handoff',
      pillAwaiting: 'Awaiting contact',
      pillContact: 'Contact received',
    },
    medicalChat: {
      headerTitle: 'MedNova Clinic',
      onlineLabel: 'Online',
      inputPlaceholder: 'Type a message...',
      sendAriaLabel: 'Send',
      resetTitle: 'Reset chat',
      resetLabel: 'Reset',
      errorMessage: 'Something went wrong. Please try again.',
      introMessage:
        "Hello! 💚 My name is Aigul, I'm the administrator at MedNova Clinic. I can help choose a doctor, guide you on pricing, and book your appointment. Could you tell me — is the patient an adult or a child, and what's bothering you?",
      quickReplies: [
        'Book a doctor',
        'Prices',
        'How to choose a specialist?',
        'Preparing for tests',
        'Doctor schedule',
      ],
    },
    medicalSummary: {
      title: 'Medical lead',
      specialty: 'Specialty',
      complaint: 'Complaint',
      time: 'Convenient time',
      status: 'Status',
      statusValues: {
        new_dialog: 'New conversation',
        consultation: 'Consultation',
        exploring: 'Exploring request',
        doctor_selection: 'Choosing specialist',
        intent_detected: 'Specialty detected',
        objection: 'Has objection',
        agreed_next_step: 'Ready to book',
        slots_offered: 'Slots offered',
        awaiting_contact: 'Awaiting contact',
        booking_created: 'Booking created',
        contact_requested: 'Contact requested',
        contact_collected: 'Contact received',
        off_topic: 'Off-topic',
        emergency: 'Urgent help',
      },
      pillReady: 'Lead ready for handoff',
      pillAwaiting: 'Awaiting contact',
      pillContact: 'Contact received',
      pillEmergency: 'Call 103/112',
    },
    scenarioSelectLabel: 'Choose a demo scenario',
    mobileSummaryLabel: 'What your team receives',
    conversionTitle: 'Want to test this on your own services and rules?',
    conversionText: 'We will prepare a focused pilot plan around one real workflow and show what the AI should collect before handing a request to your team.',
    conversionPrimary: 'Get a pilot plan',
    conversionSecondary: 'Ask the DamiWorks consultant',
  },
  capabilities: {
    headline: 'Where you can start',
    subheadline:
      'You do not need to build a complex system right away. We usually start with one clear scenario and expand the AI employee after the first real conversations.',
    cta: 'Not sure which format you need? Take the short assessment in the DamiWorks chat.',
    ctaLink: 'Take the assessment →',
    tiers: [
      {
        id: 'start',
        number: '01',
        name: 'Starter AI employee',
        tagline: 'To test on real conversations.',
        features: [
          { name: 'FAQ answers', description: 'Products, services, prices, delivery, booking, and terms.' },
          { name: 'Contact collection', description: 'Name, phone number, product or service of interest.' },
          { name: 'Lead handoff', description: 'To manager, WhatsApp/Telegram, or Google Sheets.' },
          { name: '1 channel', description: 'WhatsApp, Instagram, Telegram, or website.' },
        ],
        footerText: 'To quickly test an AI employee on real conversations without a complex integration.',
      },
      {
        id: 'sales',
        number: '02',
        name: 'Sales AI employee',
        tagline: 'When you need to qualify leads, not just answer.',
        features: [
          { name: 'Lead qualification', description: 'Understands who is ready to buy vs. just browsing.' },
          { name: 'Interest & need collection', description: 'Product, budget, preferred contact time.' },
          { name: 'Follow-up', description: 'Soft reminders if the customer hasn\'t replied.' },
          { name: 'Warm lead handoff', description: 'To manager, Google Sheets, or CRM with a brief summary.' },
        ],
        footerText: 'When AI should not just answer, but separate warm leads from casual questions.',
      },
      {
        id: 'integrated',
        number: '03',
        name: 'AI employee with integrations',
        tagline: 'When you need CRM, spreadsheets, statuses, routing, and business rules.',
        features: [
          { name: 'CRM/API', description: 'Integration with internal business systems.' },
          { name: 'Warehouse, orders, statuses', description: 'Stock, order stage, delivery, or other data.' },
          { name: 'Routing', description: 'Different managers, departments, or scenarios.' },
          { name: 'Custom business rules', description: 'Logic tailored to real company processes.' },
        ],
        footerText:
          'When AI needs to work not only in conversations, but also with business data, rules, and teams.',
      },
    ],
  },
  valueProp: {
    headline: 'How we implement your AI employee',
    description:
      'A platform gives you access to a tool. DamiWorks handles the implementation end to end: we analyze your process, build the knowledge base, design scenarios, connect channels, test responses, and improve the system after launch. You get a configured AI employee ready for real customer conversations, not an empty dashboard.',
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
    pilotOffer: {
      eyebrow: 'Pilot example',
      title: 'Pilot example: medical clinics and dental practices',
      subtitle: 'For medical centers, dental clinics, diagnostic labs, and private specialists.',
      body:
        'An AI administrator answers questions about doctors, services, prices, schedules, and visit preparation, helps choose the right specialist, then collects contact details and hands the appointment request to your administrator. It never diagnoses or prescribes — that stays with the doctor.',
      includesTitle: 'Where AI helps',
      bullets: [
        'AI answers first questions from patients 24/7',
        'Explains services, doctors, prices, and schedules',
        'Helps choose the right specialist by symptom or need',
        'Collects an appointment request and adult contact details',
        'Hands off a warm lead to the administrator to confirm the time',
      ],
      cards: [
        { label: 'Requests', title: 'Questions before the visit', text: 'AI explains services, doctors, prices, working hours, and how to prepare for a consultation or procedure.' },
        { label: 'Safety', title: 'No diagnosis, no prescriptions', text: 'AI routes to the right specialist and, on urgent symptoms, tells the patient to call emergency services — it never diagnoses or prescribes.' },
        { label: 'Handoff', title: 'Clear next step', text: 'AI collects the patient goal, specialty, and contact, then sends the administrator a ready appointment request.' },
      ],
      pricingLine:
        'Pilot format is selected after a short review of your process.',
      adaptNote:
        'The same approach adapts to schools, salons, courses, local services, online stores, and B2B services.',
      ctaPrimary: 'Discuss pilot',
      ctaSecondary: 'See clinic demo',
    },
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
    headline: "Let's discuss where an AI employee\ndelivers impact fastest",
    description:
      'In 20 minutes we will review your incoming requests and channels, and show which tasks to automate first.',
    note: '',
    highlights: [
      'Review your current requests and customer channels',
      'Find the first automation scenario',
      'Estimate where AI can deliver the fastest effect',
    ],
    formTitle: 'Leave a request',
    formSubtitle: "We'll message you in WhatsApp or Telegram.",
    calendlyButton: 'Book a 20-minute review',
    calendlySubtext: "Or fill in the form, and we'll message you.",
    placeholderName: 'Your name',
    placeholderContact: 'WhatsApp / Telegram',
    placeholderBusinessType: 'Select your business type',
    placeholderMessage: 'For example: Instagram requests, WhatsApp replies, booking clients, repeated questions. (optional)',
    messageHelp: "A short note is enough. We'll clarify the details ourselves.",
    submitButton: 'Send request',
    successMessage: "Thanks! We'll contact you soon.",
    errorMessage: 'Something went wrong. Please try again.',
    businessTypes: [
      'Beauty / Wellness',
      'Education / Tutoring',
      'Dental / Medical',
      'Retail / E-commerce',
      'Logistics / Delivery',
      'Real Estate',
      'Other',
    ],
    consentText: 'By sending the form, you agree that DamiWorks may use these contact details to respond to your request.',
    privacyLabel: 'Privacy notice',
    privacyHref: '/privacy',
  },
  footer: {
    tagline: 'AI employees for sales and support.',
    badges: ['Done-for-you implementation', 'Post-launch support', 'Built around your workflow'],
    privacyLabel: 'Privacy',
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
      priceDiscovery: 'Determined after a short review',
    },
    packageSelectedPattern: '✅ {pkg} selected',
    perDayLabel: '/day',
    askQuestionButton: 'Ask a question →',
    sendToOwnerButton: 'Send to Damir',
    sentConfirmation: 'Summary sent to Damir. You can ask questions below.',
    editAnswersButton: '← Edit answers',
    intakeStartMessage: "Great, I'll ask 5 short questions and find the right package.",
    intakeCompleteMessage: "Great! Here's my recommendation based on your answers:",
    errorMessage: 'Something went wrong. Please try again.',
    resetTitle: 'Reset',
    resetLabel: 'Reset',
    inputPlaceholder: 'Ask a question...',
    sendAriaLabel: 'Send',
    onlineLabel: 'Online',
    leadSentChipLabel: '✅ Sent',
    contactClosedPill: '✅ Request sent. We will contact you on WhatsApp/Telegram.',
    contactClosedInputPlaceholder: 'Request sent',
    bookCallButton: '📅 Book a call',
    leaveContactButton: '📱 Leave contact',
  },
  customDemoChat: {
    introMessage:
      "Upload business materials: a proposal, presentation, price list, catalog, FAQ, or service description. If you don't have a file, describe what you sell, your prices, terms, and common customer questions.\n\nThen ask a question as if you were a customer, and I'll show how an AI employee could respond using those materials.",
    headerTitle: 'Custom demo',
    inputPlaceholder: 'Describe your business or write a question as a customer...',
    errorMessage: 'Something went wrong. Please try again.',
    resetTitle: 'Reset',
    resetLabel: 'Reset',
    sendAriaLabel: 'Send',
    onlineLabel: 'Online',
    attachAriaLabel: 'Attach file',
    removeFileAriaLabel: 'Remove file',
    fileTooBig: 'File is too large (max 5 MB)',
    fileTypeError: 'Supported formats: .txt, .pdf, .csv, .md',
    fileUploadError: 'Could not upload the file. Please try another document.',
    materialsUploadedMessage: 'Materials uploaded. Now ask a customer question and I will answer using those materials.',
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
    title: 'AI-администратор для клиник и стоматологий — DamiWorks',
    description:
      'AI-администратор отвечает пациентам 24/7, помогает выбрать специалиста и передаёт клинике готовые заявки на запись.',
  },
  site: {
    name: 'DamiWorks',
    tagline: 'AI-сотрудники для продаж и поддержки.',
  },
  nav: [
    { label: 'Демо клиники', href: '#demo' },
    { label: 'Как работает', href: '#how-it-works' },
    { label: 'Пилот', href: '#pricing' },
    { label: 'Безопасность', href: '#trust' },
    { label: 'Контакты', href: '#contact' },
  ],
  bookACallLabel: 'Получить план пилота',
  langSwitcher: { enLabel: 'EN', ruLabel: 'RU' },
  hero: {
    eyebrow: 'Для медицинских клиник и стоматологий',
    headlinePart1: 'AI-администратор отвечает пациентам 24/7 и передаёт ',
    headlineAccent: 'готовые заявки на запись',
    subheadline:
      'Помогает выбрать специалиста, отвечает на вопросы об услугах и ценах, собирает контакт и передаёт сложные случаи человеку. Без диагнозов и назначений.',
    ctaPrimary: { label: 'Протестировать как пациент →', href: '#demo' },
    ctaSecondary: { label: 'Получить план пилота', href: '#contact' },
    trustBadges: ['Сайт и мессенджеры', 'Передача человеку', 'Настройка под ключ'],
    chat: {
      headerTitle: 'AI-администратор клиники',
      onlineLabel: 'Онлайн',
      leadLabel: 'Новая заявка',
      leadFieldLabels: { service: 'Пациент', objection: 'Направление', need: 'Передано', time: 'Время', status: 'Статус' },
      scenarios: [
        {
          id: 'outcome',
          messages: [
            { from: 'user', text: 'Хочу записаться к кардиологу на этой неделе.', leadStateIndex: 1 },
            { from: 'ai', text: 'Помогу с записью. Пациент взрослый? Есть предпочтение по дню и времени?', leadStateIndex: 2 },
            { from: 'user', text: 'Взрослый, лучше в четверг после 17:00.', leadStateIndex: 3 },
          ],
          leadStates: [
            { service: '—', objection: '—', need: '—', time: '—', status: 'Новая заявка' },
            { service: 'Взрослый', objection: 'Кардиология', need: '—', time: 'На этой неделе', status: 'Уточнение' },
            { service: 'Взрослый', objection: 'Кардиология', need: 'Администратору', time: 'Четверг после 17:00', status: 'Готов к записи' },
            { service: 'Взрослый', objection: 'Кардиология', need: 'Администратору', time: 'Четверг после 17:00', status: 'Передано клинике' },
          ],
        },
      ],
    },
  },
  pain: {
    headline: 'Где обычно теряются заявки',
    emphasisTitle: 'Цена медленного ответа',
    emphasisText:
      'Каждая неотвеченная заявка — это не просто сообщение. Это потенциальный клиент, который уже проявил интерес.',
    items: [
      'Клиент написал вечером, и никто не ответил.',
      'Менеджер занят и отвечает через несколько часов.',
      'Вопросы повторяются каждый день.',
      'После первого ответа нет follow-up.',
      'Заявка передаётся без контекста.',
    ],
    bottomLine:
      'Проблема не в том, что команда плохо работает. Проблема в том, что ручная обработка заявок не масштабируется, когда клиенты ждут быстрый ответ.',
  },
  howItWorks: {
    headline: 'Что происходит после сообщения пациента',
    subheadline: 'AI ведёт только согласованный первый этап и передаёт администратору собранный контекст.',
    steps: [
      {
        number: '01',
        icon: 'MessageCircle',
        title: 'Клиент пишет',
        description: 'На сайте или в подключённом мессенджере — в том канале, где клиника уже получает обращения.',
      },
      {
        number: '02',
        icon: 'Zap',
        title: 'AI отвечает сразу',
        description: 'Даже вечером или когда администратор занят звонком и пациентами на ресепшене.',
      },
      {
        number: '03',
        icon: 'ListChecks',
        title: 'Уточняет запрос',
        description: 'Помогает выбрать направление, отвечает по утверждённой базе и выясняет удобное время.',
      },
      {
        number: '04',
        icon: 'Phone',
        title: 'Собирает заявку',
        description: 'Контакт, направление, цель обращения и предпочтения по записи.',
      },
      {
        number: '05',
        icon: 'ClipboardList',
        title: 'Передаёт администратору',
        description: 'Сводку и следующий шаг. Сложный или чувствительный вопрос передаётся человеку раньше.',
      },
    ],
  },
  vsChatbot: {
    headline: 'Это не обычный чат-бот',
    description1:
      'Чат-бот отвечает по сценарию. AI-сотрудник ведёт диалог.',
    description2:
      'AI-сотрудник понимает свободный текст, задаёт уточняющие вопросы, собирает данные и передаёт заявку команде в понятном виде.',
    chatbotCard: {
      title: 'Чат-бот',
      items: ['Ждёт кнопок', 'Теряется в свободном тексте', 'Часто слишком рано зовёт человека'],
    },
    aiCard: {
      title: 'AI-сотрудник',
      items: ['Понимает вопрос', 'Уточняет детали', 'Собирает контакт', 'Передаёт заявку'],
    },
  },
  automate: {
    headline: 'С чего клиника может начать',
    actionLabel: 'Что делает AI',
    outcomeLabel: 'Что получает бизнес',
    exampleLabel: 'Пример',
    items: [
      { title: 'Запись', description: 'Уточняет направление, цель обращения, контакт и удобное время.', outcome: 'Администратор получает собранную заявку, а не начинает диалог заново.', example: 'Взрослый пациент, кардиолог, четверг после 17:00, контакт получен.' },
      { title: 'FAQ', description: 'Отвечает по утверждённой информации об услугах, врачах, ценах, графике и подготовке.', outcome: 'Команда меньше времени тратит на одинаковые вопросы.', example: 'Что входит в первичный приём и как подготовиться к анализам.' },
      { title: 'Подбор врача', description: 'Уточняет задачу и предлагает подходящее направление в рамках правил клиники.', outcome: 'Пациент понимает следующий шаг, не получая диагноза от AI.', example: 'Объясняет, к какому специалисту клиника рекомендует обратиться с таким запросом.' },
      { title: 'Передача', description: 'Распознаёт сложный, спорный или срочный случай и передаёт его человеку.', outcome: 'AI не продолжает разговор там, где требуется администратор или врач.', example: 'Экстренный симптом, жалоба, нестандартное условие или просьба связать с человеком.' },
      { title: 'Интеграции', description: 'Передаёт заявку в Telegram, таблицу или CRM и может учитывать доступные статусы.', outcome: 'Новый инструмент встраивается в текущую работу клиники.', example: 'Сводка по обращению автоматически уходит ответственному администратору.' },
    ],
    bottomLine: 'Формат запуска подбирается после короткого разбора задач.',
  },
  whatWeNeed: {
    headline: 'Что нужно от клиники для пилота',
    items: [
      { number: '01', title: 'Услуги, врачи и условия', description: 'Актуальные цены, график, правила записи, ограничения и подготовка к приёму.' },
      { number: '02', title: 'Частые вопросы пациентов', description: 'Что обычно спрашивают до записи и в каких случаях нужен человек.' },
      { number: '03', title: 'Один первый канал', description: 'Сайт или мессенджер, где проще всего безопасно проверить сценарий.' },
      { number: '04', title: 'Правило передачи', description: 'Кому и в каком виде отправлять заявку, сложный вопрос или срочный случай.' },
    ],
    bottomLine: 'Вам не нужно разбираться в AI. Мы берём настройку на себя. Если чего-то нет — поможем собрать в процессе разбора.',
  },
  trust: {
    headline: 'Безопасные границы задаются до запуска',
    description1:
      'AI-администратор не заменяет врача и не принимает медицинские решения. Он ведёт только согласованные организационные сценарии.',
    description2:
      'Неуверенный, сложный, спорный или срочный случай переводится на заранее определённый безопасный сценарий и передаётся человеку.',
    cards: [
      'Не даёт медицинских, юридических или финансовых заключений',
      'Не обещает то, чего нет в базе знаний',
      'Не называет условия, которые вы не подтвердили',
      'Передаёт сложные случаи команде',
    ],
  },
  evidence: {
    eyebrow: 'Можно проверить до договора',
    headline: 'Не просим верить обещаниям — покажем работу на сценариях вашей клиники',
    subheadline:
      'Живое демо показывает обе стороны процесса: что видит пациент и какую информацию после диалога получает администратор.',
    cards: [
      { title: 'Живой диалог', text: 'Задайте свой вопрос вместо просмотра заранее записанного идеального сценария.' },
      { title: 'Безопасные границы', text: 'Проверьте сложный или чувствительный вопрос и посмотрите, когда AI передаёт его человеку.' },
      { title: 'Видимый результат', text: 'Наблюдайте, как заполняется сводка: направление, цель обращения, время и статус.' },
      { title: 'Измеримый пилот', text: 'До запуска фиксируем критерии и вместе разбираем реальные диалоги без красивых неподтверждённых цифр.' },
    ],
    bottomLine:
      'Мы не подменяем доказательства вымышленными логотипами и общими цифрами. До договора вы можете проверить живое демо, ограничения и измеримые критерии будущего пилота.',
  },
  founder: {
    eyebrow: 'Кто отвечает за проект',
    headline: 'Прямой контакт с человеком, который проектирует и запускает систему',
    description:
      'Проект не передаётся анонимной линии поддержки. Основатель лично разбирает процесс клиники, определяет первый сценарий и участвует в проверке ответов после запуска.',
    name: 'Дамир',
    role: 'Основатель DamiWorks',
    personalNote:
      'Мой подход — начать с одного проверяемого сценария, честно обозначить ограничения и улучшать систему по разобранным диалогам, а не по общим обещаниям.',
    points: ['Прямое общение на протяжении пилота', 'Поэтапный запуск с передачей человеку', 'Прозрачный объём работ и ограничения', 'Разбор диалогов после запуска'],
    cta: 'Обсудить сценарий напрямую',
  },
  faq: {
    headline: 'Вопросы перед пилотом',
    subheadline: 'Прямые ответы на сомнения, которые обычно возникают до запуска.',
    items: [
      { question: 'AI заменит администратора клиники?', answer: 'Нет. Он берёт на себя повторяющийся первый этап общения, собирает контекст и передаёт администратору сложные, чувствительные и ценные обращения.' },
      { question: 'Что будет, если AI не знает ответа?', answer: 'Он не должен придумывать условия вне утверждённой базы знаний. Безопасный сценарий — обозначить ограничение и передать вопрос сотруднику клиники.' },
      { question: 'Можно ли использовать AI в медицинской тематике?', answer: 'Пилот проектируется для организационных задач: услуги, цены, график, выбор направления и сбор заявки. Диагнозы, назначения и медицинские заключения остаются за врачом.' },
      { question: 'Как понять, что пилот успешен?', answer: 'До запуска вместе фиксируем критерии: скорость первого ответа, долю собранных контактов, качество сводки, корректность передачи человеку и количество диалогов, потребовавших исправления.' },
      { question: 'Сколько стоит пилот?', answer: 'Базовый пилот на одном канале начинается от 150 000 ₸. Итоговый объём зависит от интеграций, сложности базы знаний и количества сценариев.' },
      { question: 'Что нужно подготовить клинике?', answer: 'Услуги и цены, информацию о врачах и графике, частые вопросы, правила записи и случаи, которые необходимо сразу передавать человеку.' },
    ],
  },
  demo: {
    headline: 'Проверьте AI-администратора как пациент',
    subheadline:
      'Выберите медицинский центр, задайте реальный вопрос и посмотрите, какую сводку получит администратор клиники.',
    scenarios: [
      {
        id: 'damiworks',
        label: 'DamiWorks-консультант',
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
        id: 'medical',
        label: 'Медицинский центр',
        agentName: 'MedNova Clinic',
        messages: [
          { from: 'user', text: 'Сколько стоит приём кардиолога?' },
          {
            from: 'ai',
            text: 'Первичный приём кардиолога стоит 16 000 ₸. Могу помочь выбрать специалиста или передать контакт администратору.',
          },
        ],
        leadSummary: {
          service: 'Консультация врача',
          need: 'Подбор специалиста',
          time: 'На этой неделе',
          status: 'Заявка на запись',
        },
      },
      {
        id: 'english',
        label: 'Школа английского',
        agentName: 'Alem English Academy',
        messages: [
          { from: 'user', text: 'У вас есть курсы английского?' },
          {
            from: 'ai',
            text: 'Да! Есть группы для детей, подростков и взрослых, офлайн и онлайн. Помогу подобрать подходящий формат.',
          },
        ],
        leadSummary: {
          service: 'Курс английского',
          need: 'Групповые занятия',
          time: 'На этой неделе',
          status: 'Тёплый лид',
        },
      },
      {
        id: 'beauty',
        label: 'Салон красоты',
        agentName: 'AI салона красоты',
        hidden: true,
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
    ],
    customDemoTab: {
      id: 'custom_demo',
      label: 'Своё демо',
      title: 'Протестируйте AI-сотрудника на своих данных',
      description:
        'Загрузите материалы или опишите бизнес, затем общайтесь как клиент и посмотрите, как AI ответит.',
      hidden: true,
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
        packageSelected: 'Сводка готова. Напишите вопрос или оставьте контакт.',
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
      text: 'Опишите бизнес или загрузите материалы, и AI покажет, как мог бы отвечать вашим клиентам.',
      status: 'Демо строится на ваших данных',
    },
    schoolChat: {
      headerTitle: 'Alem English Academy',
      onlineLabel: 'Онлайн',
      inputPlaceholder: 'Написать сообщение...',
      sendAriaLabel: 'Отправить',
      resetTitle: 'Сбросить чат',
      resetLabel: 'Сброс',
      errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
      introMessage:
        'Здравствуйте! Я помощник Alem English Academy. Расскажу о программах, ценах, расписании и помогу записаться на пробный урок. Чем могу помочь?',
    },
    schoolSummary: {
      title: 'Сводка по заявке',
      format: 'Формат',
      goal: 'Цель',
      time: 'Удобное время',
      status: 'Статус',
      statusValues: {
        consultation:     'Консультация',
        exploring:        'Изучает варианты',
        intent_detected:  'Проявил интерес',
        objection:        'Возражение',
        agreed_next_step: 'Готов к записи',
        not_ready:        'Пока не готов',
        contact_requested:'Контакт запрошен',
        contact_collected:'Контакт получен',
        off_topic:        'Не по теме',
        // Legacy
        interested:       'Интересуется',
        wantsTrialLesson: 'Хочет пробный урок',
        contactRequested: 'Контакт запрошен',
        contactReceived:  'Контакт получен',
      },
      pillReady: 'Заявка готова к передаче',
      pillAwaiting: 'Ожидаем контакт',
      pillContact: 'Контакт получен',
    },
    medicalChat: {
      headerTitle: 'MedNova Clinic',
      onlineLabel: 'Онлайн',
      inputPlaceholder: 'Написать сообщение...',
      sendAriaLabel: 'Отправить',
      resetTitle: 'Сбросить чат',
      resetLabel: 'Сброс',
      errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
      introMessage:
        'Здравствуйте! 💚 Меня зовут Айгуль, я администратор MedNova Clinic. Помогу подобрать врача, сориентировать по стоимости и записать на приём. Подскажите, пожалуйста, пациент взрослый или ребёнок, и что вас беспокоит?',
      quickReplies: [
        'Записаться к врачу',
        'Цены',
        'Как выбрать специалиста?',
        'Подготовка к анализам',
        'График врачей',
      ],
    },
    medicalSummary: {
      title: 'Сводка по заявке',
      specialty: 'Направление',
      complaint: 'Жалоба',
      time: 'Удобное время',
      status: 'Статус',
      statusValues: {
        new_dialog: 'Новый диалог',
        consultation: 'Консультация',
        exploring: 'Уточняет запрос',
        doctor_selection: 'Подбор врача',
        intent_detected: 'Направление определено',
        objection: 'Возражение',
        agreed_next_step: 'Готов к записи',
        slots_offered: 'Предложены окна',
        awaiting_contact: 'Ожидает контакт',
        booking_created: 'Запись создана',
        contact_requested: 'Контакт запрошен',
        contact_collected: 'Контакт получен',
        off_topic: 'Не по теме',
        emergency: 'Срочная помощь',
      },
      pillReady: 'Заявка готова к передаче',
      pillAwaiting: 'Ожидаем контакт',
      pillContact: 'Контакт получен',
      pillEmergency: 'Позвоните 103/112',
    },
    scenarioSelectLabel: 'Выберите сценарий демо',
    mobileSummaryLabel: 'Что получит администратор',
    conversionTitle: 'Хотите проверить этот сценарий на услугах вашей клиники?',
    conversionText: 'Подготовим план пилота для одного реального потока обращений и покажем, что AI должен собрать перед передачей администратору.',
    conversionPrimary: 'Получить план пилота',
    conversionSecondary: 'Задать вопрос DamiWorks',
  },
  capabilities: {
    headline: 'С чего можно начать',
    subheadline:
      'Не нужно сразу строить сложную систему. Обычно мы начинаем с одного понятного сценария и расширяем AI-сотрудника после первых реальных диалогов.',
    cta: 'Не знаете, какой формат нужен? Пройдите короткий подбор в DamiWorks-чате.',
    ctaLink: 'Пройти подбор →',
    tiers: [
      {
        id: 'start',
        number: '01',
        name: 'Стартовый AI-сотрудник',
        tagline: 'Для проверки на реальных диалогах.',
        features: [
          { name: 'Ответы на частые вопросы', description: 'Товары, услуги, цены, доставка, запись и условия.' },
          { name: 'Сбор контакта', description: 'Имя, телефон, интересующий товар или услуга.' },
          { name: 'Передача заявки', description: 'Менеджеру, в WhatsApp/Telegram или Google Sheets.' },
          { name: '1 канал', description: 'WhatsApp, Instagram, Telegram или сайт.' },
        ],
        footerText: 'Чтобы быстро проверить AI-сотрудника на реальных диалогах без сложной интеграции.',
      },
      {
        id: 'sales',
        number: '02',
        name: 'AI-сотрудник для продаж',
        tagline: 'Когда нужно не только отвечать, но и квалифицировать лидов.',
        features: [
          { name: 'Квалификация лидов', description: 'Понимает, кто готов купить, а кто просто спрашивает.' },
          { name: 'Сбор интереса и потребности', description: 'Товар, бюджет, потребность и удобное время связи.' },
          { name: 'Follow-up', description: 'Мягкие напоминания, если клиент не ответил.' },
          { name: 'Передача тёплых заявок', description: 'Менеджеру, в Google Sheets или CRM с краткой сводкой.' },
        ],
        footerText: 'Когда AI должен не просто отвечать, а отличать тёплых клиентов от тех, кто пока просто интересуется.',
      },
      {
        id: 'integrated',
        number: '03',
        name: 'AI-сотрудник с интеграциями',
        tagline: 'Когда нужно подключить CRM, таблицы, статусы, маршрутизацию и бизнес-правила.',
        features: [
          { name: 'CRM/API', description: 'Подключение к внутренним системам бизнеса.' },
          { name: 'Склад, заказы, статусы', description: 'Наличие, этап заказа, доставка или другие данные.' },
          { name: 'Маршрутизация', description: 'Разные менеджеры, отделы или сценарии.' },
          { name: 'Индивидуальные бизнес-правила', description: 'Правила под реальные процессы компании.' },
        ],
        footerText:
          'Когда AI должен работать не только в переписке, но и с данными, правилами и командами внутри бизнеса.',
      },
    ],
  },
  valueProp: {
    headline: 'Как проходит пилот',
    description:
      'Клиника получает не пустой кабинет и не шаблонного бота. DamiWorks разбирает один процесс, собирает утверждённую базу знаний, задаёт границы, подключает передачу человеку и проверяет ответы на реальных диалогах.',
    items: [
      {
        number: '01',
        title: 'Фиксируем сценарий и критерии',
        description:
          'Определяем, какие вопросы обрабатывает AI, какие данные собирает, когда зовёт человека и по каким показателям оцениваем пилот.',
      },
      {
        number: '02',
        title: 'Настраиваем и безопасно запускаем',
        description:
          'Собираем базу знаний, тестируем типовые и сложные вопросы, подключаем канал и передачу заявки ответственному сотруднику.',
      },
      {
        number: '03',
        title: 'Разбираем реальные диалоги',
        description:
          'Находим слабые ответы, уточняем правила и показываем, где система справляется, а где процесс нужно оставить человеку.',
      },
    ],
  },
  pricing: {
    headline: 'Простые цены. Без скрытых платежей.',
    subheadline:
      'Прозрачные пакеты под разные задачи: от первого запуска до квалификации лидов, интеграций и сложных сценариев.',
    note: 'Итоговая стоимость зависит от объёма и сложности проекта.',
    pilotOffer: {
      eyebrow: 'Пилот без большого внедрения',
      title: 'Начните с одного сценария, который можно измерить на реальных обращениях',
      subtitle:
        'Для медицинских центров, стоматологий, лабораторий и частных специалистов.',
      body:
        'Не нужно автоматизировать всю клинику сразу. Выбираем один поток обращений — например, вопросы до приёма и сбор заявки на запись — настраиваем безопасные границы, передачу администратору и критерии проверки.',
      includesTitle: 'Где помогает AI',
      bullets: [
        'AI отвечает на первые вопросы пациентов 24/7',
        'Объясняет услуги, врачей, цены и расписание',
        'Помогает выбрать специалиста по жалобе или задаче',
        'Собирает заявку на запись и контакт взрослого',
        'Передаёт тёплую заявку администратору для подтверждения времени',
      ],
      cards: [
        { label: 'Объём', title: 'Один канал и сценарий', text: 'Фокусируем пилот на одном понятном процессе, чтобы быстро увидеть реальные слабые и сильные стороны.' },
        { label: 'Результат', title: 'Рабочий AI и передача заявки', text: 'Настроенная база знаний, правила ответа, сбор контакта и сводка для администратора.' },
        { label: 'Контроль', title: 'Месяц первых улучшений', text: 'Разбираем реальные диалоги, исправляем слабые ответы и уточняем правила после запуска.' },
      ],
      pricingLine:
        'Базовый пилот — от 150 000 ₸. Точный объём фиксируем до старта после короткого разбора процесса.',
      adaptNote:
        'По такому же принципу AI-сотрудника можно адаптировать под школы, салоны, курсы, локальные услуги, онлайн-магазины и B2B-сервисы.',
      ctaPrimary: 'Получить план пилота',
      ctaSecondary: 'Протестировать демо',
    },
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
    headline: 'Получите план первого\nпилота для клиники',
    description:
      'За 20 минут разберём один поток обращений и определим, что AI сможет делать, где передавать диалог человеку и как проверить результат.',
    note: '',
    highlights: [
      'выберем один безопасный сценарий для старта',
      'зафиксируем данные и правила передачи человеку',
      'дадим понятный объём и стоимость пилота',
    ],
    formTitle: 'Получить план пилота',
    formSubtitle: 'Мы напишем вам в WhatsApp или Telegram.',
    calendlyButton: 'Забронировать 20-минутный разбор',
    calendlySubtext: 'Или заполните форму, и мы напишем вам сами.',
    placeholderName: 'Ваше имя',
    placeholderContact: 'WhatsApp / Telegram',
    placeholderBusinessType: 'Тип клиники или бизнеса',
    placeholderMessage: 'Например: стоматология, обращения с сайта и WhatsApp, вопросы о ценах и запись к врачу. (необязательно)',
    messageHelp: 'Можно коротко — мы уточним детали сами.',
    submitButton: 'Отправить заявку',
    successMessage: 'Спасибо! Скоро свяжемся с вами.',
    errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
    businessTypes: [
      'Стоматология',
      'Медицинская клиника',
      'Диагностическая лаборатория',
      'Частный специалист',
      'Красота / Оздоровление',
      'Образование / Репетиторство',
      'Розница / Интернет-магазин',
      'Логистика / Доставка',
      'Недвижимость',
      'Другое',
    ],
    consentText: 'Отправляя форму, вы соглашаетесь на использование контактных данных только для ответа на эту заявку.',
    privacyLabel: 'Уведомление о конфиденциальности',
    privacyHref: '/ru/privacy',
  },
  footer: {
    tagline: 'AI-администраторы для клиник и сервисного бизнеса.',
    badges: [
      'Внедрение под ключ',
      'Сопровождение после запуска',
      'Под задачи бизнеса',
    ],
    privacyLabel: 'Конфиденциальность',
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
      priceDiscovery: 'Обсуждается после разбора задач',
    },
    packageSelectedPattern: '✅ {pkg} подобран',
    perDayLabel: '/день',
    askQuestionButton: 'Задать вопрос →',
    sendToOwnerButton: 'Отправить Дамиру',
    sentConfirmation: 'Сводка отправлена команде. Можно задать вопрос ниже.',
    editAnswersButton: '← Изменить ответы',
    intakeStartMessage: 'Отлично, задам 5 коротких вопросов и подберу подходящий пакет.',
    intakeCompleteMessage: 'Отлично! Вот что рекомендую на основе ваших ответов:',
    errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
    resetTitle: 'Сбросить',
    resetLabel: 'Сброс',
    inputPlaceholder: 'Задайте вопрос...',
    sendAriaLabel: 'Отправить',
    onlineLabel: 'Онлайн',
    leadSentChipLabel: '✅ Отправлено',
    contactClosedPill: '✅ Заявка отправлена. Мы свяжемся с вами в WhatsApp/Telegram.',
    contactClosedInputPlaceholder: 'Заявка отправлена',
    bookCallButton: '📅 Забронировать звонок',
    leaveContactButton: '📱 Оставить контакт',
  },
  customDemoChat: {
    introMessage:
      'Загрузите материалы о бизнесе: КП, презентацию, прайс, каталог, FAQ или описание услуг. Если файла нет, опишите, что продаёте, цены, условия и частые вопросы клиентов.\n\nЗатем напишите вопрос как будто вы клиент, и я покажу, как AI-сотрудник ответит на основе этих материалов.',
    headerTitle: 'Custom demo',
    inputPlaceholder: 'Опишите бизнес или напишите вопрос как клиент...',
    errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
    resetTitle: 'Сбросить',
    resetLabel: 'Сброс',
    sendAriaLabel: 'Отправить',
    onlineLabel: 'Онлайн',
    attachAriaLabel: 'Прикрепить файл',
    removeFileAriaLabel: 'Убрать файл',
    fileTooBig: 'Файл слишком большой (макс. 5 МБ)',
    fileTypeError: 'Поддерживаемые форматы: .txt, .pdf, .csv, .md',
    fileUploadError: 'Не удалось загрузить файл. Попробуйте другой документ.',
    materialsUploadedMessage: 'Материалы загружены. Теперь задайте вопрос как клиент, и я отвечу с учетом этих материалов.',
  },
  intake: {
    questions: [
      {
        id: 'channels',
        text: 'Где вам пишут клиенты? Можно выбрать несколько.',
        options: ['WhatsApp', 'Instagram', 'Telegram', 'Сайт', 'Другое'],
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
