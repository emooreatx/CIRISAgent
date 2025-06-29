"""Discord role-based access control for channels and operations."""
import discord
import logging
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    """Access levels for Discord operations."""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 3
    ADMIN = 4


@dataclass
class ChannelPermissions:
    """Permissions for a specific channel."""
    channel_id: str
    read_roles: Set[str]  # Role names that can read
    write_roles: Set[str]  # Role names that can write
    execute_roles: Set[str]  # Role names that can execute tools
    admin_roles: Set[str]  # Role names with full access

    def get_access_level(self, roles: List[str]) -> AccessLevel:
        """Get highest access level for given roles.

        Args:
            roles: List of role names

        Returns:
            Highest access level
        """
        role_set = set(role.upper() for role in roles)

        if any(role in self.admin_roles for role in role_set):
            return AccessLevel.ADMIN
        elif any(role in self.execute_roles for role in role_set):
            return AccessLevel.EXECUTE
        elif any(role in self.write_roles for role in role_set):
            return AccessLevel.WRITE
        elif any(role in self.read_roles for role in role_set):
            return AccessLevel.READ
        else:
            return AccessLevel.NONE


class DiscordAccessControl:
    """Manages role-based access control for Discord operations."""

    # Default role mappings
    DEFAULT_ROLE_ACCESS = {
        "AUTHORITY": AccessLevel.ADMIN,
        "OBSERVER": AccessLevel.READ,
        "MODERATOR": AccessLevel.EXECUTE,
        "MEMBER": AccessLevel.WRITE,
        "@everyone": AccessLevel.NONE
    }

    def __init__(self, client: Optional[discord.Client] = None):
        """Initialize access control.

        Args:
            client: Discord client instance
        """
        self.client = client
        self._channel_permissions: Dict[str, ChannelPermissions] = {}
        self._global_permissions: Dict[str, AccessLevel] = self.DEFAULT_ROLE_ACCESS.copy()
        self._user_overrides: Dict[str, AccessLevel] = {}  # user_id -> access level

    def set_client(self, client: discord.Client) -> None:
        """Set Discord client after initialization.

        Args:
            client: Discord client instance
        """
        self.client = client

    def configure_channel(self, channel_id: str,
                        read_roles: Optional[List[str]] = None,
                        write_roles: Optional[List[str]] = None,
                        execute_roles: Optional[List[str]] = None,
                        admin_roles: Optional[List[str]] = None) -> None:
        """Configure permissions for a specific channel.

        Args:
            channel_id: Discord channel ID
            read_roles: Roles that can read from channel
            write_roles: Roles that can write to channel
            execute_roles: Roles that can execute tools in channel
            admin_roles: Roles with full access to channel
        """
        self._channel_permissions[channel_id] = ChannelPermissions(
            channel_id=channel_id,
            read_roles=set(role.upper() for role in (read_roles or [])),
            write_roles=set(role.upper() for role in (write_roles or [])),
            execute_roles=set(role.upper() for role in (execute_roles or [])),
            admin_roles=set(role.upper() for role in (admin_roles or ["AUTHORITY"]))
        )

        logger.info(f"Configured permissions for channel {channel_id}")

    def set_global_role_access(self, role: str, access_level: AccessLevel) -> None:
        """Set global access level for a role.

        Args:
            role: Role name
            access_level: Access level to grant
        """
        self._global_permissions[role.upper()] = access_level
        logger.info(f"Set global access for role {role} to {access_level.name}")

    def set_user_override(self, user_id: str, access_level: AccessLevel) -> None:
        """Set access override for a specific user.

        Args:
            user_id: Discord user ID
            access_level: Access level to grant
        """
        self._user_overrides[user_id] = access_level
        logger.info(f"Set access override for user {user_id} to {access_level.name}")

    async def check_channel_access(self, user_id: str, channel_id: str,
                                 required_level: AccessLevel) -> bool:
        """Check if user has required access level for a channel.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            required_level: Required access level

        Returns:
            True if user has required access
        """
        # Check user override first
        if user_id in self._user_overrides:
            user_level = self._user_overrides[user_id]
            return user_level.value >= required_level.value

        # Get user's roles
        roles = await self._get_user_roles(user_id)
        if not roles:
            return False

        # Check channel-specific permissions
        if channel_id in self._channel_permissions:
            channel_perms = self._channel_permissions[channel_id]
            access_level = channel_perms.get_access_level(roles)
        else:
            # Use global permissions
            access_level = self._get_global_access_level(roles)

        return access_level.value >= required_level.value

    async def check_operation(self, user_id: str, channel_id: str,
                            operation: str) -> bool:
        """Check if user can perform a specific operation.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            operation: Operation name (e.g., "send_message", "execute_tool")

        Returns:
            True if operation is allowed
        """
        # Map operations to required access levels
        operation_levels = {
            "read_messages": AccessLevel.READ,
            "send_message": AccessLevel.WRITE,
            "execute_tool": AccessLevel.EXECUTE,
            "manage_channel": AccessLevel.ADMIN,
            "manage_permissions": AccessLevel.ADMIN,
            "send_deferral": AccessLevel.EXECUTE,
            "approve_request": AccessLevel.ADMIN,
            "fetch_guidance": AccessLevel.EXECUTE
        }

        required_level = operation_levels.get(operation, AccessLevel.WRITE)
        return await self.check_channel_access(user_id, channel_id, required_level)

    async def filter_accessible_channels(self, user_id: str,
                                       channel_ids: List[str],
                                       required_level: AccessLevel = AccessLevel.READ) -> List[str]:
        """Filter list of channels to only those user can access.

        Args:
            user_id: Discord user ID
            channel_ids: List of channel IDs to check
            required_level: Required access level

        Returns:
            List of accessible channel IDs
        """
        accessible = []

        for channel_id in channel_ids:
            if await self.check_channel_access(user_id, channel_id, required_level):
                accessible.append(channel_id)

        return accessible

    async def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """Get all permissions for a user.

        Args:
            user_id: Discord user ID

        Returns:
            Dictionary of user permissions
        """
        # Get user's roles
        roles = await self._get_user_roles(user_id)

        # Check override
        override_level = self._user_overrides.get(user_id)

        # Get global access level
        global_level = self._get_global_access_level(roles)

        # Get channel-specific permissions
        channel_access = {}
        for channel_id, perms in self._channel_permissions.items():
            channel_access[channel_id] = perms.get_access_level(roles).name

        return {
            "user_id": user_id,
            "roles": roles,
            "override_level": override_level.name if override_level else None,
            "global_access": global_level.name,
            "channel_access": channel_access
        }

    async def _get_user_roles(self, user_id: str) -> List[str]:
        """Get roles for a Discord user.

        Args:
            user_id: Discord user ID

        Returns:
            List of role names
        """
        if not self.client:
            return []

        roles = []

        try:
            # Check all guilds
            for guild in self.client.guilds:
                member = guild.get_member(int(user_id))
                if member:
                    for role in member.roles:
                        roles.append(role.name.upper())

            # Always include @everyone
            if "@EVERYONE" not in roles:
                roles.append("@EVERYONE")

        except Exception as e:
            logger.error(f"Failed to get roles for user {user_id}: {e}")

        return roles

    def _get_global_access_level(self, roles: List[str]) -> AccessLevel:
        """Get highest global access level for roles.

        Args:
            roles: List of role names

        Returns:
            Highest access level
        """
        max_level = AccessLevel.NONE

        for role in roles:
            if role.upper() in self._global_permissions:
                level = self._global_permissions[role.upper()]
                if level.value > max_level.value:
                    max_level = level

        return max_level

    async def enforce_channel_permissions(self, message: discord.Message) -> bool:
        """Check if a message should be processed based on permissions.

        Args:
            message: Discord message

        Returns:
            True if message should be processed
        """
        # Always allow bot's own messages
        if message.author.bot and self.client and self.client.user and message.author.id == self.client.user.id:
            return True

        # Check if user has read access to the channel
        return await self.check_channel_access(
            str(message.author.id),
            str(message.channel.id),
            AccessLevel.READ
        )

    def get_access_info(self) -> Dict[str, Any]:
        """Get current access control configuration.

        Returns:
            Access control information
        """
        return {
            "global_permissions": {
                role: level.name
                for role, level in self._global_permissions.items()
            },
            "channel_count": len(self._channel_permissions),
            "user_overrides": len(self._user_overrides),
            "configured_channels": list(self._channel_permissions.keys())
        }
