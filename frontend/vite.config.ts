import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
import { visualizer } from "rollup-plugin-visualizer";
import viteCompression from "vite-plugin-compression";

// Brief: Vite configuration optimized for USB deployment with code splitting and compression.

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === "production";
  const isUSBBuild = process.env.USB_BUILD === "true" || mode === "production";

  return {
    // Base path for assets - relative for USB deployment (works offline)
    base: isUSBBuild ? "./" : "/",
    
    server: {
      host: "::",
      port: 8080,
      // Proxy API requests to backend during development
      proxy: {
        "/api": {
          target: "http://localhost:8001",
          changeOrigin: true,
          secure: false,
        },
        "/health": {
          target: "http://localhost:8001",
          changeOrigin: true,
          secure: false,
        }
      }
    },

    plugins: [
      react(),
      mode === "development" && componentTagger(),
      
      // Production optimizations - gzip compression
      isProduction && viteCompression({
        algorithm: "gzip",
        ext: ".gz",
        threshold: 1024, // Only compress files > 1KB
        deleteOriginFile: false, // Keep original files (server handles compression)
      }),
      
      // Brotli compression (better than gzip)
      isProduction && viteCompression({
        algorithm: "brotliCompress",
        ext: ".br",
        threshold: 1024,
        deleteOriginFile: false,
      }),
      
      // Bundle analyzer for optimization
      isProduction && visualizer({
        filename: "dist/stats.html",
        open: false,
        gzipSize: true,
        brotliSize: true,
      }),
    ].filter(Boolean),

    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },

    // Build optimizations for USB deployment
    build: {
      // Output directory
      outDir: "dist",
      
      // Generate source maps only for development (reduces build size)
      sourcemap: !isProduction,
      
      // Optimize for USB deployment (ES2020 for better browser compatibility)
      target: "es2020",
      
      // Use terser for better minification in production
      minify: isProduction ? "terser" : false,
      
      // Increase chunk size warning limit for production builds
      chunkSizeWarningLimit: isProduction ? 500 : 1000,
      
      // Code splitting and tree shaking optimizations
      rollupOptions: {
        output: {
          // Manual chunk splitting for optimal caching and parallel loading
          manualChunks: (id) => {
            // Node modules - split by vendor
            if (id.includes('node_modules')) {
              // React core (usually loaded first)
              if (id.includes('react') || id.includes('react-dom') || id.includes('scheduler')) {
                return 'react-vendor';
              }
              
              // UI components library (Radix UI)
              if (id.includes('@radix-ui')) {
                return 'ui-vendor';
              }
              
              // Router
              if (id.includes('react-router')) {
                return 'router-vendor';
              }
              
              // State management and data fetching
              if (id.includes('@tanstack/react-query')) {
                return 'query-vendor';
              }
              
              // Form handling
              if (id.includes('react-hook-form') || id.includes('@hookform') || id.includes('zod')) {
                return 'form-vendor';
              }
              
              // Charts and visualization
              if (id.includes('recharts')) {
                return 'charts-vendor';
              }
              
              // Large utility libraries
              if (id.includes('date-fns')) {
                return 'utils-vendor';
              }
              
              // Other vendor packages
              return 'vendor';
            }
          },
          
          // Consistent chunk naming with content hashing for cache busting
          chunkFileNames: "assets/js/[name]-[hash].js",
          entryFileNames: "assets/js/[name]-[hash].js",
          assetFileNames: (assetInfo) => {
            const info = assetInfo.name?.split('.') || [];
            const ext = info[info.length - 1];
            if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext)) {
              return `assets/images/[name]-[hash].[ext]`;
            }
            if (/woff2?|eot|ttf|otf/i.test(ext)) {
              return `assets/fonts/[name]-[hash].[ext]`;
            }
            return `assets/[ext]/[name]-[hash].[ext]`;
          }
        }
      },
      
      // Terser options for aggressive minification
      terserOptions: isProduction ? {
        compress: {
          drop_console: true, // Remove console.log in production
          drop_debugger: true,
          pure_funcs: ['console.log', 'console.info', 'console.debug'], // Remove specific console methods
          passes: 2, // Multiple passes for better compression
        },
        mangle: {
          safari10: true, // Fix Safari 10 bugs
        },
        format: {
          comments: false, // Remove comments
        },
      } : undefined,
      
      // CSS code splitting
      cssCodeSplit: true,
      
      // Report compressed sizes
      reportCompressedSize: true,
    },

    // Environment variables
    define: {
      __USB_DEPLOYMENT__: JSON.stringify(isUSBBuild),
      __DEV_MODE__: JSON.stringify(!isProduction),
    },

    // Optimize dependencies
    optimizeDeps: {
      include: [
        "react",
        "react-dom",
        "react-router-dom",
        "@tanstack/react-query",
        "react-hook-form",
        "zod"
      ],
    },
  };
});
