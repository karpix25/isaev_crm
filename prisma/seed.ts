import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    console.log('🌱 Seeding database...\n');

    // Create test user
    const user = await prisma.user.upsert({
        where: { tgId: BigInt(123456789) },
        update: {},
        create: {
            tgId: BigInt(123456789),
            name: 'Тестовый Менеджер',
            role: 'manager',
        },
    });
    console.log('✅ Created user:', user.name);

    // Create test leads
    const leads = [
        {
            clientName: 'Иван Петров',
            phone: '+79001234567',
            areaSq: 45.5,
            budget: 250000,
            status: 'NEW' as const,
            avitoLink: 'https://avito.ru/moskva/remont/test1',
        },
        {
            clientName: 'Мария Сидорова',
            phone: '+79007654321',
            areaSq: 62.0,
            budget: 400000,
            status: 'QUALIFIED' as const,
            avitoLink: 'https://avito.ru/moskva/remont/test2',
        },
        {
            clientName: 'Алексей Иванов',
            phone: '+79009876543',
            areaSq: 38.0,
            budget: 180000,
            status: 'CONSULT' as const,
        },
        {
            clientName: 'Елена Смирнова',
            phone: '+79005551234',
            areaSq: 75.0,
            budget: 500000,
            status: 'CONTRACT' as const,
        },
        {
            clientName: 'Дмитрий Козлов',
            phone: '+79003332211',
            areaSq: 52.0,
            budget: 320000,
            status: 'REPAIR' as const,
        },
    ];

    for (const leadData of leads) {
        const lead = await prisma.lead.create({
            data: {
                ...leadData,
                userId: user.id,
            },
        });

        // Create chat for each lead
        const messages = [];
        if (lead.status !== 'NEW') {
            messages.push({
                role: 'user',
                text: `Здравствуйте! Хочу сделать ремонт квартиры ${leadData.areaSq}м²`,
                ts: new Date().toISOString(),
            });
            messages.push({
                role: 'ai',
                text: 'Здравствуйте! Отлично, мы поможем вам с ремонтом. Какой у вас бюджет?',
                ts: new Date().toISOString(),
            });
            messages.push({
                role: 'user',
                text: `Примерно ${leadData.budget?.toLocaleString()} рублей`,
                ts: new Date().toISOString(),
            });
        }

        await prisma.chat.create({
            data: {
                leadId: lead.id,
                messages: messages as any,
                memory: messages.length > 0
                    ? `Клиент интересуется ремонтом ${leadData.areaSq}м², бюджет ${leadData.budget}₽`
                    : null,
            },
        });

        console.log(`✅ Created lead: ${leadData.clientName} (${leadData.status})`);
    }

    // Create sample RAG documents
    console.log('\n📚 Creating RAG documents...');

    const ragDocs = [
        'Наша компания занимается ремонтом квартир под ключ с 2015 года. Мы предлагаем полный спектр услуг от косметического до капитального ремонта.',
        'Стоимость работ: косметический ремонт от 5000₽/м², капитальный ремонт от 12000₽/м². Цены включают материалы и работу.',
        'Гарантия на все виды работ - 2 года. Мы используем только качественные материалы от проверенных производителей.',
        'Сроки выполнения: косметический ремонт 2-3 недели, капитальный ремонт 1-2 месяца в зависимости от площади.',
    ];

    for (const doc of ragDocs) {
        // Note: We can't insert embeddings without OpenRouter API key
        // This would be done via /api/rag/embed endpoint in production
        console.log(`  - ${doc.substring(0, 50)}...`);
    }

    console.log('\n✅ Database seeded successfully!');
    console.log('\n📊 Summary:');
    console.log(`  - Users: 1`);
    console.log(`  - Leads: ${leads.length}`);
    console.log(`  - Chats: ${leads.length}`);
    console.log(`  - RAG docs: ${ragDocs.length} (ready for embedding)`);
}

main()
    .catch((e) => {
        console.error('❌ Seed error:', e);
        process.exit(1);
    })
    .finally(async () => {
        await prisma.$disconnect();
    });
