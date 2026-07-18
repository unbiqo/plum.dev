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
  // WhatsApp CTA — rendered only when NEXT_PUBLIC_WHATSAPP_URL is set.
  whatsappCta: string
  trustBadges: string[]
  chat: DictHeroChat
}

// Test-first hero: the live medical demo IS the hero surface. The visitor
// writes as a patient and immediately sees the admin-ready заявка forming.
export interface DictHeroTest {
  headlinePart1: string
  headlineAccent: string
  subheadline: string
  // Mobile-only headline/subheadline override — falls back to the desktop
  // headlinePart1/headlineAccent/subheadline when omitted. Headline is split
  // the same way as the desktop one so the tail can be accented.
  mobileHeadlinePart1?: string
  mobileHeadlineAccent?: string
  mobileSubheadline?: string
  scenarioNote: string
  summaryLabel: string
  ctaSecondary: { label: string; href: string }
  liveHint: string
  // Floating context chips around the test surface (desktop only, decorative).
  chips: string[]
}

// Compact one-row strip right under the hero test: what just happened.
export interface DictBackstage {
  title: string
  steps: string[]
}

// Light, CTA-first hero: one claim, one button into the demo workspace
// (/ru/demo — intake mock -> patient test chat -> launch-plan assistant).
export interface DictHeroDemo {
  headlineLine1: string
  headlineLine2: string
  subheadline: string
  ctaLabel: string
}

export interface DictAssistantQuestion {
  // Short progress label, e.g. «Каналы».
  step: string
  question: string
  why: string
  options: string[]
  multi: boolean
}

// The /ru/demo workspace: intake mock -> patient test chat -> launch
// assistant questionnaire -> plan draft.
export interface DictDemoWorkspace {
  headerCta: string
  intake: {
    eyebrow: string
    title: string
    demoNote: string
    siteLabel: string
    fallbackClinic: string
    foundTitle: string
    foundItems: string[]
    clarifyTitle: string
    clarifyItems: string[]
  }
  test: {
    eyebrow: string
    title: string
    subtitle: string
    summaryLabel: string
  }
  assistant: {
    eyebrow: string
    title: string
    subtitle: string
    whyLabel: string
    questions: DictAssistantQuestion[]
    planStepLabel: string
    backLabel: string
    nextLabel: string
    finishLabel: string
  }
  plan: {
    title: string
    subtitle: string
    blockChannels: string
    blockKnowledge: string
    blockScenarios: string
    blockHandoff: string
    blockLead: string
    leadFieldsNote: string
    emptyValue: string
    priceLine: string
    priceNote: string
    ctaPrimary: string
    ctaWhatsapp: string
    restartLabel: string
  }
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

// «Один вопрос пациента — два разных процесса» — the message-to-lead contrast.
// Sells structuring the first contact, not "AI is better than a human".
export interface DictMessageToLead {
  headline: string
  subheadline: string
  before: {
    title: string
    patientMessage: string
    problemsTitle: string
    problems: string[]
  }
  after: {
    title: string
    fields: { label: string; value: string }[]
    nextStepLabel: string
    nextStep: string
  }
}

// Тёмная секция «Администратор получает не переписку, а готовую заявку».
export interface DictAdminHandoff {
  eyebrow: string
  headline: string
  subheadline: string
  points: string[]
  card: {
    title: string
    fields: { label: string; value: string }[]
    pill: string
    nextStepLabel: string
    nextStep: string
  }
}

// «Запуск под ключ» — merged launch section:
// steps + what we track + what we need + price + CTA.
export interface DictLaunch {
  headline: string
  subheadline: string
  steps: { number: string; title: string; description: string }[]
  measuresTitle: string
  measures: string[]
  needTitle: string
  needItems: string[]
  pricingLine: string
  priceNote: string
  ctaPrimary: string
  ctaSecondary: string
}

// «Что входит в запуск AI-администратора» — the 3-zone systems diagram:
// incoming channels → the AI core (dominant) → the ready request handoff.
export interface DictLaunchKit {
  headline: string
  subheadline: string
  channels: { title: string; items: string[] }
  core: { title: string; layers: { title: string; text: string }[] }
  handoff: { title: string; items: string[] }
}

// «AI знает, где отвечать, а где передать человеку» — the decision flow.
// Exactly 3 states, colored by the component: answers (green), clarifies
// (amber), hands off (brand accent — a feature, not a fail state).
export interface DictSafetyFlow {
  headline: string
  subheadline: string
  guarantees: string[]
  states: { title: string; description: string; note?: string }[]
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
  // Shorter first AI message shown on mobile — falls back to introMessage.
  mobileIntroMessage?: string
  quickReplies: string[]
  // Staged loading lines shown while the backend thinks — sells the process.
  // Falls back to plain typing dots when omitted.
  loadingStages?: string[]
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
  // Short proof bullets under the headline (former Evidence section, condensed).
  proofPoints?: string[]
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
  // WhatsApp CTA — rendered only when NEXT_PUBLIC_WHATSAPP_URL is set.
  whatsappButton: string
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
  // Ghost demo link in the minimal (no-menu) header variant.
  headerDemoLabel: string
  langSwitcher: DictLangSwitcher
  hero: DictHero
  heroTest: DictHeroTest
  heroDemo: DictHeroDemo
  backstage: DictBackstage
  demoWorkspace: DictDemoWorkspace
  pain: DictPain
  howItWorks: DictHowItWorks
  demo: DictDemo
  vsChatbot: DictVsChatbot
  automate: DictAutomate
  capabilities: DictCapabilities
  valueProp: DictValueProp
  whatWeNeed: DictWhatWeNeed
  trust: DictTrust
  messageToLead: DictMessageToLead
  adminHandoff: DictAdminHandoff
  launch: DictLaunch
  launchKit: DictLaunchKit
  safetyFlow: DictSafetyFlow
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
    title: 'DamiWorks | AI Employees for Sales and Support',
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
  headerDemoLabel: 'Try the demo',
  langSwitcher: { enLabel: 'EN', ruLabel: 'RU' },
  hero: {
    eyebrow: '',
    headlinePart1: 'An AI employee that keeps you from ',
    headlineAccent: 'losing leads',
    subheadline:
      'DamiWorks helps your business reply to customers 24/7, qualify leads, follow up, and hand warm requests to your team.',
    ctaPrimary: { label: 'Try live demo →', href: '#demo' },
    ctaSecondary: { label: 'Review my requests →', href: '#contact' },
    whatsappCta: 'Message us on WhatsApp',
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
  // Rendered on the RU page only for now — EN values keep the Dict type complete.
  heroTest: {
    headlinePart1: 'Write as a patient. ',
    headlineAccent: 'See what the administrator gets.',
    subheadline:
      'DamiWorks answers patients on WhatsApp, Instagram and your website, clarifies the request and builds a ready-made заявка for your team. Only a doctor diagnoses.',
    scenarioNote: 'Example: MedNova multi-specialty clinic',
    summaryLabel: 'What the administrator gets',
    ctaSecondary: { label: 'Discuss a launch', href: '#contact' },
    liveHint: 'A live AI, not a recording — ask anything',
    chips: ['WhatsApp', 'Instagram', 'Website', 'Telegram', 'CRM', 'Request ready'],
  },
  backstage: {
    title: 'What just happened behind the scenes',
    steps: ['Patient writes', 'AI clarifies the details', 'Request assembled', 'Complex cases go to a human'],
  },
  heroDemo: {
    headlineLine1: 'See how AI runs the conversation.',
    headlineLine2: 'Try the live demo yourself.',
    subheadline:
      'See how AI takes over the first conversation: answers the patient, clarifies details and helps turn the inquiry into a clear request.',
    ctaLabel: 'Try the demo',
  },
  demoWorkspace: {
    headerCta: 'Discuss a launch',
    intake: {
      eyebrow: '01',
      title: 'What we understood about the clinic',
      demoNote: 'Demo mode: the structure is shown on a typical medical scenario. A draft for your site is assembled on a short call.',
      siteLabel: 'Website',
      fallbackClinic: 'MedNova sample clinic',
      foundTitle: 'What goes into the knowledge base',
      foundItems: ['Services and specialties', 'Contacts and address', 'Working hours', 'Doctors and specializations'],
      clarifyTitle: 'What we will clarify with you',
      clarifyItems: ['Service prices', 'Human-handoff rules', 'Request format for the administrator'],
    },
    test: {
      eyebrow: '02',
      title: 'Try it as a patient',
      subtitle: 'A live AI on a typical clinic base: ask a question and watch the request assemble.',
      summaryLabel: 'Live request summary',
    },
    assistant: {
      eyebrow: '03',
      title: 'Build a launch plan',
      subtitle: 'Five short questions — and we will show a draft launch plan for your clinic.',
      whyLabel: 'Why this matters',
      questions: [
        {
          step: 'Channels',
          question: 'Where do patients write to you most often?',
          why: 'The AI plugs into the channels where inquiries already flow — patients keep their habits.',
          options: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Phone calls'],
          multi: true,
        },
        {
          step: 'Base',
          question: 'Which questions repeat most often?',
          why: 'This becomes the knowledge base: the AI answers these itself, with no waiting.',
          options: ['Prices and services', 'Doctors’ schedule', 'Preparation for tests', 'Choosing a doctor', 'Address and directions'],
          multi: true,
        },
        {
          step: 'Scenarios',
          question: 'What can the AI answer on its own?',
          why: 'This defines the first-answer scenarios and where the assistant saves the most time.',
          options: ['Prices and services', 'Booking', 'Schedule and open slots', 'Procedure preparation'],
          multi: true,
        },
        {
          step: 'Boundaries',
          question: 'When must the AI hand the dialog to a human?',
          why: 'Safety rules: the AI does not play doctor. Clear boundaries are what separate an assistant from a “bot”.',
          options: ['Medical questions', 'Complaints and disputes', 'Urgent cases', 'Non-standard requests'],
          multi: true,
        },
        {
          step: 'Request',
          question: 'Where should the ready request go?',
          why: 'The request must land where your team already works — otherwise it gets lost.',
          options: ['Administrator’s WhatsApp or Telegram', 'Spreadsheet (Google Sheets)', 'Clinic CRM', 'Email'],
          multi: false,
        },
      ],
      planStepLabel: 'Plan',
      backLabel: 'Back',
      nextLabel: 'Next',
      finishLabel: 'Show the plan',
    },
    plan: {
      title: 'Draft launch of your AI receptionist',
      subtitle: 'Assembled from your answers. A starting point — details are refined on a short call.',
      blockChannels: 'Channels',
      blockKnowledge: 'Knowledge base',
      blockScenarios: 'AI answers itself',
      blockHandoff: 'Hands off to a human',
      blockLead: 'Request',
      leadFieldsNote: 'In the request: contact, specialty, goal of the inquiry, preferred time.',
      emptyValue: 'To clarify on the call',
      priceLine: 'A turnkey AI receptionist — from 150,000 ₸.',
      priceNote: 'The base launch includes clinic-specific setup, a knowledge base, answer scenarios and human-handoff rules.',
      ctaPrimary: 'Discuss a launch',
      ctaWhatsapp: 'Send the plan to WhatsApp',
      restartLabel: 'Start over',
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
  // Rendered on the RU page only for now — EN values keep the Dict type complete.
  messageToLead: {
    headline: 'One customer question — two different processes',
    subheadline:
      'On the left: a message your team has to untangle manually. On the right: what they get after a DamiWorks dialog.',
    before: {
      title: 'A typical incoming message',
      patientMessage: 'Hi, how much does an implant cost?',
      problemsTitle: 'The team has to find out manually:',
      problems: [
        'First consultation or an existing treatment plan?',
        'When is the customer available?',
        'How to reach them?',
        'How urgent is it?',
      ],
    },
    after: {
      title: 'After a DamiWorks dialog',
      fields: [
        { label: 'Service', value: 'Implant' },
        { label: 'Goal', value: 'Get a price and book' },
        { label: 'Time', value: 'This week' },
        { label: 'Contact', value: 'Collected' },
      ],
      nextStepLabel: 'Next step',
      nextStep: 'Offer consultation slots',
    },
  },
  adminHandoff: {
    eyebrow: 'The outcome of every dialog',
    headline: 'Your team gets a ready request, not a raw conversation',
    subheadline:
      'Every dialog turns into a short summary: who is writing, what they need, when it is convenient, and what to do next.',
    points: [
      'No need to re-read the conversation',
      'You see who the AI handed to a human, and why',
      'The request lands where you already work: Telegram, a spreadsheet, or your CRM',
    ],
    card: {
      title: 'New request',
      fields: [
        { label: 'Category', value: 'Dentistry' },
        { label: 'Request', value: 'Tooth pain, wants a consultation' },
        { label: 'Preferred time', value: 'Today after 5 PM' },
        { label: 'Contact', value: '+7 707 ••• •• 44' },
        { label: 'Status', value: 'Contact collected' },
      ],
      pill: 'Ready for handoff',
      nextStepLabel: 'Next step for the team',
      nextStep: 'Offer slots today after 5 PM and confirm the booking',
    },
  },
  launch: {
    headline: 'A turnkey launch: from knowledge base to ready requests',
    subheadline:
      'We set it up, launch it, and improve it with you — based on real conversations, not gut feeling.',
    steps: [
      {
        number: '01',
        title: 'We study your process',
        description: 'What inquiries come in, what the AI takes over, where the boundaries are, and who receives the requests.',
      },
      {
        number: '02',
        title: 'We set up and launch',
        description: 'The technical part is on us: knowledge base, answer scenarios, safety rules, and request handoff to your team.',
      },
      {
        number: '03',
        title: 'We improve on real conversations',
        description: 'We review the dialogs, fix weak answers, and decide together what to expand next.',
      },
    ],
    measuresTitle: 'What we track after launch',
    measures: [
      'How many inquiries the AI handled',
      'How many contacts it collected',
      'How many requests it handed to the team',
      'Where it handed off to a human',
      'Which questions repeat most often',
    ],
    needTitle: 'All we need from you',
    needItems: ['Services and prices', 'Common customer questions', 'Booking rules', 'Where to send requests'],
    pricingLine: 'A turnkey AI receptionist — from 150,000 ₸.',
    priceNote:
      'The base launch includes clinic-specific setup, a knowledge base, answer scenarios, human-handoff rules, and the request format for your team. Extra integrations and complex channels are scoped separately.',
    ctaPrimary: 'Discuss a launch',
    ctaSecondary: 'Try the demo first',
  },
  launchKit: {
    headline: 'What a launch includes',
    subheadline:
      'We do not hand you an empty bot. We configure the system for your services, channels, and rules — and deliver requests where your team already works.',
    channels: { title: 'Incoming channels', items: ['WhatsApp', 'Instagram', 'Website'] },
    core: {
      title: 'AI receptionist',
      layers: [
        { title: 'Clinic knowledge base', text: 'Services, prices, schedule, preparation, booking rules.' },
        { title: 'Conversation scenarios', text: 'Bookings, price questions, specialty routing, FAQs.' },
        { title: 'Safety rules', text: 'Where it answers, where it clarifies, where it hands off to a human.' },
      ],
    },
    handoff: { title: 'Ready request for the team', items: ['WhatsApp / Telegram', 'Spreadsheet', 'CRM'] },
  },
  safetyFlow: {
    headline: 'The AI knows where to answer — and where to hand off',
    subheadline:
      'It does not diagnose and does not play doctor. Its job is to take the first message, clarify the organizational details, and pass the dialog to your team in time.',
    guarantees: ['No diagnoses', 'No treatment advice', 'No made-up prices'],
    states: [
      { title: 'Answers on its own', description: 'Organizational questions: prices, schedule, preparation, bookings, services.' },
      { title: 'Clarifies by the rules', description: 'Collects context: specialty, the goal of the inquiry, preferred time, contact.' },
      {
        title: 'Hands off to a human',
        description: 'When a question is medical, urgent, contested, or outside the knowledge base.',
        note: 'On alarming symptoms it does not continue the dialog — it points to urgent care and a human.',
      },
    ],
  },
  evidence: {
    eyebrow: 'Verifiable before you buy',
    headline: 'Do not take my word for it. Test the workflow yourself',
    subheadline:
      'The live demo shows both sides of the process: what a customer sees and what your team receives after the conversation.',
    cards: [
      { title: 'Live conversation', text: 'Ask your own question instead of watching a pre-recorded ideal script.' },
      { title: 'Clear guardrails', text: 'Test a sensitive or complex question and see when the AI hands it to a human.' },
      { title: 'Visible outcome', text: 'Watch the request summary fill with the need, timing, contact, and next step.' },
      { title: 'Measured pilot', text: 'Agree on success criteria before launch and review real conversations together.' },
    ],
    bottomLine:
      'I do not replace evidence with invented logos or unsupported numbers. Before any contract, you can test the product, its limits, and the pilot criteria directly.',
  },
  founder: {
    eyebrow: 'Who is responsible',
    headline: 'You work with me directly',
    description:
      'I review your workflow, define the first scenario, and stay involved while we test the AI on real conversations. Your project never disappears into an anonymous support queue.',
    name: 'Damir',
    role: 'Founder, DamiWorks',
    personalNote:
      'I start with one measurable workflow. I explain the limits clearly. After launch, I improve the system through reviewed conversations.',
    points: ['You speak with me throughout the pilot', 'I launch in stages and keep a human handoff', 'I define scope and limits in advance', 'I review conversations after launch'],
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
        "Hello! 💚 My name is Aigul, and I'm the administrator at MedNova Clinic. I can help choose a doctor, explain pricing, and book an appointment. Is the patient an adult or a child? What is bothering you?",
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
      'A platform gives you access to a tool. We handle the implementation. We analyze your process, build the knowledge base, connect channels, and test responses. You receive an AI employee configured for real customer conversations.',
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
        'An AI administrator answers questions about doctors, services, prices, schedules, and visit preparation. It helps choose the right specialist and collects contact details. Diagnoses and prescriptions stay with the doctor.',
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
        { label: 'Safety', title: 'No diagnosis, no prescriptions', text: 'AI routes to the right specialist. For urgent symptoms, it tells the patient to call emergency services. It never diagnoses or prescribes.' },
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
    whatsappButton: 'Message us on WhatsApp',
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
    title: 'AI-администратор для клиник: отвечает пациентам и записывает 24/7 | DamiWorks',
    description:
      'Умный помощник отвечает пациентам круглосуточно, помогает выбрать врача и передаёт клинике готовую заявку на запись. Диагнозы ставит только врач.',
  },
  site: {
    name: 'DamiWorks',
    tagline: 'Умный помощник, который отвечает пациентам и записывает на приём.',
  },
  nav: [
    { label: 'Попробовать', href: '#demo' },
    { label: 'Как это работает', href: '#how-it-works' },
    { label: 'Сколько стоит', href: '#pricing' },
    { label: 'Безопасность', href: '#trust' },
    { label: 'Контакты', href: '#contact' },
  ],
  bookACallLabel: 'Обсудить запуск',
  headerDemoLabel: 'Попробовать демо',
  langSwitcher: { enLabel: 'EN', ruLabel: 'RU' },
  hero: {
    eyebrow: 'Для клиник, стоматологий и медицинских центров',
    headlinePart1: 'Входящие заявки теряются ',
    headlineAccent: 'после первого сообщения',
    subheadline:
      'DamiWorks отвечает пациентам в WhatsApp, Instagram и на сайте, уточняет запрос, собирает контакт и передаёт администратору готовую заявку. Диагнозы ставит только врач.',
    ctaPrimary: { label: 'Попробовать как пациент →', href: '#demo' },
    ctaSecondary: { label: 'Получить план запуска', href: '#contact' },
    whatsappCta: 'Написать в WhatsApp',
    trustBadges: ['WhatsApp / Instagram / сайт', 'Сложные случаи — живому человеку', 'Запуск под ключ'],
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
  heroTest: {
    headlinePart1: 'Побудьте пациентом. ',
    headlineAccent: 'Посмотрите, как AI ведёт диалог.',
    subheadline:
      'DamiWorks отвечает пациентам в WhatsApp, Instagram и на сайте, уточняет запрос и собирает готовую заявку для вашей команды.',
    mobileHeadlinePart1: 'Не теряйте пациента ',
    mobileHeadlineAccent: 'после первого сообщения',
    mobileSubheadline:
      'Проверьте, как AI ведёт первый диалог с пациентом и собирает заявку для администратора.',
    scenarioNote: 'Пример: многопрофильная клиника MedNova',
    summaryLabel: 'Live-сводка по диалогу',
    ctaSecondary: { label: 'Обсудить запуск', href: '#contact' },
    liveHint: 'Не отличить от человека — попробуйте сами',
    chips: ['WhatsApp', 'Instagram', 'Сайт', 'Telegram', 'CRM', 'Заявка готова'],
  },
  backstage: {
    title: 'Что произошло за кулисами',
    steps: ['Пациент пишет', 'AI уточняет детали и помогает клиенту принять решение', 'Заявка собрана', 'Передаёт или сам оформляет'],
  },
  heroDemo: {
    headlineLine1: 'Посмотрите, как AI ведёт диалог.',
    headlineLine2: 'Попробуйте демо прямо сейчас.',
    subheadline:
      'Проверьте, как AI берёт первый диалог на себя: отвечает пациенту, уточняет детали и помогает довести обращение до понятной заявки.',
    ctaLabel: 'Пройти демо',
  },
  demoWorkspace: {
    headerCta: 'Обсудить запуск',
    intake: {
      eyebrow: '01',
      title: 'Что мы поняли о клинике',
      demoNote: 'Демо-режим: структура показана на типовом медицинском сценарии. Черновик по вашему сайту соберём на коротком разборе.',
      siteLabel: 'Сайт',
      fallbackClinic: 'Типовая клиника MedNova',
      foundTitle: 'Что войдёт в базу знаний',
      foundItems: ['Услуги и направления', 'Контакты и адрес', 'График работы', 'Врачи и специализации'],
      clarifyTitle: 'Что уточним у вас',
      clarifyItems: ['Цены на услуги', 'Правила передачи человеку', 'Формат заявки для администратора'],
    },
    test: {
      eyebrow: '02',
      title: 'Проверьте как пациент',
      subtitle: 'Живой AI на типовой базе клиники: задайте вопрос — и посмотрите, как собирается заявка.',
      summaryLabel: 'Живая сводка заявки',
    },
    assistant: {
      eyebrow: '03',
      title: 'Соберите план запуска',
      subtitle: 'Пять коротких вопросов — и покажем черновик запуска AI-администратора для вашей клиники.',
      whyLabel: 'Почему это важно',
      questions: [
        {
          step: 'Каналы',
          question: 'Куда пациенты чаще всего пишут вам?',
          why: 'AI подключается туда, где обращения уже идут, — пациентам не нужно менять привычки.',
          options: ['WhatsApp', 'Instagram', 'Telegram', 'Сайт', 'Звонки'],
          multi: true,
        },
        {
          step: 'База',
          question: 'Какие вопросы повторяются чаще всего?',
          why: 'Из этого собирается база знаний: на эти вопросы AI будет отвечать сам, без ожидания администратора.',
          options: ['Цены и услуги', 'График врачей', 'Подготовка к анализам', 'Как выбрать врача', 'Адрес и как добраться'],
          multi: true,
        },
        {
          step: 'Сценарии',
          question: 'Что AI может отвечать сам, без человека?',
          why: 'Так мы определяем сценарии первых ответов — и где помощник экономит больше всего времени.',
          options: ['Цены и услуги', 'Запись на приём', 'График и свободные окна', 'Подготовка к процедурам'],
          multi: true,
        },
        {
          step: 'Границы',
          question: 'Когда AI должен сразу передать диалог человеку?',
          why: 'Правила безопасности: AI не изображает врача. Чёткие границы — то, что отличает помощника от «бота».',
          options: ['Медицинские вопросы', 'Жалобы и спорные ситуации', 'Срочные случаи', 'Нестандартные запросы'],
          multi: true,
        },
        {
          step: 'Заявка',
          question: 'Куда отправлять готовую заявку?',
          why: 'Заявка должна попадать туда, где ваша команда уже работает, — иначе она потеряется.',
          options: ['WhatsApp или Telegram администратора', 'Таблица (Google Sheets)', 'CRM клиники', 'На почту'],
          multi: false,
        },
      ],
      planStepLabel: 'План',
      backLabel: 'Назад',
      nextLabel: 'Дальше',
      finishLabel: 'Показать план',
    },
    plan: {
      title: 'Черновик запуска AI-администратора',
      subtitle: 'Собрано из ваших ответов. Это отправная точка — детали уточним на коротком разборе.',
      blockChannels: 'Каналы',
      blockKnowledge: 'База знаний',
      blockScenarios: 'AI отвечает сам',
      blockHandoff: 'Передаёт человеку',
      blockLead: 'Заявка',
      leadFieldsNote: 'В заявке: контакт, направление, цель обращения, удобное время.',
      emptyValue: 'Уточним на разборе',
      priceLine: 'AI-администратор под ключ — от 150 000 ₸.',
      priceNote: 'В базовый запуск входит настройка под клинику, база знаний, сценарии ответов и правила передачи человеку.',
      ctaPrimary: 'Обсудить запуск',
      ctaWhatsapp: 'Отправить план в WhatsApp',
      restartLabel: 'Пройти заново',
    },
  },
  pain: {
    headline: 'Где клиника теряет пациентов',
    emphasisTitle: 'Цена одного пропущенного сообщения',
    emphasisText:
      'Пациенту не ответили за пять минут, и он просто написал в другую клинику. Он уже был готов прийти, но выбрал тех, кто ответил первым.',
    items: [
      'Пациент написал вечером, а ответили только утром. Он уже записался в другом месте.',
      'Администратор на ресепшене или на звонке, а сообщение в WhatsApp ждёт час.',
      'Каждый день по кругу одни и те же вопросы про цены и график.',
      'Человек спросил и пропал, а напомнить и довести до записи некому.',
      'Заявку передали врачу без деталей: непонятно, кто это и с чем пришёл.',
    ],
    bottomLine:
      'Дело не в том, что администратор плохо работает. Просто один человек не может отвечать всем и сразу, особенно вечером, ночью и в выходные, когда пишут чаще всего.',
  },
  howItWorks: {
    headline: 'Что происходит, когда пациент вам написал',
    subheadline: 'Помощник ведёт только начало разговора и передаёт администратору готовую заявку со всеми деталями.',
    steps: [
      {
        number: '01',
        icon: 'MessageCircle',
        title: 'Пациент пишет',
        description: 'В WhatsApp, Instagram, Telegram или прямо на сайте, как ему удобно.',
      },
      {
        number: '02',
        icon: 'Zap',
        title: 'Ему сразу отвечают',
        description: 'За несколько секунд. Даже поздно вечером или когда администратор занят.',
      },
      {
        number: '03',
        icon: 'ListChecks',
        title: 'Помощник всё уточняет',
        description: 'Что беспокоит, к какому врачу и на какое время. Отвечает на вопросы о ценах и услугах.',
      },
      {
        number: '04',
        icon: 'Phone',
        title: 'Собирает заявку',
        description: 'Имя, телефон, направление и удобное время для записи.',
      },
      {
        number: '05',
        icon: 'ClipboardList',
        title: 'Передаёт администратору',
        description: 'Готовую заявку с деталями. Остаётся только подтвердить время. Сложный случай передаёт человеку раньше.',
      },
    ],
  },
  vsChatbot: {
    headline: 'Это не тот раздражающий бот с кнопками',
    description1:
      'Обычный бот отвечает только заученными фразами и «нажмите 1, нажмите 2». Наш помощник понимает живую речь и ведёт нормальный разговор, как хороший администратор.',
    description2:
      'Он понимает вопрос, заданный своими словами, уточняет детали, отвечает по-человечески и передаёт администратору готовую заявку. Пациент часто даже не понимает, что писал не человеку.',
    chatbotCard: {
      title: 'Обычный бот',
      items: ['Ждёт, что вы нажмёте кнопку', 'Не понимает вопрос своими словами', 'Чуть что, сразу «ожидайте оператора»'],
    },
    aiCard: {
      title: 'Наш помощник',
      items: ['Понимает живую речь', 'Уточняет, что нужно', 'Собирает контакт и время', 'Передаёт готовую заявку'],
    },
  },
  automate: {
    headline: 'Начните с одного сценария',
    actionLabel: 'Что делает',
    outcomeLabel: 'Что это даёт клинике',
    exampleLabel: 'Пример',
    items: [
      { title: 'Запись на приём', description: 'Уточняет, что беспокоит, к какому врачу и на какое время, берёт контакт.', outcome: 'Администратор получает готовую заявку, а не начинает разговор с нуля.', example: 'Взрослый, к кардиологу, в четверг после 17:00, телефон записан.' },
      { title: 'Ответы на вопросы', description: 'Отвечает про цены, услуги, врачей, график и подготовку к приёму, опираясь на вашу информацию.', outcome: 'Администратор не тратит время на одни и те же вопросы каждый день.', example: '«Сколько стоит первичный приём и как подготовиться к анализам?»' },
      { title: 'Помощь с выбором врача', description: 'По жалобе подсказывает, к какому специалисту записаться, в рамках ваших правил.', outcome: 'Пациент понимает, что делать дальше. Диагноз при этом не ставится.', example: 'Подсказывает, к какому врачу клиника советует обратиться с таким вопросом.' },
      { title: 'Передача человеку', description: 'Замечает сложный, спорный или срочный случай и сразу зовёт живого администратора.', outcome: 'Помощник не пытается решать там, где нужен человек или врач.', example: 'Тревожный симптом, жалоба или просьба «соедините с человеком».' },
      { title: 'Связь с вашими программами', description: 'Отправляет заявку туда, где вам удобно: в Telegram, таблицу или вашу CRM.', outcome: 'Ничего менять не нужно: помощник встраивается в то, как вы уже работаете.', example: 'Заявка сама падает нужному администратору в Telegram.' },
    ],
    bottomLine: 'Обычно стартуем с одного, самого важного для вас потока. С чего начать — решим вместе на коротком разборе.',
  },
  whatWeNeed: {
    headline: 'Что нужно от вас, чтобы начать',
    items: [
      { number: '01', title: 'Про ваши услуги и цены', description: 'Что делаете, сколько стоит, график работы и правила записи.' },
      { number: '02', title: 'Частые вопросы пациентов', description: 'О чём чаще всего спрашивают перед тем, как записаться.' },
      { number: '03', title: 'Один канал для старта', description: 'Где начнём: сайт, WhatsApp, Instagram или Telegram.' },
      { number: '04', title: 'Кому передавать заявки', description: 'Администратору, в таблицу или в вашу программу.' },
    ],
    bottomLine: 'Разбираться в технологиях не нужно: настройку мы берём на себя. Если каких-то материалов нет, соберём их вместе на разборе.',
  },
  trust: {
    headline: 'AI знает, где остановиться',
    description1:
      'В медицине это главное. Помощник не заменяет врача и не ставит диагнозов. Он занимается только организацией: отвечает на вопросы, помогает записаться и собирает заявку.',
    description2:
      'Если случай сложный, спорный или срочный, помощник не додумывает. Он сразу передаёт разговор живому человеку.',
    cards: [
      'Не ставит диагнозов и не назначает лечение',
      'Не обещает того, чего вы не подтвердили',
      'Не выдумывает цены и условия',
      'Сложные и срочные случаи сразу передаёт человеку',
    ],
  },
  messageToLead: {
    headline: 'Один вопрос пациента — два разных процесса',
    subheadline:
      'Слева — сообщение, с которым администратору нужно разбираться вручную. Справа — то, что он получает после диалога с DamiWorks.',
    before: {
      title: 'Обычное входящее сообщение',
      patientMessage: 'Здравствуйте, сколько стоит имплантация?',
      problemsTitle: 'Администратору нужно выяснять вручную:',
      problems: [
        'Первичная консультация или уже есть план лечения?',
        'Когда пациенту удобно прийти?',
        'Как с ним связаться?',
        'Насколько это срочно?',
      ],
    },
    after: {
      title: 'После диалога с DamiWorks',
      fields: [
        { label: 'Услуга', value: 'Имплантация' },
        { label: 'Цель', value: 'Узнать цену и записаться' },
        { label: 'Время', value: 'На этой неделе' },
        { label: 'Контакт', value: 'Получен' },
      ],
      nextStepLabel: 'Следующий шаг',
      nextStep: 'Предложить окна консультации',
    },
  },
  adminHandoff: {
    eyebrow: 'Итог каждого диалога',
    headline: 'Администратор получает не переписку, а готовую заявку',
    subheadline:
      'Каждый диалог превращается в короткую сводку: кто пишет, что нужно, когда удобно и что делать дальше. Остаётся подтвердить время.',
    points: [
      'Не нужно перечитывать переписку',
      'Видно, кого AI передал человеку и почему',
      'Заявка приходит туда, где вы работаете: в Telegram, таблицу или CRM',
    ],
    card: {
      title: 'Новая заявка',
      fields: [
        { label: 'Направление', value: 'Стоматология' },
        { label: 'Запрос', value: 'Болит зуб, хочет консультацию' },
        { label: 'Удобное время', value: 'Сегодня после 17:00' },
        { label: 'Контакт', value: '+7 707 ••• •• 44' },
        { label: 'Статус', value: 'Контакт получен' },
      ],
      pill: 'Готово к передаче',
      nextStepLabel: 'Следующий шаг для администратора',
      nextStep: 'Предложить окна сегодня после 17:00 и подтвердить запись',
    },
  },
  launch: {
    headline: 'Запуск под ключ: от базы знаний до готовых заявок',
    subheadline:
      'Настраиваем, запускаем и улучшаем вместе с вами — по реальным диалогам, а не по ощущениям.',
    steps: [
      {
        number: '01',
        title: 'Разбираем ваш процесс',
        description: 'Какие обращения приходят, что AI возьмёт на себя, где границы и кому передавать заявки.',
      },
      {
        number: '02',
        title: 'Настраиваем и запускаем',
        description: 'Техническую часть берём на себя: база знаний, сценарии ответов, правила безопасности и передача заявок вашей команде.',
      },
      {
        number: '03',
        title: 'Улучшаем по реальным диалогам',
        description: 'Смотрим переписки, правим слабые ответы и решаем вместе, что расширять дальше.',
      },
    ],
    measuresTitle: 'Что смотрим после запуска',
    measures: [
      'Сколько обращений обработал AI',
      'Сколько контактов собрал',
      'Сколько заявок передал команде',
      'Где передал человеку',
      'Какие вопросы повторяются чаще всего',
    ],
    needTitle: 'От клиники нужно только это',
    needItems: ['Услуги и цены', 'Частые вопросы пациентов', 'Правила записи', 'Кому передавать заявки'],
    pricingLine: 'AI-администратор под ключ — от 150 000 ₸.',
    priceNote:
      'В базовый запуск входит настройка под клинику, база знаний, сценарии ответов, правила передачи человеку и формат заявки для администратора. Дополнительные интеграции и сложные каналы — отдельно, после разбора.',
    ctaPrimary: 'Обсудить запуск',
    ctaSecondary: 'Сначала попробовать демо',
  },
  launchKit: {
    headline: 'Что входит в запуск AI-администратора',
    subheadline:
      'Мы не отдаём вам пустого бота. Настраиваем систему под ваши услуги, каналы и правила — и передаём заявки туда, где работает ваша команда.',
    channels: { title: 'Каналы входящих', items: ['WhatsApp', 'Instagram', 'Сайт', 'Telegram'] },
    core: {
      title: 'AI-администратор',
      layers: [
        { title: 'База знаний клиники', text: 'Услуги, цены, график, подготовка, правила записи.' },
        { title: 'Сценарии общения', text: 'Запись, вопросы о ценах, подбор направления, частые вопросы.' },
        { title: 'Правила безопасности', text: 'Где отвечает сам, где уточняет, где сразу передаёт человеку.' },
      ],
    },
    handoff: { title: 'Готовая заявка команде', items: ['WhatsApp / Telegram', 'Таблица', 'CRM'] },
  },
  safetyFlow: {
    headline: 'AI знает, где отвечать, а где передать человеку',
    subheadline:
      'Он не ставит диагнозы и не изображает врача. Его задача — принять первое сообщение, уточнить организационные детали и вовремя передать диалог вашей команде.',
    guarantees: ['Не ставит диагнозы', 'Не назначает лечение', 'Не выдумывает цены'],
    states: [
      { title: 'Отвечает сам', description: 'Организационные вопросы: цены, график, подготовка, запись, услуги.' },
      { title: 'Уточняет по правилам', description: 'Собирает контекст: направление, цель обращения, удобное время, контакт.' },
      {
        title: 'Передаёт человеку',
        description: 'Когда вопрос медицинский, срочный, спорный или выходит за базу знаний.',
        note: 'При тревожных симптомах не продолжает диалог, а направляет к срочной помощи и человеку.',
      },
    ],
  },
  evidence: {
    eyebrow: 'Проверьте сами, это бесплатно',
    headline: 'Не верьте на слово. Просто попробуйте прямо сейчас',
    subheadline:
      'В демо видно обе стороны: что видит пациент в переписке и какую готовую заявку получает администратор.',
    cards: [
      { title: 'Живой разговор', text: 'Пишите любой вопрос своими словами. Помощник отвечает вживую, здесь и сейчас.' },
      { title: 'Видно, где стоп', text: 'Спросите что-то сложное или срочное, и увидите, как помощник передаёт разговор человеку.' },
      { title: 'Виден результат', text: 'Прямо на глазах собирается заявка: врач, что беспокоит, время и статус.' },
      { title: 'Честный старт', text: 'До запуска договоримся, как поймём, что всё работает. Потом вместе смотрим реальные диалоги.' },
    ],
    bottomLine:
      'Никаких красивых чужих логотипов и придуманных цифр. До договора вы сами проверяете, как это работает, где границы и как мы будем измерять результат.',
  },
  founder: {
    eyebrow: 'Кто отвечает за проект',
    headline: 'Проект ведёт команда DamiWorks',
    description:
      'Мы сами разбираем, как устроена ваша клиника, настраиваем запуск и проверяем ответы после старта. Основатель лично участвует в каждом запуске, чтобы он не превратился в «поставили бота и забыли». Ваша задача не потеряется в общей очереди заявок.',
    name: 'Дамир, основатель',
    role: 'Работаем с вами лично весь запуск',
    personalNote:
      'Начинаем с одной понятной задачи. Сразу честно говорим, что помощник умеет, а что нет. После запуска сами разбираем реальные диалоги и делаем ответы лучше.',
    points: ['На связи с вами весь запуск', 'Запускаем поэтапно, без резких движений', 'Заранее договариваемся об объёме и цене', 'Сами разбираем диалоги после старта'],
    cta: 'Обсудить мою клинику',
  },
  faq: {
    headline: 'Частые вопросы перед стартом',
    subheadline: 'Прямые ответы на то, что обычно волнует до запуска.',
    items: [
      { question: 'Помощник заменит моего администратора?', answer: 'Нет. Он берёт на себя рутину: типовые вопросы и сбор заявок. Сложное и важное по-прежнему делает ваш администратор. Просто теперь у него больше времени на живых пациентов.' },
      { question: 'А если он чего-то не знает?', answer: 'Он не имеет права выдумывать. Если ответа нет в том, что вы подтвердили, помощник честно скажет об этом и передаст вопрос вашему сотруднику.' },
      { question: 'Можно ли вообще использовать это в медицине?', answer: 'Да, для организационных задач: вопросы об услугах, ценах, графике и записи. Диагнозы, назначения и заключения всегда остаются за врачом.' },
      { question: 'Как понять, что это работает?', answer: 'До запуска договоримся о простых понятных критериях: как быстро приходит ответ, собираются ли контакты, удобно ли администратору. Потом вместе смотрим реальные диалоги.' },
      { question: 'Сколько это стоит?', answer: 'Запуск под ключ — от 150 000 ₸. В базовую цену входит настройка под клинику, база знаний и передача заявок. Дополнительные интеграции и сложные каналы считаем отдельно. Точную цену назовём после короткого разбора, без сюрпризов.' },
      { question: 'Что нужно подготовить?', answer: 'Услуги, цены, врачей, график и правила записи. Плюс частые вопросы пациентов. Если чего-то нет, соберём вместе.' },
    ],
  },
  demo: {
    headline: 'Побудьте пациентом и проверьте AI вживую',
    subheadline:
      'Выберите пример клиники, напишите любой вопрос и увидите, какую готовую заявку получит администратор.',
    proofPoints: [
      'Живой разговор, не запись',
      'Видно, где AI зовёт человека',
      'Заявка собирается у вас на глазах',
    ],
    scenarios: [
      {
        id: 'damiworks',
        label: 'DamiWorks-консультант',
        agentName: 'Консультант DamiWorks',
        messages: [
          { from: 'user', text: 'Что ваш помощник может сделать для моей клиники?' },
          {
            from: 'ai',
            text: 'Отвечаю пациентам круглосуточно, помогаю выбрать врача, записываю на приём и передаю вам готовую заявку по каждому обращению.',
          },
        ],
        leadSummary: {
          service: 'Помощник под вашу клинику',
          need: 'Ответы и запись пациентов',
          time: 'Как можно скорее',
          status: 'Знакомство',
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
        // Hidden on the clinic-focused RU landing: a non-medical tab dilutes
        // the "we understand clinics" positioning.
        hidden: true,
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
          status: 'Хочет записаться',
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
          status: 'Готов записаться',
        },
      },
    ],
    customDemoTab: {
      id: 'custom_demo',
      label: 'Своё демо',
      title: 'Проверьте помощника на данных вашей клиники',
      description:
        'Загрузите материалы или просто опишите клинику, затем напишите как пациент и увидите, как помощник ответит.',
      hidden: true,
    },
    staticChat: {
      inputPlaceholder: 'Написать сообщение...',
      sendAriaLabel: 'Отправить',
      onlineLabel: 'Онлайн',
    },
    leadSummary: {
      title: 'Сводка по заявке',
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
        start: 'Базовый запуск',
        sales: 'Помощник для записи',
        integrated: 'Помощник с подключениями',
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
      mobileIntroMessage: 'Здравствуйте! Помогу с записью, ценами и выбором специалиста. Что вас интересует?',
      quickReplies: [
        'Сколько стоит консультация?',
        'К какому врачу записаться?',
        'Как подготовиться к анализам?',
        'Можно записать ребёнка?',
        'График врачей',
      ],
      loadingStages: [
        'AI читает вопрос…',
        'Уточняет детали…',
        'Собирает сводку для администратора…',
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
    scenarioSelectLabel: 'Выберите пример клиники',
    mobileSummaryLabel: 'Что получит администратор',
    conversionTitle: 'Хотите проверить это на своих услугах и ценах?',
    conversionText: 'Подготовим план запуска для вашей клиники: с чего начать и какие данные помощник будет собирать для администратора.',
    conversionPrimary: 'Обсудить запуск',
    conversionSecondary: 'Спросить у DamiWorks',
  },
  capabilities: {
    headline: 'С чего можно начать',
    subheadline:
      'Не нужно сразу автоматизировать всё. Начинаем с одной понятной задачи, а после первых живых диалогов расширяем, если захотите.',
    cta: 'Не знаете, что подойдёт именно вам? Пройдите короткий подбор в чате. Это займёт минуту.',
    ctaLink: 'Пройти подбор →',
    tiers: [
      {
        id: 'start',
        number: '01',
        name: 'Простой помощник',
        tagline: 'Чтобы быстро попробовать на живых диалогах.',
        features: [
          { name: 'Ответы на частые вопросы', description: 'Про услуги, цены, график, запись и условия.' },
          { name: 'Сбор контакта', description: 'Имя, телефон и с чем обращается пациент.' },
          { name: 'Передача заявки', description: 'Администратору, в WhatsApp/Telegram или таблицу.' },
          { name: 'Один канал', description: 'WhatsApp, Instagram, Telegram или сайт.' },
        ],
        footerText: 'Чтобы за короткий срок проверить помощника на реальных пациентах, без сложных подключений.',
      },
      {
        id: 'sales',
        number: '02',
        name: 'Помощник для записи',
        tagline: 'Когда важно не просто отвечать, а доводить пациента до записи.',
        features: [
          { name: 'Понимает, кто готов записаться', description: 'Отличает готового пациента от того, кто просто спрашивает.' },
          { name: 'Собирает детали', description: 'Что нужно, на когда и как удобнее связаться.' },
          { name: 'Напоминает', description: 'Мягко возвращает тех, кто спросил и пропал.' },
          { name: 'Передаёт готовые заявки', description: 'Администратору, в таблицу или CRM с короткой сводкой.' },
        ],
        footerText: 'Когда помощник должен не просто отвечать, а отличать готовых записаться от тех, кто пока приценивается.',
      },
      {
        id: 'integrated',
        number: '03',
        name: 'Помощник с подключениями',
        tagline: 'Когда нужно связать с вашей CRM, таблицами и правилами клиники.',
        features: [
          { name: 'Ваша CRM', description: 'Подключение к программам, в которых вы уже работаете.' },
          { name: 'Записи, статусы, расписание', description: 'Учитывает свободные окна и статусы, если нужно.' },
          { name: 'Направляет нужному человеку', description: 'Разным администраторам или отделениям.' },
          { name: 'Правила вашей клиники', description: 'Настраиваем под то, как всё устроено именно у вас.' },
        ],
        footerText:
          'Когда помощник должен работать не только в переписке, но и с вашими программами и правилами.',
      },
    ],
  },
  valueProp: {
    headline: 'Как проходит запуск',
    description:
      'Вам не нужно ничего настраивать. Сначала мы разбираем одну задачу вашей клиники, собираем всю нужную информацию, задаём границы и подключаем передачу живому человеку. После старта проверяем ответы на реальных диалогах.',
    items: [
      {
        number: '01',
        title: 'Разбираю вашу задачу',
        description:
          'Определяем, с чего начать, что помощник должен собирать и когда звать человека. Сразу договариваемся, как поймём, что всё работает.',
      },
      {
        number: '02',
        title: 'Настраиваю и запускаю',
        description:
          'Готовим ответы на типовые и сложные вопросы, подключаем канал и передачу заявок вашему администратору. Вам делать ничего не нужно.',
      },
      {
        number: '03',
        title: 'Разбираю реальные диалоги',
        description:
          'Находим слабые ответы и делаем их лучше. Честно показываем, где помощник справляется сам, а где нужен человек.',
      },
    ],
  },
  pricing: {
    headline: 'Простые цены. Без скрытых платежей.',
    subheadline:
      'Понятные пакеты под разные задачи: от первого запуска до записи пациентов, подключения ваших программ и сложных случаев.',
    note: 'Итоговая цена зависит от объёма. Назовём её до старта, без сюрпризов.',
    pilotOffer: {
      eyebrow: 'Начать без большого внедрения',
      title: 'Начнём с одной задачи и проверим её на живых пациентах',
      subtitle:
        'Для медицинских центров, стоматологий, лабораторий и частных специалистов.',
      body:
        'Не будем автоматизировать всё сразу. Выберем один поток, например вопросы до приёма или запись на консультацию. Настроим ответы, безопасные границы и передачу администратору. До запуска договоримся, как будем понимать, что всё работает.',
      includesTitle: 'Где помощник помогает',
      bullets: [
        'Отвечает пациентам круглосуточно, даже ночью и в выходные',
        'Рассказывает про услуги, врачей, цены и график',
        'Помогает выбрать врача по жалобе',
        'Собирает заявку на запись и контакт',
        'Передаёт готовую заявку администратору, остаётся подтвердить время',
      ],
      cards: [
        { label: 'Объём', title: 'Одна задача, один канал', text: 'Фокусируемся на одном понятном процессе, чтобы быстро увидеть реальную пользу, без месяцев внедрения.' },
        { label: 'Результат', title: 'Рабочий помощник и готовые заявки', text: 'Настроенные ответы, сбор контакта и готовая сводка для администратора.' },
        { label: 'Контроль', title: 'Первый месяц вместе', text: 'Разбираем реальные диалоги, правим слабые ответы и доводим до стабильной работы.' },
      ],
      pricingLine:
        'Пробный запуск стоит от 150 000 ₸. Точную цену назовём до старта, после короткого разбора вашей клиники.',
      adaptNote:
        'По такому же принципу помощника можно сделать для школ, салонов, курсов, магазинов и услуг, не только для клиник.',
      ctaPrimary: 'Получить бесплатный разбор',
      ctaSecondary: 'Сначала попробовать демо',
    },
    plans: [
      {
        id: 'start',
        name: 'Пробный запуск',
        description:
          'Первый запуск на одном канале: ответы на частые вопросы, сбор контакта и передача заявки администратору.',
        priceSetup: 'от 150 000 ₸ за запуск',
        priceMonthly: 'Первый месяц поддержки уже в цене',
        priceMonthlyDetail: 'дальше от 40 000–60 000 ₸/мес',
        badge: null,
        highlighted: false,
        features: [
          'Один канал',
          'Ответы на частые вопросы',
          'Сбор контактов',
          'Передача заявки администратору или в таблицу',
          'Проверка на реальных диалогах',
          'Первые правки после запуска',
        ],
        supportNote:
          'В первый месяц мы проверяем ответы на реальных диалогах, правим их и доводим помощника до стабильной работы. Дополнительные каналы и подключения к программам считаем отдельно. После первого месяца можно продолжить, расширить или остановиться без обязательств.',
        limitNote: null,
        reassurance: null,
        cta: 'Начать',
      },
      {
        id: 'sales',
        name: 'Помощник для записи',
        description:
          'Для клиник, где важно не только отвечать, но и доводить пациента до записи на нескольких каналах.',
        priceSetup: 'от 350 000 ₸ за запуск',
        priceMonthly: 'Первый месяц поддержки уже в цене',
        priceMonthlyDetail: 'дальше от 120 000 ₸/мес',
        badge: 'ПОПУЛЯРНЫЙ',
        highlighted: true,
        features: [
          '1–3 канала',
          'Понимает, кто готов записаться',
          'Собирает контакт и детали',
          'Передача в WhatsApp / таблицу / CRM',
          'Напоминания тем, кто пропал',
          'Проверка на реальных диалогах',
          'Регулярные улучшения',
        ],
        supportNote:
          'В первый месяц проверяем, как помощник доводит до записи, как собирает заявки и как напоминает. Дальше можно продолжить поддержку, добавить каналы или подключения к вашим программам.',
        limitNote: null,
        reassurance: null,
        cta: 'Начать',
      },
      {
        id: 'integrated',
        name: 'Помощник с подключениями',
        description:
          'Для сложных процессов: ваша CRM, расписание, статусы, несколько администраторов и правила клиники.',
        priceSetup: 'от 700 000 ₸ за запуск',
        priceMonthly: 'Три месяца поддержки уже в цене',
        priceMonthlyDetail: 'дальше от 200 000 ₸/мес',
        badge: null,
        highlighted: false,
        features: [
          'Несколько каналов',
          'Подключение к вашей CRM',
          'Записи, заказы или статусы',
          'Направляет нужному администратору',
          'Правила вашей клиники',
          'Расширенный контроль качества',
        ],
        supportNote:
          'Первые три месяца следим за стабильностью подключений, качеством ответов и сложными случаями. Дальнейшую поддержку согласуем по объёму: наблюдение, правки, развитие и поддержка подключений.',
        limitNote: null,
        reassurance: null,
        cta: 'Обсудить проект',
      },
    ],
  },
  contact: {
    headline: 'Разберём входящие заявки\nвашей клиники',
    description:
      'За 20 минут посмотрим, как к вам приходят обращения: что AI возьмёт на себя, где будет передавать человеку и как будет выглядеть заявка для администратора.',
    note: '',
    highlights: [
      'посмотрим ваши обращения и каналы',
      'выберем безопасную задачу для старта',
      'назовём понятную цену и сроки',
    ],
    formTitle: 'Получить план запуска',
    formSubtitle: 'Напишем вам в WhatsApp или Telegram.',
    calendlyButton: 'Записаться на 20-минутный разбор',
    calendlySubtext: '20 минут, бесплатно, без обязательств. Или оставьте контакт ниже — напишем сами.',
    whatsappButton: 'Написать в WhatsApp',
    placeholderName: 'Ваше имя',
    placeholderContact: 'WhatsApp / Telegram',
    placeholderBusinessType: 'Тип клиники или бизнеса',
    placeholderMessage: 'Например: стоматология, пишут с сайта и WhatsApp, спрашивают про цены и запись. (необязательно)',
    messageHelp: 'Можно коротко, детали уточним сами.',
    submitButton: 'Отправить',
    successMessage: 'Спасибо! Скоро напишем вам.',
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
    consentText: 'Отправляя форму, вы соглашаетесь, что мы используем ваш контакт только чтобы ответить на эту заявку.',
    privacyLabel: 'Уведомление о конфиденциальности',
    privacyHref: '/ru/privacy',
  },
  footer: {
    tagline: 'Умный администратор для клиник и сервисного бизнеса.',
    badges: [
      'Настроим за вас',
      'Поддержка после запуска',
      'Под вашу клинику',
    ],
    privacyLabel: 'Конфиденциальность',
  },
  liveChat: {
    introMessage:
      'Привет! Поможем разобраться, какой помощник подойдёт вашей клинике: чтобы отвечать пациентам, доводить до записи и передавать заявки администратору.\n\nМожете задать вопрос или пройти короткий подбор за минуту.',
    introChips: [
      'Подобрать помощника',
      'Сколько стоит?',
      'Как это работает?',
      'Чем лучше обычного бота?',
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
      priceDiscovery: 'Назову после короткого разбора',
    },
    packageSelectedPattern: '✅ {pkg} подобран',
    perDayLabel: '/день',
    askQuestionButton: 'Задать вопрос →',
    sendToOwnerButton: 'Отправить Дамиру',
    sentConfirmation: 'Заявку получили. Скоро напишем вам в WhatsApp или Telegram. Можно задать вопрос ниже.',
    editAnswersButton: '← Изменить ответы',
    intakeStartMessage: 'Отлично! Зададим 5 коротких вопросов и подберём подходящий вариант.',
    intakeCompleteMessage: 'Готово! Вот что советую по вашим ответам:',
    errorMessage: 'Что-то пошло не так. Попробуйте ещё раз.',
    resetTitle: 'Сбросить',
    resetLabel: 'Сброс',
    inputPlaceholder: 'Задайте вопрос...',
    sendAriaLabel: 'Отправить',
    onlineLabel: 'Онлайн',
    leadSentChipLabel: '✅ Отправлено',
    contactClosedPill: '✅ Заявка отправлена. Я свяжусь с вами в WhatsApp или Telegram.',
    contactClosedInputPlaceholder: 'Заявка отправлена',
    bookCallButton: '📅 Забронировать звонок',
    leaveContactButton: '📱 Оставить контакт',
  },
  customDemoChat: {
    introMessage:
      'Загрузите материалы о клинике: прайс, список услуг, ответы на частые вопросы или описание. Нет файла? Просто опишите, что делаете, цены и о чём чаще спрашивают.\n\nПотом напишите вопрос как пациент, и мы покажем, как помощник ответит по этим материалам.',
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
    materialsUploadedMessage: 'Материалы загружены. Теперь задайте вопрос как клиент, и мы ответим с учётом этих материалов.',
  },
  intake: {
    questions: [
      {
        id: 'channels',
        text: 'Где вам пишут пациенты? Можно выбрать несколько.',
        options: ['WhatsApp', 'Instagram', 'Telegram', 'Сайт', 'Другое'],
        values: ['WhatsApp', 'Instagram', 'Telegram', 'Website', 'Другое'],
        multi: true,
      },
      {
        id: 'tasks',
        text: 'Что помощник должен делать в первую очередь? (можно выбрать несколько)',
        options: [
          'Отвечать на вопросы',
          'Собирать контакты',
          'Понимать, кто готов записаться',
          'Передавать заявки администратору',
          'Напоминать тем, кто пропал',
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
