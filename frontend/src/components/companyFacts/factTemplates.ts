import type { CompanyFactCategory, CompanyFactPayload } from '@/types'

export type FactTemplate = {
    key: string
    title: string
    label: string
    placeholder: string
    help: string
    category: CompanyFactCategory
    value_type?: CompanyFactPayload['value_type']
    priority?: CompanyFactPayload['priority']
    tags?: string[]
    questions?: string[]
    hint?: string
    multiline?: boolean
}

export type FactSection = {
    category: CompanyFactCategory
    label: string
    description: string
    fields: FactTemplate[]
}

export const FACT_SECTIONS: FactSection[] = [
    {
        category: 'pricing',
        label: 'Цены',
        description: 'Тут задаются правила, по которым ИИ отвечает на вопросы про стоимость.',
        fields: [
            {
                key: 'price_from_per_m2',
                title: 'Минимальная цена работ за м²',
                label: 'Цена работ от, ₽/м²',
                placeholder: '15000',
                help: 'Если клиент спрашивает “от какой цены”, ИИ даст этот ориентир.',
                category: 'pricing',
                value_type: 'number',
                priority: 'core',
                tags: ['цена', 'стоимость', 'прайс'],
                questions: ['сколько стоит', 'цена за метр', 'расценки'],
            },
            {
                key: 'price_scope',
                title: 'Что входит в предварительную цену',
                label: 'Что входит в предварительный расчет',
                placeholder: 'Ремонтные работы без строительных материалов',
                help: 'Важно, чтобы ИИ не включал материалы в цену работ.',
                category: 'pricing',
                priority: 'core',
                multiline: true,
            },
            {
                key: 'price_fix_period_days',
                title: 'Фиксация цены',
                label: 'На сколько дней фиксируем цену',
                placeholder: '30',
                help: 'ИИ сможет сказать, что цена работ фиксируется за клиентом на месяц.',
                category: 'pricing',
                value_type: 'number',
                priority: 'core',
                tags: ['цена', 'смета'],
            },
            {
                key: 'price_discussion_rule',
                title: 'Как говорить о цене',
                label: 'Правило ответа про цену',
                placeholder: 'Дать вилку, объяснить что это работы без материалов, затем предложить замер или проект для точной сметы',
                help: 'Это не текст для клиента слово в слово, а инструкция для ИИ.',
                category: 'pricing',
                priority: 'core',
                multiline: true,
            },
        ],
    },
    {
        category: 'estimate',
        label: 'Смета',
        description: 'Сроки, формат и правила передачи сметы клиенту.',
        fields: [
            {
                key: 'estimate_sla_hours',
                title: 'Срок подготовки сметы',
                label: 'Сколько часов готовится смета',
                placeholder: '24',
                help: 'Используется в ответах и follow-up логике.',
                category: 'estimate',
                value_type: 'number',
                priority: 'core',
                tags: ['смета', 'срок'],
                questions: ['когда будет смета', 'сколько ждать смету'],
            },
            {
                key: 'estimate_delivery_format',
                title: 'Формат сметы',
                label: 'В каком формате отправляем смету',
                placeholder: 'PDF или Excel файлом в Telegram',
                help: 'Чтобы клиент понимал, что получит.',
                category: 'estimate',
            },
            {
                key: 'estimate_without_project_rule',
                title: 'Если нет дизайн-проекта',
                label: 'Что говорить без проекта',
                placeholder: 'Дать предварительную вилку по работам и предложить бесплатный замер для точного расчета',
                help: 'Защищает от обещания точной сметы вслепую.',
                category: 'estimate',
                priority: 'core',
                multiline: true,
            },
        ],
    },
    {
        category: 'portfolio',
        label: 'Портфолио',
        description: 'Ссылки и правило, как показывать клиенту примеры работ.',
        fields: [
            {
                key: 'portfolio_url',
                title: 'Ссылка на портфолио',
                label: 'Ссылка на портфолио',
                placeholder: 'https://isaevgroup.ru/portfolio/',
                help: 'ИИ даст эту ссылку, если клиент попросит примеры.',
                category: 'portfolio',
                value_type: 'url',
                priority: 'core',
                tags: ['портфолио', 'кейсы'],
                questions: ['портфолио', 'примеры работ', 'кейсы'],
            },
            {
                key: 'portfolio_usage_rule',
                title: 'Как предлагать портфолио',
                label: 'Как ИИ должен предлагать кейсы',
                placeholder: 'Дать ссылку и предложить показать похожие объекты под тип ремонта клиента',
                help: 'Чтобы ответ был полезнее простой ссылки.',
                category: 'portfolio',
                multiline: true,
            },
        ],
    },
    {
        category: 'measurement',
        label: 'Замер',
        description: 'Как объяснять клиенту замер без давления и лишней воды.',
        fields: [
            {
                key: 'measurement_price',
                title: 'Стоимость замера',
                label: 'Стоимость замера',
                placeholder: 'Бесплатно',
                help: 'ИИ будет уверенно отвечать, платный замер или нет.',
                category: 'measurement',
                priority: 'core',
                tags: ['замер'],
            },
            {
                key: 'measurement_value',
                title: 'Зачем нужен замер',
                label: 'Зачем клиенту замер',
                placeholder: 'Инженер фиксирует реальные размеры и нюансы, чтобы смета была точной',
                help: 'Короткое объяснение пользы без спора с клиентом.',
                category: 'measurement',
                multiline: true,
            },
        ],
    },
    {
        category: 'services',
        label: 'Услуги',
        description: 'Типы объектов и ремонтов, с которыми работает компания.',
        fields: [
            {
                key: 'object_types',
                title: 'Типы объектов',
                label: 'Какие объекты делаете',
                placeholder: 'Квартиры, дома, коммерческие помещения',
                help: 'Помогает отвечать на вопросы про квартиры, дома и коммерцию.',
                category: 'services',
                priority: 'core',
                tags: ['объекты', 'коммерция'],
                questions: ['коммерческие делаете', 'дома делаете'],
            },
            {
                key: 'repair_types',
                title: 'Типы ремонта',
                label: 'Какие ремонты делаете',
                placeholder: 'Косметический, капитальный, под ключ',
                help: 'Список услуг без подробной методологии.',
                category: 'services',
            },
        ],
    },
    {
        category: 'company',
        label: 'Компания',
        description: 'Базовая информация, которую ИИ может использовать почти всегда.',
        fields: [
            {
                key: 'company_name',
                title: 'Название компании',
                label: 'Название компании',
                placeholder: 'ISAEV GROUP',
                help: 'Используется в приветствиях и объяснениях.',
                category: 'company',
                priority: 'core',
            },
            {
                key: 'company_short_description',
                title: 'Короткое описание компании',
                label: 'Чем занимается компания',
                placeholder: 'Ремонт квартир, домов и коммерческих помещений под ключ',
                help: 'Одно-два предложения без рекламной воды.',
                category: 'company',
                priority: 'core',
                multiline: true,
            },
            {
                key: 'working_hours',
                title: 'Рабочее время',
                label: 'Рабочее время',
                placeholder: 'Пн-Сб 10:00-19:00',
                help: 'Когда менеджер или команда обычно на связи.',
                category: 'company',
                tags: ['график', 'режим'],
            },
        ],
    },
]

export function templateToPayload(template: FactTemplate, value: string): CompanyFactPayload {
    return {
        key: template.key,
        title: template.title,
        value,
        category: template.category,
        value_type: template.value_type || 'text',
        priority: template.priority || 'scenario',
        tags: template.tags || [],
        stages: [],
        questions: template.questions || [],
        hint: template.hint || template.help,
        display_order: 0,
        is_active: true,
    }
}
