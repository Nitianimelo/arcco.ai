import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(() => {
  return {
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy: {
        '/api/agent': {
          target: 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        },
        '/api/admin': {
          target: 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        },
        '/health': {
          target: 'http://localhost:8001',
          changeOrigin: true,
          secure: false,
        },
      },
    },
    plugins: [
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      }
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom'],
            'vendor-supabase': ['@supabase/supabase-js'],
            'vendor-markdown': ['react-markdown', 'rehype-highlight'],
            'vendor-pdf': ['pdfjs-dist', 'jspdf', 'pdfkit'],
            'vendor-office': ['xlsx', 'mammoth'],
            'vendor-ui': ['lucide-react', 'date-fns'],
          }
        }
      }
    }
  };
});
