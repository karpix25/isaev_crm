import { NextRequest, NextResponse } from 'next/server';
import jwt from 'jsonwebtoken';
import { prisma } from '@/lib/prisma';
import { verifyTelegramWebAppData } from '@/lib/telegram';

export async function POST(req: NextRequest) {
    try {
        const { initData } = await req.json();

        if (!initData) {
            return NextResponse.json(
                { error: 'Missing initData' },
                { status: 400 }
            );
        }

        const botToken = process.env.TELEGRAM_BOT_TOKEN;
        if (!botToken) {
            return NextResponse.json(
                { error: 'Server configuration error' },
                { status: 500 }
            );
        }

        // Verify Telegram data
        const verification = verifyTelegramWebAppData(initData, botToken);
        if (!verification.valid || !verification.data) {
            return NextResponse.json(
                { error: 'Invalid Telegram data' },
                { status: 401 }
            );
        }

        const { id: tgId, firstName, lastName, username } = verification.data;

        // Upsert user in database
        const user = await prisma.user.upsert({
            where: { tgId: BigInt(tgId) },
            update: {
                name: `${firstName} ${lastName || ''}`.trim() || username || 'User',
            },
            create: {
                tgId: BigInt(tgId),
                name: `${firstName} ${lastName || ''}`.trim() || username || 'User',
                role: 'manager',
            },
        });

        // Generate JWT token
        const jwtSecret = process.env.JWT_SECRET || 'default-secret-change-me';
        const token = jwt.sign(
            {
                userId: user.id,
                tgId: user.tgId.toString(),
                role: user.role,
            },
            jwtSecret,
            { expiresIn: '30d' }
        );

        return NextResponse.json({
            token,
            user: {
                id: user.id,
                name: user.name,
                role: user.role,
            },
        });
    } catch (error) {
        console.error('Auth error:', error);
        return NextResponse.json(
            { error: 'Authentication failed' },
            { status: 500 }
        );
    }
}
