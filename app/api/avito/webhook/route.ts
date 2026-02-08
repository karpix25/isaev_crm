import { NextRequest, NextResponse } from 'next/server';

/**
 * POST /api/avito/webhook
 * Receive Avito lead notifications and forward to n8n
 */
export async function POST(req: NextRequest) {
    try {
        const body = await req.json();

        // Forward to n8n workflow
        const n8nUrl = process.env.N8N_WEBHOOK_URL;
        if (n8nUrl) {
            await fetch(n8nUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        }

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Avito webhook error:', error);
        return NextResponse.json(
            { error: 'Webhook processing failed' },
            { status: 500 }
        );
    }
}
