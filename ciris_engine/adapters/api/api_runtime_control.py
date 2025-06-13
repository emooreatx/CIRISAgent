"""API endpoints for runtime control - processor control, adapter management, and configuration."""
import logging
import json
from aiohttp import web
from typing import Any, Optional

from ciris_engine.runtime.runtime_control import RuntimeControlService
from ciris_engine.schemas.runtime_control_schemas import (
    ProcessorControlRequest, AdapterLoadRequest, AdapterUnloadRequest,
    ConfigUpdateRequest, ConfigGetRequest, ProfileReloadRequest,
    ConfigValidationRequest, EnvVarSetRequest, EnvVarDeleteRequest,
    ConfigBackupRequest, ConfigRestoreRequest
)

logger = logging.getLogger(__name__)


class APIRuntimeControlRoutes:
    """API routes for runtime control operations."""

    def __init__(self, runtime_control_service: RuntimeControlService) -> None:
        self.runtime_control = runtime_control_service

    def register(self, app: web.Application) -> None:
        """Register all runtime control endpoints."""
        
        # Processor Control
        app.router.add_post('/v1/runtime/processor/step', self._handle_single_step)
        app.router.add_post('/v1/runtime/processor/pause', self._handle_pause_processing)
        app.router.add_post('/v1/runtime/processor/resume', self._handle_resume_processing)
        app.router.add_post('/v1/runtime/processor/shutdown', self._handle_shutdown_runtime)
        app.router.add_get('/v1/runtime/processor/queue', self._handle_get_queue_status)
        
        # Adapter Management
        app.router.add_post('/v1/runtime/adapters', self._handle_load_adapter)
        app.router.add_delete('/v1/runtime/adapters/{adapter_id}', self._handle_unload_adapter)
        app.router.add_get('/v1/runtime/adapters', self._handle_list_adapters)
        app.router.add_get('/v1/runtime/adapters/{adapter_id}', self._handle_get_adapter_info)
        
        # Configuration Management
        app.router.add_get('/v1/runtime/config', self._handle_get_config)
        app.router.add_put('/v1/runtime/config', self._handle_update_config)
        app.router.add_post('/v1/runtime/config/validate', self._handle_validate_config)
        app.router.add_post('/v1/runtime/config/reload', self._handle_reload_config)
        
        # Agent Profile Management
        app.router.add_get('/v1/runtime/profiles', self._handle_list_profiles)
        app.router.add_post('/v1/runtime/profiles/{profile_name}/load', self._handle_load_profile)
        app.router.add_get('/v1/runtime/profiles/{profile_name}', self._handle_get_profile)
        app.router.add_post('/v1/runtime/profiles', self._handle_create_profile)
        app.router.add_put('/v1/runtime/profiles/{profile_name}', self._handle_update_profile)
        app.router.add_delete('/v1/runtime/profiles/{profile_name}', self._handle_delete_profile)
        
        # Environment Variable Management
        app.router.add_get('/v1/runtime/env', self._handle_list_env_vars)
        app.router.add_put('/v1/runtime/env/{var_name}', self._handle_set_env_var)
        app.router.add_delete('/v1/runtime/env/{var_name}', self._handle_delete_env_var)
        
        # Configuration Backup/Restore
        app.router.add_post('/v1/runtime/config/backup', self._handle_backup_config)
        app.router.add_post('/v1/runtime/config/restore', self._handle_restore_config)
        app.router.add_get('/v1/runtime/config/backups', self._handle_list_config_backups)
        
        # Runtime Status
        app.router.add_get('/v1/runtime/status', self._handle_get_runtime_status)
        app.router.add_get('/v1/runtime/snapshot', self._handle_get_runtime_snapshot)
        
        # Service Registry Management
        app.router.add_get('/v1/runtime/services', self._handle_list_services)
        app.router.add_get('/v1/runtime/services/health', self._handle_get_service_health)
        app.router.add_get('/v1/runtime/services/selection-logic', self._handle_get_service_selection_explanation)
        app.router.add_post('/v1/runtime/services/circuit-breakers/reset', self._handle_reset_circuit_breakers)
        app.router.add_put('/v1/runtime/services/{provider_name}/priority', self._handle_update_service_priority)

    # Processor Control Endpoints
    async def _handle_single_step(self, request: web.Request) -> web.Response:
        """Execute a single processing step."""
        try:
            result = await self.runtime_control.single_step()
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error executing single step: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_pause_processing(self, request: web.Request) -> web.Response:
        """Pause the processor."""
        try:
            result = await self.runtime_control.pause_processing()
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error pausing processing: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_resume_processing(self, request: web.Request) -> web.Response:
        """Resume the processor."""
        try:
            result = await self.runtime_control.resume_processing()
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error resuming processing: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_shutdown_runtime(self, request: web.Request) -> web.Response:
        """Shutdown the entire runtime system."""
        try:
            # Get optional reason from request body
            reason = "API shutdown request"
            try:
                data = await request.json()
                reason = data.get("reason", reason)
            except:
                pass  # Use default reason if no JSON body
            
            result = await self.runtime_control.shutdown_runtime(reason)
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error shutting down runtime: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_queue_status(self, request: web.Request) -> web.Response:
        """Get processor queue status."""
        try:
            status = await self.runtime_control.get_queue_status()
            return web.json_response(status, status=200)
        except Exception as e:
            logger.error(f"Error getting queue status: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Adapter Management Endpoints
    async def _handle_load_adapter(self, request: web.Request) -> web.Response:
        """Load a new adapter instance."""
        try:
            data = await request.json()
            load_request = AdapterLoadRequest(**data)
            
            result = await self.runtime_control.load_adapter(
                load_request.adapter_type,
                load_request.adapter_id,
                load_request.config,
                load_request.auto_start
            )
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except ValueError as e:
            logger.warning(f"Invalid adapter load request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error loading adapter: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_unload_adapter(self, request: web.Request) -> web.Response:
        """Unload an adapter instance."""
        try:
            adapter_id = request.match_info['adapter_id']
            force = request.query.get('force', 'false').lower() == 'true'
            
            result = await self.runtime_control.unload_adapter(adapter_id, force)
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error unloading adapter: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_list_adapters(self, request: web.Request) -> web.Response:
        """List all loaded adapters."""
        try:
            adapters = await self.runtime_control.list_adapters()
            return web.json_response(adapters, status=200)
        except Exception as e:
            logger.error(f"Error listing adapters: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_adapter_info(self, request: web.Request) -> web.Response:
        """Get information about a specific adapter."""
        try:
            adapter_id = request.match_info['adapter_id']
            adapter_info = await self.runtime_control.get_adapter_info(adapter_id)
            
            if adapter_info:
                if hasattr(adapter_info, 'model_dump'):
                    return web.json_response(adapter_info.model_dump(mode="json"), status=200)
                else:
                    return web.json_response(adapter_info, status=200)
            else:
                return web.json_response({"error": "Adapter not found"}, status=404)
        except Exception as e:
            logger.error(f"Error getting adapter info: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Configuration Management Endpoints
    async def _handle_get_config(self, request: web.Request) -> web.Response:
        """Get configuration values."""
        try:
            path = request.query.get('path')
            include_sensitive = request.query.get('include_sensitive', 'false').lower() == 'true'
            
            result = await self.runtime_control.get_config(path, include_sensitive)
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error getting config: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_update_config(self, request: web.Request) -> web.Response:
        """Update configuration values."""
        try:
            data = await request.json()
            update_request = ConfigUpdateRequest(**data)
            
            result = await self.runtime_control.update_config(
                update_request.path,
                update_request.value,
                update_request.scope,
                update_request.validation_level,
                update_request.reason
            )
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except ValueError as e:
            logger.warning(f"Invalid config update request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error updating config: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_validate_config(self, request: web.Request) -> web.Response:
        """Validate configuration data."""
        try:
            data = await request.json()
            validation_request = ConfigValidationRequest(**data)
            
            result = await self.runtime_control.validate_config(
                validation_request.config_data,
                validation_request.config_path
            )
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except ValueError as e:
            logger.warning(f"Invalid config validation request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error validating config: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_reload_config(self, request: web.Request) -> web.Response:
        """Reload configuration from files."""
        try:
            result = await self.runtime_control.reload_config()
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error reloading config: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Agent Profile Management Endpoints
    async def _handle_list_profiles(self, request: web.Request) -> web.Response:
        """List all available agent profiles."""
        try:
            profiles = await self.runtime_control.list_agent_profiles()
            return web.json_response(profiles, status=200)
        except Exception as e:
            logger.error(f"Error listing profiles: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_load_profile(self, request: web.Request) -> web.Response:
        """Load an agent profile."""
        try:
            profile_name = request.match_info['profile_name']
            data = await request.json() if request.can_read_body else {}
            
            reload_request = ProfileReloadRequest(
                profile_name=profile_name,
                **data
            )
            
            result = await self.runtime_control.load_agent_profile(reload_request)
            if hasattr(result, 'model_dump'):
                return web.json_response(result.model_dump(mode="json"), status=200)
            else:
                return web.json_response(result, status=200)
        except ValueError as e:
            logger.warning(f"Invalid profile load request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error loading profile: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_profile(self, request: web.Request) -> web.Response:
        """Get information about a specific agent profile."""
        try:
            profile_name = request.match_info['profile_name']
            profile_info = await self.runtime_control.get_agent_profile(profile_name)
            
            if profile_info:
                if hasattr(profile_info, 'model_dump'):
                    return web.json_response(profile_info.model_dump(mode="json"), status=200)
                else:
                    return web.json_response(profile_info, status=200)
            else:
                return web.json_response({"error": "Profile not found"}, status=404)
        except Exception as e:
            logger.error(f"Error getting profile info: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_create_profile(self, request: web.Request) -> web.Response:
        """Create a new agent profile."""
        try:
            data = await request.json()
            # TODO: Implement profile creation logic in runtime control service
            return web.json_response({"message": "Profile creation not yet implemented"}, status=501)
        except Exception as e:
            logger.error(f"Error creating profile: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_update_profile(self, request: web.Request) -> web.Response:
        """Update an agent profile."""
        try:
            profile_name = request.match_info['profile_name']
            data = await request.json()
            # TODO: Implement profile update logic in runtime control service
            return web.json_response({"message": "Profile update not yet implemented"}, status=501)
        except Exception as e:
            logger.error(f"Error updating profile: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_delete_profile(self, request: web.Request) -> web.Response:
        """Delete an agent profile."""
        try:
            profile_name = request.match_info['profile_name']
            # TODO: Implement profile deletion logic in runtime control service
            return web.json_response({"message": "Profile deletion not yet implemented"}, status=501)
        except Exception as e:
            logger.error(f"Error deleting profile: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Environment Variable Management Endpoints
    async def _handle_list_env_vars(self, request: web.Request) -> web.Response:
        """List environment variables."""
        try:
            include_sensitive = request.query.get('include_sensitive', 'false').lower() == 'true'
            env_vars = await self.runtime_control.list_env_vars(include_sensitive)
            return web.json_response(env_vars, status=200)
        except Exception as e:
            logger.error(f"Error listing env vars: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_set_env_var(self, request: web.Request) -> web.Response:
        """Set an environment variable."""
        try:
            var_name = request.match_info['var_name']
            data = await request.json()
            
            env_request = EnvVarSetRequest(
                name=var_name,
                **data
            )
            
            result = await self.runtime_control.set_env_var(env_request)
            return web.json_response(result.model_dump(mode="json"), status=200)
        except ValueError as e:
            logger.warning(f"Invalid env var set request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error setting env var: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_delete_env_var(self, request: web.Request) -> web.Response:
        """Delete an environment variable."""
        try:
            var_name = request.match_info['var_name']
            persist = request.query.get('persist', 'false').lower() == 'true'
            reload_config = request.query.get('reload_config', 'true').lower() == 'true'
            
            env_request = EnvVarDeleteRequest(
                name=var_name,
                persist=persist,
                reload_config=reload_config
            )
            
            result = await self.runtime_control.delete_env_var(env_request)
            return web.json_response(result.model_dump(mode="json"), status=200)
        except Exception as e:
            logger.error(f"Error deleting env var: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Configuration Backup/Restore Endpoints
    async def _handle_backup_config(self, request: web.Request) -> web.Response:
        """Backup configuration."""
        try:
            data = await request.json() if request.can_read_body else {}
            backup_request = ConfigBackupRequest(**data)
            
            result = await self.runtime_control.backup_config(backup_request)
            return web.json_response(result.model_dump(mode="json"), status=200)
        except ValueError as e:
            logger.warning(f"Invalid backup request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error backing up config: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_restore_config(self, request: web.Request) -> web.Response:
        """Restore configuration from backup."""
        try:
            data = await request.json()
            restore_request = ConfigRestoreRequest(**data)
            
            result = await self.runtime_control.restore_config(restore_request)
            return web.json_response(result.model_dump(mode="json"), status=200)
        except ValueError as e:
            logger.warning(f"Invalid restore request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error restoring config: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_list_config_backups(self, request: web.Request) -> web.Response:
        """List available configuration backups."""
        try:
            backups = await self.runtime_control.list_config_backups()
            return web.json_response(backups, status=200)
        except Exception as e:
            logger.error(f"Error listing config backups: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Runtime Status Endpoints
    async def _handle_get_runtime_status(self, request: web.Request) -> web.Response:
        """Get current runtime status."""
        try:
            status = await self.runtime_control.get_runtime_status()
            return web.json_response(status.model_dump(mode="json"), status=200)
        except Exception as e:
            logger.error(f"Error getting runtime status: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_runtime_snapshot(self, request: web.Request) -> web.Response:
        """Get complete runtime state snapshot."""
        try:
            snapshot = await self.runtime_control.get_runtime_snapshot()
            return web.json_response(snapshot.model_dump(mode="json"), status=200)
        except Exception as e:
            logger.error(f"Error getting runtime snapshot: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    # Service Registry Management Endpoints
    async def _handle_list_services(self, request: web.Request) -> web.Response:
        """List all registered services with their configuration."""
        try:
            handler = request.query.get('handler')
            service_type = request.query.get('service_type')
            
            services = await self.runtime_control.get_service_registry_info(handler, service_type)
            return web.json_response(services, status=200)
        except Exception as e:
            logger.error(f"Error listing services: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_service_health(self, request: web.Request) -> web.Response:
        """Get health status of all services."""
        try:
            health_status = await self.runtime_control.get_service_health_status()
            return web.json_response(health_status, status=200)
        except Exception as e:
            logger.error(f"Error getting service health: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_get_service_selection_explanation(self, request: web.Request) -> web.Response:
        """Get explanation of service selection logic."""
        try:
            explanation = await self.runtime_control.get_service_selection_explanation()
            return web.json_response(explanation, status=200)
        except Exception as e:
            logger.error(f"Error getting service selection explanation: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_reset_circuit_breakers(self, request: web.Request) -> web.Response:
        """Reset circuit breakers for services."""
        try:
            service_type = request.query.get('service_type')
            result = await self.runtime_control.reset_circuit_breakers(service_type)
            return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error resetting circuit breakers: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_update_service_priority(self, request: web.Request) -> web.Response:
        """Update service provider priority and selection strategy."""
        try:
            provider_name = request.match_info['provider_name']
            data = await request.json()
            
            result = await self.runtime_control.update_service_priority(
                provider_name=provider_name,
                new_priority=data.get('priority'),
                new_priority_group=data.get('priority_group'),
                new_strategy=data.get('strategy')
            )
            return web.json_response(result, status=200)
        except ValueError as e:
            logger.warning(f"Invalid service priority update request: {e}")
            return web.json_response({"error": f"Invalid request: {e}"}, status=400)
        except Exception as e:
            logger.error(f"Error updating service priority: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
