import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

function quizHtmlFallback() {
    return {
        name: 'quiz-html-fallback',
        configureServer(server) {
            server.middlewares.use((req, _res, next) => {
                if (!req.url?.match(/^\/quiz-remont(?:\/|$|\?)/)) {
                    next();
                    return;
                }
                const queryIndex = req.url.indexOf('?');
                const query = queryIndex >= 0 ? req.url.slice(queryIndex) : '';
                req.url = `/quiz-remont.html${query}`;
                next();
            });
        },
    };
}

// https://vite.dev/config/
export default defineConfig({
    plugins: [react(), quizHtmlFallback()],
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    react: ['react', 'react-dom', 'react-router-dom'],
                    query: ['@tanstack/react-query', 'axios', 'axios-retry'],
                    charts: ['recharts'],
                    ui: ['lucide-react', 'sonner'],
                },
            },
        },
    },
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:8001',
                changeOrigin: true,
            },
        },
    },
});
