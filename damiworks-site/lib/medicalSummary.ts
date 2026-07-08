// RU normalization for the MedNova summary panel so a known specialty/symptom
// never renders in English. Kept as a standalone module so the mapping is unit
// testable without rendering the React component.

// RU labels + EN synonyms.
export const SPECIALTY_PATTERNS: Array<[RegExp, string]> = [
  [/кардиолог|cardiolog/i, 'Кардиолог'],
  [/педиатр|pediatric|paediatric/i, 'Педиатр'],
  [/терапевт|therapist/i, 'Терапевт'],
  [/эндокринолог|endocrinolog/i, 'Эндокринолог'],
  [/гастроэнтеролог|gastroenterolog/i, 'Гастроэнтеролог'],
  [/невролог|neurolog/i, 'Невролог'],
  [/лор|отоларинголог|otolaryngolog|\bent\b/i, 'ЛОР'],
  [/дерматолог|dermatolog/i, 'Дерматолог'],
  [/гинеколог|gynecolog|gynaecolog/i, 'Гинеколог'],
  [/уролог|urolog/i, 'Уролог'],
  [/офтальмолог|окулист|ophthalmolog|oculist/i, 'Офтальмолог'],
  [/стоматолог|dentist/i, 'Стоматолог'],
  [/узи/i, 'УЗИ'],
  [/анализ/i, 'Анализы'],
]

// Known English clinical terms -> RU (only a small closed set is normalized).
export const SYMPTOM_TERMS: Array<[RegExp, string]> = [
  [/headache/gi, 'головная боль'],
  [/fever|temperature/gi, 'температура'],
  [/cough/gi, 'кашель'],
  [/sore throat/gi, 'боль в горле'],
  [/back pain/gi, 'боль в спине'],
  [/abdominal pain|stomach ache/gi, 'боль в животе'],
  [/rash/gi, 'сыпь'],
  [/consultation/gi, 'консультация'],
  [/appointment/gi, 'запись'],
]

export function normalizeSpecialty(raw: string): string {
  for (const [re, label] of SPECIALTY_PATTERNS) {
    if (re.test(raw)) return label
  }
  return raw
}

export function normalizeComplaint(raw: string): string {
  let text = raw
  for (const [re, ru] of SYMPTOM_TERMS) text = text.replace(re, ru)
  return text
}
