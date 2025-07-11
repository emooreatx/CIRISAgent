"""Simple web UI for CIRIS Wyoming Bridge status and configuration."""
import aiohttp
import asyncio
import logging
from aiohttp import web
import json

logger = logging.getLogger(__name__)

class WebUI:
    def __init__(self, config, port=8099):
        self.config = config
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        self.stats = {
            "transcriptions": 0,
            "ciris_responses": 0,
            "errors": 0,
            "last_transcript": None,
            "last_response": None
        }
    
    def setup_routes(self):
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/stats', self.get_stats)
        self.app.router.add_get('/api/config', self.get_config)
        self.app.router.add_post('/api/test', self.test_ciris)
    
    async def index(self, request):
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>CIRIS Wyoming Bridge</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .status { background: #f0f0f0; padding: 10px; border-radius: 5px; }
                .error { color: red; }
                .success { color: green; }
            </style>
        </head>
        <body>
            <h1>CIRIS Wyoming Bridge</h1>
            <div class="status">
                <h2>Status</h2>
                <p>Bridge is running on port 10300</p>
                <p id="stats">Loading stats...</p>
            </div>
            
            <h2>Configuration</h2>
            <div id="config">Loading...</div>
            
            <h2>Test CIRIS Connection</h2>
            <input type="text" id="testInput" placeholder="Test message" style="width: 300px;">
            <button onclick="testCiris()">Test</button>
            <div id="testResult"></div>
            
            <h2>Home Assistant Setup</h2>
            <ol>
                <li>This addon provides STT (Speech-to-Text) using ciris</li>
                <li>To use CIRIS for conversations, you need to install the CIRIS conversation agent</li>
                <li>Unfortunately, Home Assistant addons cannot register as conversation agents</li>
                <li>For now, CIRIS will respond but HA will say "device not found"</li>
            </ol>
            
            <script>
                async function loadStats() {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    document.getElementById('stats').innerHTML = `
                        Transcriptions: ${stats.transcriptions}<br>
                        CIRIS Responses: ${stats.ciris_responses}<br>
                        Errors: ${stats.errors}<br>
                        Last: "${stats.last_transcript || 'None'}" → "${stats.last_response || 'None'}"
                    `;
                }
                
                async function loadConfig() {
                    const response = await fetch('/api/config');
                    const config = await response.json();
                    document.getElementById('config').innerHTML = `
                        <pre>${JSON.stringify(config, null, 2)}</pre>
                    `;
                }
                
                async function testCiris() {
                    const input = document.getElementById('testInput').value;
                    const result = document.getElementById('testResult');
                    result.innerHTML = 'Testing...';
                    
                    try {
                        const response = await fetch('/api/test', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({message: input})
                        });
                        const data = await response.json();
                        result.innerHTML = `<div class="success">Response: ${data.response}</div>`;
                    } catch (e) {
                        result.innerHTML = `<div class="error">Error: ${e.message}</div>`;
                    }
                }
                
                loadStats();
                loadConfig();
                setInterval(loadStats, 5000);
            </script>
        </body>
        </html>
        '''
        return web.Response(text=html, content_type='text/html')
    
    async def get_stats(self, request):
        return web.json_response(self.stats)
    
    async def get_config(self, request):
        return web.json_response({
            "ciris_url": self.config.ciris.api_url,
            "stt_provider": self.config.stt.provider,
            "tts_provider": self.config.tts.provider,
            "timeout": self.config.ciris.timeout
        })
    
    async def test_ciris(self, request):
        data = await request.json()
        message = data.get('message', 'Hello')
        
        # Test CIRIS connection
        from .ciris_sdk_client import CIRISClient
        client = CIRISClient(self.config.ciris)
        
        try:
            await client.voice_client.initialize()
            response = await client.send_message(message)
            await client.voice_client.close()
            
            return web.json_response({
                "success": True,
                "response": response.get("content", "No response")
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    def update_stats(self, event_type, data=None):
        """Update statistics from the bridge."""
        if event_type == "transcription":
            self.stats["transcriptions"] += 1
            self.stats["last_transcript"] = data
        elif event_type == "ciris_response":
            self.stats["ciris_responses"] += 1
            self.stats["last_response"] = data
        elif event_type == "error":
            self.stats["errors"] += 1
    
    async def start(self):
        """Start the web UI."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Web UI started on port {self.port}")