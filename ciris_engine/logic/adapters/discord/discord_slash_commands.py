"""Discord slash command handler for tool execution."""
import discord
from discord import app_commands
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)


class DiscordSlashCommands:
    """Handles Discord slash commands for tool execution."""
    
    def __init__(self, client: Optional[discord.Client] = None,
                 tool_handler: Optional[Any] = None,
                 time_service: Optional["TimeServiceProtocol"] = None):
        """Initialize slash command handler.
        
        Args:
            client: Discord client
            tool_handler: Tool handler for execution
            time_service: Time service
        """
        self.client = client
        self.tool_handler = tool_handler
        self._time_service = time_service
        self._command_tree: Optional[app_commands.CommandTree] = None
        self._registered_commands: Dict[str, app_commands.Command] = {}
        
        # Ensure we have a time service
        if self._time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService
            self._time_service = TimeService()
    
    def set_client(self, client: discord.Client) -> None:
        """Set Discord client and initialize command tree.
        
        Args:
            client: Discord client instance
        """
        self.client = client
        if client:
            self._command_tree = app_commands.CommandTree(client)
            self._setup_base_commands()
    
    def set_tool_handler(self, tool_handler: Any) -> None:
        """Set tool handler for command execution.
        
        Args:
            tool_handler: Tool handler instance
        """
        self.tool_handler = tool_handler
    
    def _setup_base_commands(self) -> None:
        """Set up base slash commands."""
        if not self._command_tree:
            return
        
        # /help command
        @self._command_tree.command(
            name="help",
            description="Get help with available commands"
        )
        async def help_command(interaction: discord.Interaction):
            """Show help information."""
            embed = discord.Embed(
                title="CIRIS Discord Bot Help",
                description="Available commands and features",
                color=0x3498db
            )
            
            # Base commands
            embed.add_field(
                name="Basic Commands",
                value=(
                    "`/help` - Show this help message\n"
                    "`/tools` - List available tools\n"
                    "`/tool <name>` - Get info about a specific tool\n"
                    "`/execute <tool> <params>` - Execute a tool"
                ),
                inline=False
            )
            
            # Tool commands
            if self.tool_handler:
                tools = await self.tool_handler.get_available_tools()
                if tools:
                    tool_list = "\n".join(f"• `{tool}`" for tool in tools[:10])
                    if len(tools) > 10:
                        tool_list += f"\n... and {len(tools) - 10} more"
                    embed.add_field(
                        name="Available Tools",
                        value=tool_list,
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed)
        
        # /tools command
        @self._command_tree.command(
            name="tools",
            description="List all available tools"
        )
        async def tools_command(interaction: discord.Interaction):
            """List available tools."""
            if not self.tool_handler:
                await interaction.response.send_message("Tool handler not available", ephemeral=True)
                return
            
            tools = await self.tool_handler.get_available_tools()
            
            if not tools:
                await interaction.response.send_message("No tools available", ephemeral=True)
                return
            
            # Create paginated embed if many tools
            embed = discord.Embed(
                title="Available Tools",
                description=f"Total: {len(tools)} tools",
                color=0x1abc9c
            )
            
            # Group tools by category if possible
            tool_groups: Dict[str, List[str]] = {"general": []}
            
            for tool in tools:
                # Try to categorize by prefix
                if "_" in tool:
                    category = tool.split("_")[0]
                    if category not in tool_groups:
                        tool_groups[category] = []
                    tool_groups[category].append(tool)
                else:
                    tool_groups["general"].append(tool)
            
            # Add fields for each category
            for category, tool_list in sorted(tool_groups.items()):
                if tool_list:
                    value = "\n".join(f"• `{tool}`" for tool in sorted(tool_list)[:10])
                    if len(tool_list) > 10:
                        value += f"\n... and {len(tool_list) - 10} more"
                    embed.add_field(
                        name=category.title(),
                        value=value,
                        inline=True
                    )
            
            await interaction.response.send_message(embed=embed)
        
        # /tool command
        @self._command_tree.command(
            name="tool",
            description="Get information about a specific tool"
        )
        @app_commands.describe(name="Name of the tool to get info about")
        async def tool_info_command(interaction: discord.Interaction, name: str):
            """Get tool information."""
            if not self.tool_handler:
                await interaction.response.send_message("Tool handler not available", ephemeral=True)
                return
            
            tool_info = await self.tool_handler.get_tool_info(name)
            
            if not tool_info:
                await interaction.response.send_message(f"Tool `{name}` not found", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"Tool: {tool_info.name}",
                description=tool_info.description,
                color=0x1abc9c
            )
            
            # Add parameter information
            if tool_info.parameters:
                params_text = ""
                
                # Handle different parameter schema formats
                if hasattr(tool_info.parameters, 'properties'):
                    # JSON schema style
                    for param_name, param_info in tool_info.parameters.properties.items():
                        required = param_name in getattr(tool_info.parameters, 'required', [])
                        param_type = param_info.get('type', 'any')
                        param_desc = param_info.get('description', 'No description')
                        
                        params_text += f"• **{param_name}** ({param_type})"
                        if required:
                            params_text += " *[Required]*"
                        params_text += f"\n  {param_desc}\n"
                elif hasattr(tool_info.parameters, 'model_fields'):
                    # Pydantic model style
                    for field_name, field_info in tool_info.parameters.model_fields.items():
                        params_text += f"• **{field_name}** ({field_info.annotation})\n"
                        if field_info.description:
                            params_text += f"  {field_info.description}\n"
                
                if params_text:
                    embed.add_field(
                        name="Parameters",
                        value=params_text[:1024],
                        inline=False
                    )
            
            # Add example if available
            if hasattr(tool_info, 'example'):
                embed.add_field(
                    name="Example",
                    value=f"```json\n{json.dumps(tool_info.example, indent=2)[:500]}\n```",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
        
        # /execute command
        @self._command_tree.command(
            name="execute",
            description="Execute a tool with parameters"
        )
        @app_commands.describe(
            tool="Name of the tool to execute",
            parameters="Tool parameters as JSON string"
        )
        async def execute_command(interaction: discord.Interaction, tool: str, parameters: str):
            """Execute a tool."""
            if not self.tool_handler:
                await interaction.response.send_message("Tool handler not available", ephemeral=True)
                return
            
            # Parse parameters
            try:
                params = json.loads(parameters) if parameters else {}
            except json.JSONDecodeError as e:
                await interaction.response.send_message(
                    f"Invalid JSON parameters: {e}", 
                    ephemeral=True
                )
                return
            
            # Defer response as tool execution might take time
            await interaction.response.defer()
            
            # Execute tool
            start_time = self._time_service.now()
            
            try:
                result = await self.tool_handler.execute_tool(tool, params)
                
                # Create result embed
                embed = discord.Embed(
                    title=f"Tool Execution: {tool}",
                    color=0x2ecc71 if result.success else 0xe74c3c
                )
                
                # Add execution details
                embed.add_field(
                    name="Status",
                    value="✅ Success" if result.success else "❌ Failed",
                    inline=True
                )
                
                embed.add_field(
                    name="Execution Time",
                    value=f"{result.execution_time:.2f}ms",
                    inline=True
                )
                
                # Add result
                if result.data:
                    result_str = str(result.data)[:1000]
                    embed.add_field(
                        name="Result",
                        value=f"```\n{result_str}\n```",
                        inline=False
                    )
                
                # Add error if failed
                if not result.success and result.error:
                    embed.add_field(
                        name="Error",
                        value=result.error[:1024],
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                # Error executing tool
                embed = discord.Embed(
                    title=f"Tool Execution Failed: {tool}",
                    description=str(e),
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed)
        
        # Store registered commands
        self._registered_commands = {
            "help": help_command,
            "tools": tools_command,
            "tool": tool_info_command,
            "execute": execute_command
        }
    
    async def register_tool_commands(self, guild_id: Optional[int] = None) -> None:
        """Register tool-specific slash commands.
        
        Args:
            guild_id: Optional guild ID to register commands for (None for global)
        """
        if not self.tool_handler or not self._command_tree:
            logger.warning("Cannot register tool commands - handler or tree not initialized")
            return
        
        try:
            # Get available tools
            tools = await self.tool_handler.get_all_tool_info()
            
            # Register dynamic tool commands (limit to prevent too many commands)
            for tool_info in tools[:20]:  # Discord has limits on slash commands
                # Create command for this tool
                tool_name = tool_info.name.replace("_", "-")  # Discord command names
                
                # Skip if command would conflict
                if tool_name in self._registered_commands:
                    continue
                
                # Create dynamic command
                async def tool_command(interaction: discord.Interaction, **kwargs):
                    """Execute specific tool."""
                    tool = interaction.command.name.replace("-", "_")
                    
                    # Execute with provided parameters
                    await interaction.response.defer()
                    
                    try:
                        result = await self.tool_handler.execute_tool(tool, kwargs)
                        
                        # Format result
                        if result.success:
                            embed = discord.Embed(
                                title=f"✅ {tool} executed successfully",
                                description=str(result.data)[:2000],
                                color=0x2ecc71
                            )
                        else:
                            embed = discord.Embed(
                                title=f"❌ {tool} execution failed",
                                description=result.error,
                                color=0xe74c3c
                            )
                        
                        await interaction.followup.send(embed=embed)
                        
                    except Exception as e:
                        await interaction.followup.send(f"Error executing {tool}: {e}")
                
                # Create command with dynamic parameters
                command = app_commands.Command(
                    name=tool_name,
                    description=tool_info.description[:100],  # Discord limit
                    callback=tool_command
                )
                
                # Add to tree
                self._command_tree.add_command(command)
                self._registered_commands[tool_name] = command
            
            # Sync commands
            if guild_id:
                guild = discord.Object(id=guild_id)
                await self._command_tree.sync(guild=guild)
                logger.info(f"Synced {len(self._registered_commands)} commands to guild {guild_id}")
            else:
                await self._command_tree.sync()
                logger.info(f"Synced {len(self._registered_commands)} commands globally")
                
        except Exception as e:
            logger.exception(f"Failed to register tool commands: {e}")
    
    async def handle_autocomplete(self, interaction: discord.Interaction,
                                current: str) -> List[app_commands.Choice[str]]:
        """Handle autocomplete for tool names.
        
        Args:
            interaction: Discord interaction
            current: Current input value
            
        Returns:
            List of autocomplete choices
        """
        if not self.tool_handler:
            return []
        
        try:
            tools = await self.tool_handler.get_available_tools()
            
            # Filter and sort by relevance
            matches = [
                tool for tool in tools
                if current.lower() in tool.lower()
            ]
            
            # Return top 25 matches (Discord limit)
            return [
                app_commands.Choice(name=tool, value=tool)
                for tool in sorted(matches)[:25]
            ]
            
        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return []