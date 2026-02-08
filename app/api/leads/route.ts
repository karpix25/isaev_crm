import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { Status } from '@prisma/client';

export async function GET(req: NextRequest) {
    try {
        const userId = req.headers.get('x-user-id');
        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { searchParams } = new URL(req.url);
        const status = searchParams.get('status') as Status | null;

        const where: any = { userId: parseInt(userId) };
        if (status) {
            where.status = status;
        }

        const leads = await prisma.lead.findMany({
            where,
            include: {
                chats: true,
            },
            orderBy: {
                createdAt: 'desc',
            },
        });

        // Convert BigInt to string for JSON serialization
        const serializedLeads = leads.map((lead) => ({
            ...lead,
            user: undefined, // Remove user object to avoid circular refs
        }));

        return NextResponse.json(serializedLeads);
    } catch (error) {
        console.error('GET /api/leads error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch leads' },
            { status: 500 }
        );
    }
}

export async function POST(req: NextRequest) {
    try {
        const userId = req.headers.get('x-user-id');
        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await req.json();
        const { clientName, phone, areaSq, budget, status, avitoLink } = body;

        const lead = await prisma.lead.create({
            data: {
                userId: parseInt(userId),
                clientName,
                phone,
                areaSq: areaSq ? parseFloat(areaSq) : null,
                budget: budget ? parseFloat(budget) : null,
                status: status || 'NEW',
                avitoLink,
            },
        });

        // Create initial chat for this lead
        await prisma.chat.create({
            data: {
                leadId: lead.id,
                messages: [],
            },
        });

        return NextResponse.json(lead, { status: 201 });
    } catch (error) {
        console.error('POST /api/leads error:', error);
        return NextResponse.json(
            { error: 'Failed to create lead' },
            { status: 500 }
        );
    }
}

export async function PUT(req: NextRequest) {
    try {
        const userId = req.headers.get('x-user-id');
        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await req.json();
        const { id, ...updateData } = body;

        if (!id) {
            return NextResponse.json({ error: 'Lead ID required' }, { status: 400 });
        }

        // Verify lead belongs to user
        const existingLead = await prisma.lead.findFirst({
            where: {
                id: parseInt(id),
                userId: parseInt(userId),
            },
        });

        if (!existingLead) {
            return NextResponse.json({ error: 'Lead not found' }, { status: 404 });
        }

        const lead = await prisma.lead.update({
            where: { id: parseInt(id) },
            data: {
                ...updateData,
                areaSq: updateData.areaSq ? parseFloat(updateData.areaSq) : undefined,
                budget: updateData.budget ? parseFloat(updateData.budget) : undefined,
            },
        });

        return NextResponse.json(lead);
    } catch (error) {
        console.error('PUT /api/leads error:', error);
        return NextResponse.json(
            { error: 'Failed to update lead' },
            { status: 500 }
        );
    }
}
