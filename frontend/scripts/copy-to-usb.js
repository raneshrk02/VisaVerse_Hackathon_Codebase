#!/usr/bin/env node

/**
 * Post-build script to copy React build to USB deployment directory
 * This script runs after `vite build` to prepare the frontend for USB deployment
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const BUILD_DIR = path.join(__dirname, '..', 'dist');
const USB_FRONTEND_DIR = path.join(__dirname, '..', '..', 'usb-deploy', 'frontend');
const USB_BUILD_DIR = path.join(USB_FRONTEND_DIR, 'build');

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(message, color = colors.reset) {
  console.log(`${color}${message}${colors.reset}`);
}

function logStep(step, message) {
  log(`[${step}] ${message}`, colors.blue);
}

function logSuccess(message) {
  log(`✅ ${message}`, colors.green);
}

function logError(message) {
  log(`❌ ${message}`, colors.red);
}

function logWarning(message) {
  log(`⚠️  ${message}`, colors.yellow);
}

/**
 * Copy directory recursively
 */
function copyDir(src, dest) {
  if (!fs.existsSync(src)) {
    throw new Error(`Source directory does not exist: ${src}`);
  }

  // Create destination directory
  fs.mkdirSync(dest, { recursive: true });

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * Get directory size in MB
 */
function getDirSize(dirPath) {
  let totalSize = 0;

  function calculateSize(currentPath) {
    const stats = fs.statSync(currentPath);
    
    if (stats.isDirectory()) {
      const files = fs.readdirSync(currentPath);
      files.forEach(file => {
        calculateSize(path.join(currentPath, file));
      });
    } else {
      totalSize += stats.size;
    }
  }

  calculateSize(dirPath);
  return (totalSize / (1024 * 1024)).toFixed(2); // Convert to MB
}

/**
 * Create a simple HTTP server script for serving the frontend
 */
function createServerScript() {
  const serverScript = `#!/usr/bin/env node

/**
 * Simple HTTP server for serving the SAGE frontend in USB deployment
 * This server serves the built React application
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.FRONTEND_PORT || 8080;
const BUILD_DIR = path.join(__dirname, 'build');

// MIME types
const mimeTypes = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.wav': 'audio/wav',
  '.mp4': 'video/mp4',
  '.woff': 'application/font-woff',
  '.ttf': 'application/font-ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.otf': 'application/font-otf',
  '.wasm': 'application/wasm'
};

function getContentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return mimeTypes[ext] || 'application/octet-stream';
}

const server = http.createServer((req, res) => {
  // Parse URL
  const parsedUrl = url.parse(req.url);
  let pathname = parsedUrl.pathname;

  // Security: prevent directory traversal
  pathname = pathname.replace(/\\.\\./g, '');

  // Default to index.html for SPA routing
  if (pathname === '/' || pathname === '') {
    pathname = '/index.html';
  }

  // If no extension, assume it's a route and serve index.html
  if (!path.extname(pathname)) {
    pathname = '/index.html';
  }

  const filePath = path.join(BUILD_DIR, pathname);

  // Check if file exists
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if (err) {
      // File not found, serve index.html for SPA routing
      const indexPath = path.join(BUILD_DIR, 'index.html');
      fs.readFile(indexPath, (err, content) => {
        if (err) {
          res.writeHead(500);
          res.end('Server Error');
          return;
        }
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(content, 'utf-8');
      });
      return;
    }

    // Serve the file
    fs.readFile(filePath, (err, content) => {
      if (err) {
        res.writeHead(500);
        res.end('Server Error');
        return;
      }

      const contentType = getContentType(filePath);
      res.writeHead(200, { 
        'Content-Type': contentType,
        'Cache-Control': contentType.includes('text/html') ? 'no-cache' : 'public, max-age=31536000'
      });
      res.end(content, 'utf-8');
    });
  });
});

server.listen(PORT, () => {
  console.log(\`🚀 SAGE Frontend server running at http://localhost:\${PORT}\`);
  console.log(\`📁 Serving files from: \${BUILD_DIR}\`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('\\n🛑 Shutting down frontend server...');
  server.close(() => {
    console.log('✅ Frontend server stopped');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('\\n🛑 Shutting down frontend server...');
  server.close(() => {
    console.log('✅ Frontend server stopped');
    process.exit(0);
  });
});
`;

  const serverPath = path.join(USB_FRONTEND_DIR, 'server.js');
  fs.writeFileSync(serverPath, serverScript);
  
  // Make executable on Unix systems
  try {
    fs.chmodSync(serverPath, '755');
  } catch (err) {
    // Ignore chmod errors on Windows
  }

  logSuccess(`Created frontend server script: ${serverPath}`);
}

/**
 * Create startup script for the frontend
 */
function createStartupScript() {
  const startupScript = `#!/bin/bash

# SAGE Frontend Startup Script for USB Deployment
# This script starts the frontend server for the portable SAGE system

set -e

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
SERVER_SCRIPT="$SCRIPT_DIR/server.js"

echo -e "\${BLUE}🚀 Starting SAGE Frontend Server...\${NC}"

# Check if build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "\${RED}❌ Build directory not found: $BUILD_DIR\${NC}"
    echo "Please run the build process first:"
    echo "  cd react_frontend"
    echo "  npm run build:usb"
    exit 1
fi

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo -e "\${RED}❌ Node.js is not installed or not in PATH\${NC}"
    echo "Please install Node.js or use the portable Node.js runtime"
    exit 1
fi

# Find available port
FRONTEND_PORT=8080
while netstat -an 2>/dev/null | grep -q ":$FRONTEND_PORT "; do
    FRONTEND_PORT=$((FRONTEND_PORT + 1))
done

echo -e "\${GREEN}✅ Using port: $FRONTEND_PORT\${NC}"

# Set environment variable
export FRONTEND_PORT=$FRONTEND_PORT

# Start the server
echo -e "\${BLUE}📁 Serving from: $BUILD_DIR\${NC}"
echo -e "\${GREEN}🌐 Frontend will be available at: http://localhost:$FRONTEND_PORT\${NC}"
echo -e "\${YELLOW}Press Ctrl+C to stop the server\${NC}"
echo

# Start the Node.js server
node "$SERVER_SCRIPT"
`;

  const startupPath = path.join(USB_FRONTEND_DIR, 'start-frontend.sh');
  fs.writeFileSync(startupPath, startupScript);
  
  // Make executable
  try {
    fs.chmodSync(startupPath, '755');
  } catch (err) {
    // Ignore chmod errors on Windows
  }

  logSuccess(`Created frontend startup script: ${startupPath}`);
}

/**
 * Main execution
 */
function main() {
  log('🔧 SAGE USB Frontend Deployment', colors.magenta);
  log('=====================================', colors.magenta);

  try {
    // Step 1: Verify build directory exists
    logStep('1', 'Checking build directory...');
    if (!fs.existsSync(BUILD_DIR)) {
      throw new Error(`Build directory not found: ${BUILD_DIR}. Run 'npm run build' first.`);
    }
    logSuccess(`Build directory found: ${BUILD_DIR}`);

    // Step 2: Create USB frontend directory
    logStep('2', 'Creating USB frontend directory...');
    fs.mkdirSync(USB_FRONTEND_DIR, { recursive: true });
    logSuccess(`USB frontend directory created: ${USB_FRONTEND_DIR}`);

    // Step 3: Clean existing build in USB directory
    logStep('3', 'Cleaning existing USB build...');
    if (fs.existsSync(USB_BUILD_DIR)) {
      fs.rmSync(USB_BUILD_DIR, { recursive: true, force: true });
      logSuccess('Existing USB build cleaned');
    } else {
      log('No existing USB build to clean');
    }

    // Step 4: Copy build to USB directory
    logStep('4', 'Copying build to USB directory...');
    copyDir(BUILD_DIR, USB_BUILD_DIR);
    logSuccess(`Build copied to: ${USB_BUILD_DIR}`);

    // Step 5: Create server script
    logStep('5', 'Creating frontend server script...');
    createServerScript();

    // Step 6: Create startup script
    logStep('6', 'Creating startup script...');
    createStartupScript();

    // Step 7: Display summary
    logStep('7', 'Deployment summary');
    const buildSize = getDirSize(USB_BUILD_DIR);
    log(`📦 Build size: ${buildSize} MB`, colors.cyan);
    log(`📁 USB frontend location: ${USB_FRONTEND_DIR}`, colors.cyan);
    log(`🚀 To start frontend: cd usb-deploy/frontend && ./start-frontend.sh`, colors.cyan);

    logSuccess('Frontend deployment completed successfully!');

  } catch (error) {
    logError(`Deployment failed: ${error.message}`);
    process.exit(1);
  }
}

// Run the script
main();

export { main, copyDir, getDirSize };