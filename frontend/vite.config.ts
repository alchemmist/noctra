import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// Build into web/dist, which the FastAPI backend serves at the app root.
// In dev, proxy API + WebSocket to the local backend on :8787.
export default defineConfig({
    plugins: [react()],
    base: './',
    build: {
        outDir: '../web/dist',
        emptyOutDir: true,
    },
    server: {
        proxy: {
            '/api': 'http://127.0.0.1:8787',
            '/ws': {target: 'ws://127.0.0.1:8787', ws: true},
        },
    },
});
