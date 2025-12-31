import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // All API calls go to unified FastAPI server on port 5000
      // FastAPI handles routing: specific /api/* routes go to FastAPI, others go to Flask
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        // Don't rewrite - FastAPI handles routing internally
      }
    }
  },
  optimizeDeps: {
    esbuildOptions: {
      // Optimize dependencies
      target: 'es2020',
    }
  },
  esbuild: {
    // Optimize esbuild for faster builds
    target: 'es2020',
    // Drop console and debugger in production
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
    // Legal comments for production
    legalComments: 'none',
  },
  build: {
    // Optimize build output
    target: 'es2020',
    minify: 'esbuild', // Use esbuild for minification (faster than terser)
    sourcemap: false, // Disable sourcemaps for faster builds (enable if needed for debugging)
    rollupOptions: {
      output: {
        // Optimize chunk splitting
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        }
      }
    }
  }
})

