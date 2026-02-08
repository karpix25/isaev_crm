import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

/**
 * POST /api/rag/embed
 * Embed company documents into pgvector for RAG
 */
export async function POST(req: NextRequest) {
    try {
        const { documents } = await req.json();

        if (!documents || !Array.isArray(documents)) {
            return NextResponse.json(
                { error: 'Invalid documents array' },
                { status: 400 }
            );
        }

        const openrouterKey = process.env.OPENROUTER_API_KEY;
        if (!openrouterKey) {
            return NextResponse.json(
                { error: 'OpenRouter API key not configured' },
                { status: 500 }
            );
        }

        // Chunk and embed each document
        const embeddedChunks = [];
        for (const doc of documents) {
            // Simple chunking: split by paragraphs (max 500 chars)
            const chunks = chunkText(doc.content, 500);

            for (const chunk of chunks) {
                // Call OpenRouter embeddings API
                const embeddingRes = await fetch(
                    'https://openrouter.ai/api/v1/embeddings',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: `Bearer ${openrouterKey}`,
                        },
                        body: JSON.stringify({
                            model: 'openai/text-embedding-ada-002',
                            input: chunk,
                        }),
                    }
                );

                if (!embeddingRes.ok) {
                    console.error('OpenRouter embedding failed:', await embeddingRes.text());
                    continue;
                }

                const embeddingData = await embeddingRes.json();
                const embedding = embeddingData.data[0].embedding;

                // Store in database (note: pgvector requires raw SQL for vector insertion)
                await prisma.$executeRaw`
          INSERT INTO "RagDoc" (chunk, embedding)
          VALUES (${chunk}, ${embedding}::vector)
        `;

                embeddedChunks.push({ chunk, embeddingLength: embedding.length });
            }
        }

        return NextResponse.json({
            success: true,
            chunksEmbedded: embeddedChunks.length,
        });
    } catch (error) {
        console.error('POST /api/rag/embed error:', error);
        return NextResponse.json(
            { error: 'Failed to embed documents' },
            { status: 500 }
        );
    }
}

/**
 * GET /api/rag/query
 * Query RAG documents by semantic similarity
 */
export async function GET(req: NextRequest) {
    try {
        const { searchParams } = new URL(req.url);
        const query = searchParams.get('q');
        const limit = parseInt(searchParams.get('limit') || '5');

        if (!query) {
            return NextResponse.json({ error: 'Query required' }, { status: 400 });
        }

        const openrouterKey = process.env.OPENROUTER_API_KEY;
        if (!openrouterKey) {
            return NextResponse.json(
                { error: 'OpenRouter API key not configured' },
                { status: 500 }
            );
        }

        // Embed the query
        const embeddingRes = await fetch(
            'https://openrouter.ai/api/v1/embeddings',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${openrouterKey}`,
                },
                body: JSON.stringify({
                    model: 'openai/text-embedding-ada-002',
                    input: query,
                }),
            }
        );

        if (!embeddingRes.ok) {
            return NextResponse.json(
                { error: 'Failed to embed query' },
                { status: 500 }
            );
        }

        const embeddingData = await embeddingRes.json();
        const queryEmbedding = embeddingData.data[0].embedding;

        // Query pgvector for similar chunks
        const results: any[] = await prisma.$queryRaw`
      SELECT id, chunk, 1 - (embedding <=> ${queryEmbedding}::vector) AS similarity
      FROM "RagDoc"
      ORDER BY embedding <=> ${queryEmbedding}::vector
      LIMIT ${limit}
    `;

        return NextResponse.json({
            query,
            results: results.map((r) => ({
                chunk: r.chunk,
                similarity: r.similarity,
            })),
        });
    } catch (error) {
        console.error('GET /api/rag/query error:', error);
        return NextResponse.json(
            { error: 'Failed to query RAG' },
            { status: 500 }
        );
    }
}

function chunkText(text: string, maxLength: number): string[] {
    const chunks: string[] = [];
    const paragraphs = text.split('\n\n');

    let currentChunk = '';
    for (const para of paragraphs) {
        if (currentChunk.length + para.length > maxLength) {
            if (currentChunk) chunks.push(currentChunk.trim());
            currentChunk = para;
        } else {
            currentChunk += '\n\n' + para;
        }
    }

    if (currentChunk) chunks.push(currentChunk.trim());
    return chunks.filter((c) => c.length > 0);
}
