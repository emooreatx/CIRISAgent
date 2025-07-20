"""
Main CIRISManager service.

Coordinates container management, crash loop detection, and provides
API for agent discovery and lifecycle management.
"""
import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional

from ciris_manager.core.container_manager import ContainerManager
from ciris_manager.core.watchdog import CrashLoopWatchdog
from ciris_manager.config.settings import CIRISManagerConfig

logger = logging.getLogger(__name__)


class CIRISManager:
    """Main manager service coordinating all components."""
    
    def __init__(self, config: Optional[CIRISManagerConfig] = None):
        """
        Initialize CIRISManager.
        
        Args:
            config: Configuration object, uses defaults if not provided
        """
        self.config = config or CIRISManagerConfig()
        
        # Validate docker-compose file exists
        compose_path = Path(self.config.docker.compose_file)
        if not compose_path.exists():
            raise FileNotFoundError(
                f"Docker compose file not found: {self.config.docker.compose_file}"
            )
            
        # Initialize components
        self.container_manager = ContainerManager(
            compose_file=self.config.docker.compose_file,
            interval=self.config.container_management.interval
        )
        
        self.watchdog = CrashLoopWatchdog(
            check_interval=self.config.watchdog.check_interval,
            crash_threshold=self.config.watchdog.crash_threshold,
            crash_window=self.config.watchdog.crash_window
        )
        
        self._running = False
        self._shutdown_event = asyncio.Event()
        
    async def start(self):
        """Start all manager services."""
        logger.info("Starting CIRISManager...")
        
        self._running = True
        
        # Start components
        await self.container_manager.start()
        await self.watchdog.start()
        
        # Start API server if configured
        if hasattr(self.config, 'api') and self.config.api:
            asyncio.create_task(self._start_api_server())
        
        logger.info("CIRISManager started successfully")
    
    async def _start_api_server(self):
        """Start the FastAPI server for CIRISManager API."""
        try:
            from fastapi import FastAPI
            import uvicorn
            from .api import router
            
            app = FastAPI(title="CIRISManager API", version="1.0.0")
            app.include_router(router)
            
            config = uvicorn.Config(
                app,
                host=self.config.api.host,
                port=self.config.api.port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            
            logger.info(f"Starting API server on {self.config.api.host}:{self.config.api.port}")
            await server.serve()
            
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
        
    async def stop(self):
        """Stop all manager services."""
        logger.info("Stopping CIRISManager...")
        
        self._running = False
        
        # Stop components
        await self.container_manager.stop()
        await self.watchdog.stop()
        
        # TODO: Stop API server when implemented
        
        logger.info("CIRISManager stopped")
        
    async def run(self):
        """Run the manager until shutdown signal."""
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        
        def handle_signal():
            logger.info("Shutdown signal received")
            self._shutdown_event.set()
            
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_signal)
            
        try:
            # Start services
            await self.start()
            
            # Wait for shutdown
            await self._shutdown_event.wait()
            
        finally:
            # Stop services
            await self.stop()
            
    def get_status(self) -> dict:
        """Get current manager status."""
        return {
            'running': self._running,
            'config': self.config.model_dump(),
            'watchdog_status': self.watchdog.get_status(),
            'components': {
                'container_manager': 'running' if self._running else 'stopped',
                'watchdog': 'running' if self._running else 'stopped',
                'api_server': 'not_implemented'
            }
        }


async def main():
    """Main entry point for CIRISManager."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    config_path = "/etc/ciris-manager/config.yml"
    config = CIRISManagerConfig.from_file(config_path)
    
    # Create and run manager
    manager = CIRISManager(config)
    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())