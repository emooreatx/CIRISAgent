"""
Core System Tools: Always available tools for CIRIS agents
Implements tools that are available across all adapters.
"""
import os
from pathlib import Path
from typing import Any, Optional
from ciris_engine.schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus


async def self_help(section: Optional[str] = None) -> ToolResult:
    """
    Returns the agent's comprehensive self-documentation.
    
    Args:
        section: Optional section to retrieve (e.g., "memory", "telemetry", "scheduling")
                If None, returns the full documentation.
    """
    try:
        # Find the agent_experience.md file
        # Try multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent.parent / "docs" / "agent_experience.md",
            Path(os.getcwd()) / "docs" / "agent_experience.md",
            Path("/home/emoore/CIRISAgent/docs/agent_experience.md"),  # Fallback absolute path
        ]
        
        content = None
        for doc_path in possible_paths:
            if doc_path.exists():
                content = doc_path.read_text(encoding='utf-8')
                break
        
        if content is None:
            # Fallback: Return a helpful message
            return ToolResult(
                tool_name="SELF_HELP",
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data={
                    "content": """# Agent Self-Help Documentation Not Found

The comprehensive agent documentation file could not be located.

## Quick Reference

### Your Core Capabilities:
- **MEMORIZE**: Store information in your graph memory
- **RECALL**: Retrieve information from your graph memory  
- **FORGET**: Remove information from your graph memory
- **OBSERVE**: Gather information from your environment
- **SPEAK**: Communicate with users
- **TOOL**: Use available tools
- **REJECT**: Decline harmful requests
- **PONDER**: Deep reflection on complex issues
- **DEFER**: Escalate to human wisdom
- **TASK_COMPLETE**: Finish the current task

### Memory Scopes:
- **LOCAL**: Your personal memories
- **SHARED**: Memories shared with other agents
- **IDENTITY**: Your core identity (WA approval required)
- **ENVIRONMENT**: System configuration (WA approval required)

For full documentation, ensure agent_experience.md is available in the docs directory.
""",
                    "section": section,
                    "fallback": True
                }
            )
        
        # If a specific section is requested, try to extract it
        if section:
            # Simple section extraction based on headers
            lines = content.split('\n')
            section_content = []
            in_section = False
            section_header = f"## {section.title()}"
            
            for i, line in enumerate(lines):
                if line.strip().lower().startswith(f"## {section.lower()}") or \
                   line.strip().lower().startswith(f"## {section.replace('_', ' ').lower()}"):
                    in_section = True
                    section_content.append(line)
                elif in_section and line.startswith("## ") and i > 0:
                    # Reached the next section
                    break
                elif in_section:
                    section_content.append(line)
            
            if section_content:
                content = '\n'.join(section_content)
            else:
                content = f"Section '{section}' not found. Available sections include:\n\n" + \
                         "- identity (Your Identity and Self-Awareness)\n" + \
                         "- memory (Memory System: Your Persistent Self)\n" + \
                         "- context (Context Gathering: Understanding Your World)\n" + \
                         "- dma (Decision Making Architecture)\n" + \
                         "- faculties (Epistemic Faculties: Your Cognitive Tools)\n" + \
                         "- configuration (Self-Configuration Capabilities)\n" + \
                         "- telemetry (Telemetry and Self-Monitoring)\n" + \
                         "- audit (Audit Trail Access)\n" + \
                         "- secrets (Secrets You Can Access)\n" + \
                         "- scheduling (Task Scheduling and Future Planning)\n" + \
                         "- actions (Your Action Repertoire)\n" + \
                         "- shutdown (Graceful Shutdown and Reawakening)\n\n" + \
                         "Use SELF_HELP without arguments to see the full documentation."
        
        return ToolResult(
            tool_name="SELF_HELP",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={
                "content": content,
                "section": section,
                "source": "agent_experience.md"
            }
        )
        
    except Exception as e:
        return ToolResult(
            tool_name="SELF_HELP",
            execution_status=ToolExecutionStatus.FAILED,
            error_message=f"Error accessing self-help documentation: {str(e)}"
        )


def register_core_tools(registry: Any) -> None:
    """Register core system tools that are always available."""
    registry.register_tool(
        "SELF_HELP",
        schema={"section": (str, type(None))},
        handler=lambda args: self_help(**args),
    )