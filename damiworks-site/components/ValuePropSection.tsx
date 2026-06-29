import type { DictValueProp } from '@/lib/i18n'

export default function ValuePropSection({ dict }: { dict: DictValueProp }) {
  return (
    <section className="py-20 bg-bg border-t border-border-col">
      <div className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl mb-12">
          <h2 className="text-2xl lg:text-3xl font-bold text-primary mb-4">
            {dict.headline}
          </h2>
          <p className="text-secondary leading-relaxed">{dict.description}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
          {dict.items.map((item) => (
            <div key={item.number}>
              <div className="text-xs font-semibold text-accent tracking-widest mb-3">
                {item.number}
              </div>
              <h3 className="text-base font-semibold text-primary mb-2">{item.title}</h3>
              <p className="text-sm text-secondary leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
