const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const PORT = process.env.PORT || 8080;
const BACKEND_PORT = 8000;

// MIME types for different file extensions
const mimeTypes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'text/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon'
};

const server = http.createServer((req, res) => {
    let filePath = req.url;

    // Handle API requests to backend
    if (filePath.startsWith('/stations/')) {
        // Proxy API requests to Python backend
        const options = {
            hostname: '127.0.0.1',
            port: BACKEND_PORT,
            path: filePath,
            method: req.method,
            headers: req.headers
        };

        const proxyReq = http.request(options, (proxyRes) => {
            res.writeHead(proxyRes.statusCode, proxyRes.headers);
            proxyRes.pipe(res);
        });

        proxyReq.on('error', (err) => {
            console.error('Proxy error:', err);
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
                response: "Sorry, I'm having trouble connecting to the AI servers right now.",
                action: "error",
                error: "Backend connection failed"
            }));
        });

        req.pipe(proxyReq);
        return;
    }

    // Serve welcome.html as the default page
    if (filePath === '/' || filePath === '/index.html') {
        res.writeHead(302, { 'Location': '/welcome.html' });
        res.end();
        return;
    }

    // Remove query parameters
    filePath = filePath.split('?')[0];

    // Security: prevent directory traversal
    if (filePath.includes('..')) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
        return;
    }

    // If no extension, try adding .html
    if (!path.extname(filePath)) {
        filePath += '.html';
    }

    const fullPath = path.join(__dirname, filePath);
    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';

    fs.readFile(fullPath, (err, data) => {
        if (err) {
            if (err.code === 'ENOENT') {
                // File not found, serve 404 page
                res.writeHead(404, { 'Content-Type': 'text/html' });
                res.end(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>404 - Page Not Found</title>
                        <style>
                            body {
                                font-family: Arial, sans-serif;
                                text-align: center;
                                padding: 50px;
                                background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #2d2d5f 100%);
                                color: white;
                                min-height: 100vh;
                                margin: 0;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                            }
                            .error-container {
                                background: rgba(255, 255, 255, 0.1);
                                padding: 2rem;
                                border-radius: 20px;
                                border: 1px solid rgba(0, 212, 255, 0.3);
                            }
                            h1 { color: #00d4ff; margin-bottom: 1rem; }
                            a { color: #00d4ff; text-decoration: none; }
                            a:hover { text-decoration: underline; }
                        </style>
                    </head>
                    <body>
                        <div class="error-container">
                            <h1>404 - Page Not Found</h1>
                            <p>The page you're looking for doesn't exist.</p>
                            <a href="/">← Back to Welcome Page</a>
                        </div>
                    </body>
                    </html>
                `);
            } else {
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('Internal Server Error');
            }
            return;
        }

        res.writeHead(200, {
            'Content-Type': contentType,
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        });
        res.end(data);
    });
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 PowerGrid EV Server running on http://localhost:${PORT}`);
    console.log(`📱 Welcome page: http://localhost:${PORT}/welcome.html`);
    console.log(`🏠 Main app: http://localhost:${PORT}/index.html`);
    console.log(`🎯 Guest dashboard: http://localhost:${PORT}/guest-dashboard.html`);
    console.log(`🤖 AI Backend proxy: http://localhost:${PORT}/stations/* → http://127.0.0.1:${BACKEND_PORT}`);

    // Auto-start Python backend
    console.log('🔄 Starting Python backend...');
    const backendProcess = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', BACKEND_PORT.toString(), '--reload'], {
        cwd: path.join(__dirname, 'backend'),
        stdio: 'inherit',
        detached: true
    });

    backendProcess.on('error', (err) => {
        console.error('❌ Failed to start Python backend:', err);
    });

    backendProcess.on('close', (code) => {
        console.log(`Python backend exited with code ${code}`);
    });

    // Handle server shutdown
    process.on('exit', () => {
        if (backendProcess && !backendProcess.killed) {
            backendProcess.kill();
        }
    });
});

// Handle server shutdown gracefully
process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.log('SIGINT received, shutting down gracefully');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});
