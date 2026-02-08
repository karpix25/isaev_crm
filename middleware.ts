import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import jwt from 'jsonwebtoken';

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Skip auth for public routes
    if (
        pathname.startsWith('/api/auth') ||
        pathname === '/login' ||
        pathname === '/' ||
        pathname.startsWith('/_next') ||
        pathname.startsWith('/public')
    ) {
        return NextResponse.next();
    }

    // Check for JWT token
    const token = request.headers.get('authorization')?.replace('Bearer ', '') ||
        request.cookies.get('token')?.value;

    if (!token) {
        if (pathname.startsWith('/api')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }
        return NextResponse.redirect(new URL('/login', request.url));
    }

    try {
        const jwtSecret = process.env.JWT_SECRET || 'default-secret-change-me';
        const decoded = jwt.verify(token, jwtSecret) as {
            userId: number;
            tgId: string;
            role: string;
        };

        // Add user info to request headers for API routes
        const requestHeaders = new Headers(request.headers);
        requestHeaders.set('x-user-id', decoded.userId.toString());
        requestHeaders.set('x-user-role', decoded.role);

        return NextResponse.next({
            request: {
                headers: requestHeaders,
            },
        });
    } catch (error) {
        console.error('JWT verification failed:', error);
        if (pathname.startsWith('/api')) {
            return NextResponse.json({ error: 'Invalid token' }, { status: 401 });
        }
        return NextResponse.redirect(new URL('/login', request.url));
    }
}

export const config = {
    matcher: ['/dashboard/:path*', '/lead/:path*', '/api/leads/:path*', '/api/rag/:path*'],
};
