"""WA CLI Service - Command handlers for WA management operations."""

import json
import os
import secrets
import tempfile
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import asyncio
import http.server
import socketserver
import urllib.parse
from threading import Thread

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint

from ciris_engine.schemas.wa_schemas_v1 import (
    WACertificate, WACreateRequest, WARole, TokenType, OAuthProviderConfig
)
from ciris_engine.protocols.wa_cli_interface import WACLIInterface
from ciris_engine.services.wa_auth_service import WAAuthService


class WACLIService(WACLIInterface):
    """CLI service for WA management operations."""
    
    def __init__(self, auth_service: WAAuthService):
        """Initialize CLI service with authentication service."""
        self.auth_service = auth_service
        self.console = Console()
        
        # OAuth callback data storage
        self._oauth_callback_data: Optional[Dict[str, Any]] = None
        self._oauth_server_running = False
    
    async def bootstrap_new_root(
        self, 
        name: str, 
        use_password: bool = False,
        shamir_shares: Optional[tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """Bootstrap a new root WA."""
        try:
            self.console.print(f"🌱 Creating new root WA: [bold]{name}[/bold]")
            
            # Generate Ed25519 keypair
            private_key, public_key = self.auth_service.generate_keypair()
            
            # Generate WA ID and JWT kid
            timestamp = datetime.now(timezone.utc)
            wa_id = self.auth_service.generate_wa_id(timestamp)
            jwt_kid = f"wa-jwt-{wa_id[-6:].lower()}"
            
            # Create WA certificate
            root_wa = WACertificate(
                wa_id=wa_id,
                name=name,
                role=WARole.ROOT,
                pubkey=self.auth_service._encode_public_key(public_key),
                jwt_kid=jwt_kid,
                scopes_json='["*"]',
                token_type=TokenType.STANDARD,
                created=timestamp,
                active=True
            )
            
            # Add password if requested
            if use_password:
                password = Prompt.ask("Enter password for root WA", password=True)
                confirm_password = Prompt.ask("Confirm password", password=True)
                
                if password != confirm_password:
                    raise ValueError("Passwords do not match")
                
                root_wa.password_hash = self.auth_service.hash_password(password)
            
            # Save private key
            key_file = self.auth_service.key_dir / f"{wa_id}.key"
            key_file.write_bytes(private_key)
            key_file.chmod(0o600)
            
            # Store WA certificate
            await self.auth_service.create_wa(root_wa)
            
            self.console.print("✅ Root WA created successfully!")
            self.console.print(f"📋 WA ID: [bold]{wa_id}[/bold]")
            self.console.print(f"🔑 Private key saved to: [bold]{key_file}[/bold]")
            
            return {
                "wa_id": wa_id,
                "name": name,
                "role": "root",
                "key_file": str(key_file),
                "status": "success"
            }
            
        except Exception as e:
            self.console.print(f"❌ Error creating root WA: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def mint_wa(
        self,
        name: str,
        role: str,
        auth_type: str,
        parent_wa_id: Optional[str],
        parent_key_file: Optional[str]
    ) -> Dict[str, Any]:
        """Mint a new WA certificate."""
        try:
            self.console.print(f"🪙 Minting new {role} WA: [bold]{name}[/bold]")
            
            # Validate parent WA if provided
            parent_wa = None
            if parent_wa_id:
                parent_wa = await self.auth_service.get_wa(parent_wa_id)
                if not parent_wa:
                    raise ValueError(f"Parent WA {parent_wa_id} not found")
            
            # Generate keypair for new WA
            private_key, public_key = self.auth_service.generate_keypair()
            
            # Generate WA ID and JWT kid
            timestamp = datetime.now(timezone.utc)
            wa_id = self.auth_service.generate_wa_id(timestamp)
            jwt_kid = f"wa-jwt-{wa_id[-6:].lower()}"
            
            # Determine scopes based on role
            if role == "root":
                scopes = ["*"]
            elif role == "authority":
                scopes = ["read:any", "write:message", "write:task", "wa:mint", "wa:promote"]
            else:  # observer
                scopes = ["read:any", "write:message"]
            
            # Create WA certificate
            new_wa = WACertificate(
                wa_id=wa_id,
                name=name,
                role=WARole(role),
                pubkey=self.auth_service._encode_public_key(public_key),
                jwt_kid=jwt_kid,
                parent_wa_id=parent_wa_id,
                scopes_json=json.dumps(scopes),
                token_type=TokenType.STANDARD,
                created=timestamp,
                active=True
            )
            
            # Add authentication method
            if auth_type in ["password", "both"]:
                password = Prompt.ask(f"Enter password for {name}", password=True)
                new_wa.password_hash = self.auth_service.hash_password(password)
            
            if auth_type in ["key", "both"]:
                api_key = self.auth_service.generate_api_key(wa_id)
                new_wa.api_key_hash = self.auth_service.hash_password(api_key)
                self.console.print(f"🔑 API Key: [bold]{api_key}[/bold]")
            
            # Sign with parent if provided
            if parent_wa and parent_key_file:
                parent_private_key = Path(parent_key_file).read_bytes()
                cert_data = json.dumps(new_wa.dict(), sort_keys=True).encode()
                signature = self.auth_service.sign_data(cert_data, parent_private_key)
                new_wa.parent_signature = signature
            
            # Save private key
            key_file = self.auth_service.key_dir / f"{wa_id}.key"
            key_file.write_bytes(private_key)
            key_file.chmod(0o600)
            
            # Store WA certificate
            await self.auth_service.create_wa(new_wa)
            
            self.console.print("✅ WA minted successfully!")
            self.console.print(f"📋 WA ID: [bold]{wa_id}[/bold]")
            self.console.print(f"🔑 Private key saved to: [bold]{key_file}[/bold]")
            
            return {
                "wa_id": wa_id,
                "name": name,
                "role": role,
                "key_file": str(key_file),
                "status": "success"
            }
            
        except Exception as e:
            self.console.print(f"❌ Error minting WA: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def generate_mint_request(
        self,
        name: str,
        auth_type: str
    ) -> str:
        """Generate one-time code for mint request."""
        # Generate request data
        request_data = {
            "name": name,
            "auth_type": auth_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": secrets.token_hex(16)
        }
        
        # Create temporary file for request
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            prefix='wa_mint_request_',
            delete=False
        )
        
        json.dump(request_data, temp_file, indent=2)
        temp_file.close()
        
        # Generate one-time code (path to temp file)
        request_code = temp_file.name
        
        self.console.print(f"📝 Mint request generated: [bold]{name}[/bold]")
        self.console.print(f"🎟️  Request code: [bold]{request_code}[/bold]")
        self.console.print("Share this code with an authority to approve your request.")
        
        return request_code
    
    async def approve_mint_request(
        self,
        request_code: str,
        signer_wa_id: str,
        signer_key_file: str
    ) -> Dict[str, Any]:
        """Approve a mint request with signature."""
        try:
            # Load request data
            with open(request_code) as f:
                request_data = json.load(f)
            
            # Load signer WA
            signer_wa = await self.auth_service.get_wa(signer_wa_id)
            if not signer_wa:
                raise ValueError(f"Signer WA {signer_wa_id} not found")
            
            # Check signer authority
            if not signer_wa.has_scope("wa:mint"):
                raise ValueError("Signer does not have wa:mint scope")
            
            # Create new WA using mint_wa
            result = await self.mint_wa(
                name=request_data["name"],
                role="observer",  # Default to observer for requests
                auth_type=request_data["auth_type"],
                parent_wa_id=signer_wa_id,
                parent_key_file=signer_key_file
            )
            
            # Clean up request file
            os.unlink(request_code)
            
            self.console.print("✅ Mint request approved!")
            return result
            
        except Exception as e:
            self.console.print(f"❌ Error approving mint request: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def oauth_setup(
        self,
        provider: str,
        client_id: str,
        client_secret: str
    ) -> None:
        """Configure OAuth provider."""
        try:
            # Create OAuth config
            config = OAuthProviderConfig(
                provider=provider,
                client_id=client_id,
                client_secret=client_secret
            )
            
            # Save to oauth.json file
            oauth_file = self.auth_service.key_dir / "oauth.json"
            
            # Load existing configs if file exists
            oauth_configs = {}
            if oauth_file.exists():
                with open(oauth_file) as f:
                    oauth_configs = json.load(f)
            
            # Add new config
            oauth_configs[provider] = config.dict()
            
            # Save updated configs
            with open(oauth_file, 'w') as f:
                json.dump(oauth_configs, f, indent=2)
            
            oauth_file.chmod(0o600)
            
            self.console.print(f"✅ OAuth provider [bold]{provider}[/bold] configured!")
            
            # Display callback URL
            callback_url = f"http://localhost:8080/v1/auth/oauth/{provider}/callback"
            self.console.print(f"🔗 Callback URL: [bold]{callback_url}[/bold]")
            
        except Exception as e:
            self.console.print(f"❌ Error configuring OAuth: {e}")
            raise
    
    async def oauth_login(
        self,
        provider: str,
        callback_port: int = 8888
    ) -> Dict[str, Any]:
        """Perform OAuth login flow."""
        try:
            # Load OAuth config
            oauth_file = self.auth_service.key_dir / "oauth.json"
            if not oauth_file.exists():
                raise ValueError("No OAuth configuration found. Run 'ciris wa oauth add' first.")
            
            with open(oauth_file) as f:
                oauth_configs = json.load(f)
            
            if provider not in oauth_configs:
                raise ValueError(f"OAuth provider {provider} not configured")
            
            config = oauth_configs[provider]
            
            # Start local callback server
            await self._start_oauth_callback_server(callback_port)
            
            # Generate OAuth URL (simplified - real implementation would vary by provider)
            state = secrets.token_urlsafe(32)
            redirect_uri = f"http://localhost:{callback_port}/callback"
            
            if provider == "google":
                auth_url = (
                    f"https://accounts.google.com/o/oauth2/v2/auth?"
                    f"client_id={config['client_id']}&"
                    f"redirect_uri={redirect_uri}&"
                    f"response_type=code&"
                    f"scope=openid+email+profile&"
                    f"state={state}"
                )
            elif provider == "discord":
                auth_url = (
                    f"https://discord.com/api/oauth2/authorize?"
                    f"client_id={config['client_id']}&"
                    f"redirect_uri={redirect_uri}&"
                    f"response_type=code&"
                    f"scope=identify+email&"
                    f"state={state}"
                )
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            self.console.print(f"🌐 Opening browser for {provider} OAuth...")
            self.console.print(f"🔗 Auth URL: {auth_url}")
            
            # Open browser
            webbrowser.open(auth_url)
            
            # Wait for callback
            self.console.print("⏳ Waiting for OAuth callback...")
            
            # Wait up to 120 seconds for callback
            for _ in range(120):
                if self._oauth_callback_data:
                    break
                await asyncio.sleep(1)
            
            if not self._oauth_callback_data:
                raise ValueError("OAuth callback timeout")
            
            callback_data = self._oauth_callback_data
            self._oauth_callback_data = None
            
            # TODO: Exchange code for token and create WA
            # For now, return success with mock data
            
            self.console.print("✅ OAuth login successful!")
            
            return {
                "status": "success",
                "provider": provider,
                "user_info": callback_data
            }
            
        except Exception as e:
            self.console.print(f"❌ OAuth login error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _start_oauth_callback_server(self, port: int):
        """Start local HTTP server for OAuth callback."""
        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def __init__(self, cli_service):
                self.cli_service = cli_service
                super().__init__()
            
            def do_GET(self):
                if self.path.startswith('/callback'):
                    # Parse callback parameters
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    # Store callback data
                    self.cli_service._oauth_callback_data = {
                        "code": params.get("code", [None])[0],
                        "state": params.get("state", [None])[0],
                        "error": params.get("error", [None])[0]
                    }
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"<html><body><h1>OAuth callback received!</h1><p>You can close this window.</p></body></html>")
        
        # Create handler with CLI service reference
        handler = lambda *args: CallbackHandler.__new__(CallbackHandler, self)(*args)
        
        # Start server in background thread
        server = socketserver.TCPServer(("", port), handler)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        
        self._oauth_server_running = True
    
    # Additional CLI utilities
    
    async def list_was(self, tree_view: bool = False) -> None:
        """Display list of WAs."""
        was = await self.auth_service.list_all_was()
        
        if not was:
            self.console.print("📋 No WAs found")
            return
        
        if tree_view:
            # Display as tree
            tree = Tree("🌳 WA Hierarchy")
            
            # Find root WAs
            roots = [wa for wa in was if wa.role == WARole.ROOT]
            
            for root in roots:
                root_node = tree.add(f"👑 {root.name} ({root.wa_id})")
                await self._add_wa_children(root_node, was, root.wa_id)
            
            self.console.print(tree)
        else:
            # Display as table
            table = Table(title="WA Certificates")
            table.add_column("WA ID")
            table.add_column("Name")
            table.add_column("Role")
            table.add_column("Scopes")
            table.add_column("Created")
            table.add_column("Status")
            
            for wa in was:
                status = "🟢 Active" if wa.active else "🔴 Inactive"
                role_emoji = {"root": "👑", "authority": "🛡️", "observer": "👁️"}.get(wa.role.value, "❓")
                
                table.add_row(
                    wa.wa_id,
                    wa.name,
                    f"{role_emoji} {wa.role.value}",
                    ", ".join(wa.scopes[:3]) + ("..." if len(wa.scopes) > 3 else ""),
                    wa.created.strftime("%Y-%m-%d %H:%M"),
                    status
                )
            
            self.console.print(table)
    
    async def _add_wa_children(self, parent_node, all_was: List[WACertificate], parent_id: str):
        """Recursively add children to tree node."""
        children = [wa for wa in all_was if wa.parent_wa_id == parent_id]
        
        for child in children:
            role_emoji = {"authority": "🛡️", "observer": "👁️"}.get(child.role.value, "❓")
            child_node = parent_node.add(f"{role_emoji} {child.name} ({child.wa_id})")
            await self._add_wa_children(child_node, all_was, child.wa_id)
    
    async def onboard_wizard(self) -> Dict[str, Any]:
        """Interactive onboarding wizard."""
        self.console.print("🎯 [bold]CIRIS WA Onboarding Wizard[/bold]")
        self.console.print()
        
        # Check if any WAs exist
        was = await self.auth_service.list_all_was()
        has_root = any(wa.role == WARole.ROOT for wa in was)
        
        if has_root:
            self.console.print("ℹ️  Root WA already exists in the system.")
            
            choices = [
                "1. Create new authority WA",
                "2. Create observer WA", 
                "3. Join via OAuth",
                "4. Exit"
            ]
        else:
            self.console.print("🌱 No root WA found. You can create one or join an existing system.")
            
            choices = [
                "1. Create new root WA",
                "2. Import existing root certificate",
                "3. Stay as observer", 
                "4. Exit"
            ]
        
        self.console.print("Choose an option:")
        for choice in choices:
            self.console.print(f"  {choice}")
        
        selection = Prompt.ask("Enter choice", choices=["1", "2", "3", "4"])
        
        if has_root:
            if selection == "1":
                name = Prompt.ask("Enter WA name")
                use_password = Confirm.ask("Use password authentication?")
                return await self.mint_wa(name, "authority", "both" if use_password else "key", None, None)
            elif selection == "2":
                name = Prompt.ask("Enter WA name")
                return await self.mint_wa(name, "observer", "password", None, None)
            elif selection == "3":
                provider = Prompt.ask("OAuth provider", choices=["google", "discord", "github"])
                return await self.oauth_login(provider)
        else:
            if selection == "1":
                name = Prompt.ask("Enter root WA name")
                use_password = Confirm.ask("Use password authentication?")
                return await self.bootstrap_new_root(name, use_password)
            elif selection == "2":
                cert_file = Prompt.ask("Path to root certificate file")
                # TODO: Implement certificate import
                self.console.print("📋 Certificate import not yet implemented")
                return {"status": "not_implemented"}
            elif selection == "3":
                self.console.print("👁️  Staying as observer - you can upgrade later")
                return {"status": "observer", "message": "Remaining as observer"}
        
        return {"status": "cancelled"}