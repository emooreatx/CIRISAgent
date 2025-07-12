import os
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone

from ciris_engine.schemas.adapters.cli_tools import (
    ListFilesParams, ListFilesResult, ReadFileParams,
    ReadFileResult, WriteFileParams, WriteFileResult, ShellCommandParams,
    ShellCommandResult, SearchTextParams, SearchTextResult, SearchMatch
)
from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine.schemas.persistence.core import CorrelationUpdateRequest
from ciris_engine.logic import persistence

from ciris_engine.protocols.services import ToolService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.adapters.tools import (
    ToolExecutionResult, ToolExecutionStatus, ToolInfo, ToolParameterSchema
)

class CLIToolService(ToolService):
    """Simple ToolService providing local filesystem browsing."""

    def __init__(self, time_service: TimeServiceProtocol) -> None:
        super().__init__()
        self._time_service = time_service
        self._results: Dict[str, ToolExecutionResult] = {}
        self._tools = {
            "list_files": self._list_files,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "shell_command": self._shell_command,
            "search_text": self._search_text,
        }

    async def start(self) -> None:
        """Start the CLI tool service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the CLI tool service."""
        await super().stop()

    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        correlation_id = parameters.get("correlation_id", str(uuid.uuid4()))
        now = datetime.now(timezone.utc)
        corr = ServiceCorrelation(
            correlation_id=correlation_id,
            service_type="cli",
            handler_name="CLIToolService",
            action_type=tool_name,
            created_at=now,
            updated_at=now,
            timestamp=now,
            status=ServiceCorrelationStatus.PENDING
        )
        persistence.add_correlation(corr)

        start_time = self._time_service.timestamp()

        if tool_name not in self._tools:
            result = {"error": f"Unknown tool: {tool_name}"}
            success = False
            error_msg: Optional[str] = f"Unknown tool: {tool_name}"
        else:
            try:
                result = await self._tools[tool_name](parameters)
                success = result.get("error") is None
                error_msg = result.get("error")
            except Exception as e:
                result = {"error": str(e)}
                success = False
                error_msg = str(e)

        _execution_time = (self._time_service.timestamp() - start_time) * 1000  # milliseconds

        tool_result = ToolExecutionResult(
            tool_name=tool_name,
            status=ToolExecutionStatus.COMPLETED if success else ToolExecutionStatus.FAILED,
            success=success,
            data=result,
            error=error_msg,
            correlation_id=correlation_id
        )

        if correlation_id:
            self._results[correlation_id] = tool_result
            # Update the correlation we created earlier
            corr.status = ServiceCorrelationStatus.COMPLETED
            corr.updated_at = datetime.now(timezone.utc)
            persistence.update_correlation(
                correlation_id,
                corr,
                self._time_service
            )
        return tool_result

    async def _list_files(self, params: dict) -> dict:
        """List files using typed parameters."""
        # Parse parameters
        list_params = ListFilesParams.model_validate(params)

        try:
            files = sorted(os.listdir(list_params.path))
            result = ListFilesResult(files=files, path=list_params.path)
            return result.model_dump()
        except Exception as e:
            result = ListFilesResult(files=[], path=list_params.path, error=str(e))
            return result.model_dump()

    async def _read_file(self, params: dict) -> dict:
        """Read file contents using typed parameters."""
        try:
            # Parse and validate parameters
            read_params = ReadFileParams.model_validate(params)

            with open(read_params.path, "r") as f:
                content = f.read()
                result = ReadFileResult(content=content, path=read_params.path)
                return result.model_dump()
        except ValueError:
            # Parameter validation error
            result = ReadFileResult(error="path parameter required")
            return result.model_dump()
        except Exception as e:
            result = ReadFileResult(error=str(e))
            return result.model_dump()

    async def _write_file(self, params: dict) -> dict:
        """Write file using typed parameters."""
        try:
            # Parse and validate parameters
            write_params = WriteFileParams.model_validate(params)

            await asyncio.to_thread(self._write_file_sync, write_params.path, write_params.content)
            result = WriteFileResult(status="written", path=write_params.path)
            return result.model_dump()
        except ValueError:
            # Parameter validation error
            result = WriteFileResult(error="path parameter required")
            return result.model_dump()
        except Exception as e:
            result = WriteFileResult(error=str(e))
            return result.model_dump()

    def _write_file_sync(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

    async def _shell_command(self, params: dict) -> dict:
        """Execute shell command using typed parameters."""
        try:
            # Parse and validate parameters
            shell_params = ShellCommandParams.model_validate(params)

            proc = await asyncio.create_subprocess_shell(
                shell_params.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            result = ShellCommandResult(
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                returncode=proc.returncode
            )
            return result.model_dump()
        except ValueError:
            # Parameter validation error
            result = ShellCommandResult(error="command parameter required")
            return result.model_dump()
        except Exception as e:
            result = ShellCommandResult(error=str(e))
            return result.model_dump()

    async def _search_text(self, params: dict) -> dict:
        """Search text in file using typed parameters."""
        try:
            # Parse and validate parameters
            search_params = SearchTextParams.model_validate(params)

            matches: List[SearchMatch] = []
            lines = await asyncio.to_thread(self._read_lines_sync, search_params.path)
            for idx, line in enumerate(lines, 1):
                if search_params.pattern in line:
                    matches.append(SearchMatch(line=idx, text=line.strip()))

            result = SearchTextResult(matches=matches)
            return result.model_dump()
        except ValueError:
            # Parameter validation error
            result = SearchTextResult(error="pattern and path required")
            return result.model_dump()
        except Exception as e:
            result = SearchTextResult(error=str(e))
            return result.model_dump()

    def _read_lines_sync(self, path: str) -> List[str]:
        with open(path, "r") as f:
            return f.readlines()

    async def get_available_tools(self) -> List[str]:
        return list(self._tools.keys())

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]:
        for _ in range(int(timeout * 10)):
            if correlation_id in self._results:
                return self._results.pop(correlation_id)
            await asyncio.sleep(0.1)
        return None

    async def validate_parameters(self, tool_name: str, parameters: dict) -> bool:
        return tool_name in self._tools

    async def list_tools(self) -> List[str]:
        """List available tools - required by ToolServiceProtocol."""
        return list(self._tools.keys())

    async def get_tool_schema(self, tool_name: str) -> Optional[ToolParameterSchema]:
        """Get parameter schema for a specific tool - required by ToolServiceProtocol."""
        # Define schemas for each tool
        schemas = {
            "list_files": ToolParameterSchema(
                type="object",
                properties={
                    "path": {"type": "string", "description": "Directory path to list files from", "default": "."}
                },
                required=[]
            ),
            "read_file": ToolParameterSchema(
                type="object",
                properties={
                    "path": {"type": "string", "description": "File path to read"}
                },
                required=["path"]
            ),
            "write_file": ToolParameterSchema(
                type="object",
                properties={
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write to file"}
                },
                required=["path", "content"]
            ),
            "shell_command": ToolParameterSchema(
                type="object",
                properties={
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                required=["command"]
            ),
            "search_text": ToolParameterSchema(
                type="object",
                properties={
                    "path": {"type": "string", "description": "Directory path to search in"},
                    "pattern": {"type": "string", "description": "Text pattern to search for"}
                },
                required=["path", "pattern"]
            )
        }
        return schemas.get(tool_name)
