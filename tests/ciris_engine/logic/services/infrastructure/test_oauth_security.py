"""
OAuth Security Validation Tests

Tests security validation for OAuth profile data to prevent:
- XSS attacks via profile pictures
- HTTP downgrade attacks
- Domain spoofing
- Path traversal attacks
"""
import pytest
from ciris_engine.logic.adapters.api.services.oauth_security import validate_oauth_picture_url


class TestOAuthSecurity:
    """Test OAuth profile data security validation."""
    
    def test_valid_oauth_picture_urls(self):
        """Test that valid OAuth provider URLs are accepted."""
        valid_urls = [
            # Google
            ("https://lh3.googleusercontent.com/a/ACg8ocKt3P4yBmK8sLB2uPCmpvR0N7V_ybpGmQ", "Google avatar"),
            ("https://lh3.googleusercontent.com/test.png", "Google simple"),
            
            # Discord
            ("https://cdn.discordapp.com/avatars/123456/abcdef.png", "Discord avatar"),
            ("https://cdn.discordapp.com/avatars/123/abc.jpg", "Discord JPEG"),
            
            # GitHub
            ("https://avatars.githubusercontent.com/u/12345?v=4", "GitHub avatar"),
            ("https://avatars.githubusercontent.com/u/123", "GitHub simple"),
            
            # Gravatar
            ("https://secure.gravatar.com/avatar/abcdef123456", "Gravatar"),
            ("https://www.gravatar.com/avatar/123", "Gravatar www"),
            
            # Empty/None (safe defaults)
            ("", "Empty string"),
            (None, "None value"),
        ]
        
        for url, description in valid_urls:
            assert validate_oauth_picture_url(url) is True, f"Failed for {description}: {url}"
    
    def test_invalid_oauth_picture_urls_security(self):
        """Test that potentially malicious URLs are rejected."""
        invalid_urls = [
            # HTTP downgrade attack
            ("http://lh3.googleusercontent.com/test.png", "HTTP not HTTPS"),
            ("http://cdn.discordapp.com/avatars/123/abc.png", "Discord HTTP"),
            
            # Domain spoofing
            ("https://evil.com/malicious.png", "Not whitelisted domain"),
            ("https://lh3.googleusercontent.com.evil.com/bad.png", "Subdomain attack"),
            ("https://fake-avatars.githubusercontent.com/u/123", "Fake GitHub"),
            
            # Path traversal
            ("https://lh3.googleusercontent.com/../../../etc/passwd", "Path traversal"),
            ("https://cdn.discordapp.com/avatars/../../../sensitive", "Discord traversal"),
            
            # XSS attempts
            ("javascript:alert('xss')", "JavaScript URL"),
            ("data:text/html,<script>alert('xss')</script>", "Data URL with script"),
            ("vbscript:msgbox('xss')", "VBScript URL"),
            
            # Other protocols
            ("file:///etc/passwd", "File protocol"),
            ("ftp://lh3.googleusercontent.com/test.png", "FTP protocol"),
            ("chrome://settings", "Chrome protocol"),
        ]
        
        for url, description in invalid_urls:
            assert validate_oauth_picture_url(url) is False, f"Should reject {description}: {url}"
    
    def test_oauth_picture_url_edge_cases(self):
        """Test edge cases in OAuth picture URL validation."""
        edge_cases = [
            # URL encoding
            ("https://lh3.googleusercontent.com/test%20image.png", True, "URL encoded space"),
            ("https://lh3.googleusercontent.com/test%2F..%2Fetc%2Fpasswd", False, "Encoded traversal"),
            
            # Query parameters
            ("https://avatars.githubusercontent.com/u/123?v=4&size=200", True, "Multiple params"),
            ("https://lh3.googleusercontent.com/test.png?<script>", False, "Script in query"),
            
            # Fragments
            ("https://cdn.discordapp.com/avatars/123/abc.png#anchor", True, "URL fragment"),
            ("https://secure.gravatar.com/avatar/123#<script>", False, "Script in fragment"),
            
            # Case sensitivity
            ("HTTPS://LH3.GOOGLEUSERCONTENT.COM/TEST.PNG", True, "Uppercase protocol/domain"),
            ("https://LH3.googleusercontent.com/test.png", True, "Mixed case domain"),
            
            # Whitespace
            ("  https://lh3.googleusercontent.com/test.png  ", True, "Whitespace trimming"),
            ("https://lh3.googleusercontent.com/test.png\n", True, "Newline trimming"),
        ]
        
        for url, expected, description in edge_cases:
            result = validate_oauth_picture_url(url)
            assert result == expected, f"Failed for {description}: {url} (expected {expected}, got {result})"
    
    def test_oauth_domain_whitelist_strict(self):
        """Test that domain whitelist is strictly enforced."""
        # Similar looking domains that should be rejected
        similar_domains = [
            "https://ih3.googleusercontent.com/test.png",  # ih3 instead of lh3
            "https://lh3.googleusercontents.com/test.png",  # googleusercontents
            "https://cdn.discord.com/avatars/123/abc.png",  # discord.com not discordapp.com
            "https://avatar.githubusercontent.com/u/123",  # avatar not avatars
            "https://gravatar.com/avatar/123",  # Missing secure/www
            "https://secure-gravatar.com/avatar/123",  # Hyphen instead of dot
        ]
        
        for url in similar_domains:
            assert validate_oauth_picture_url(url) is False, f"Should reject similar domain: {url}"
    
    def test_oauth_url_validation_performance(self):
        """Test that URL validation handles large inputs gracefully."""
        # Very long URL - should reject URLs over 2000 chars
        long_path = "a" * 10000
        long_url = f"https://lh3.googleusercontent.com/{long_path}.png"
        assert validate_oauth_picture_url(long_url) is False  # Changed: reject long URLs
        
        # URL with many query parameters but under 2000 chars total
        params = "&".join([f"param{i}=value{i}" for i in range(50)])  # Reduced from 100
        param_url = f"https://avatars.githubusercontent.com/u/123?{params}"
        assert len(param_url) < 2000  # Ensure it's under limit
        assert validate_oauth_picture_url(param_url) is True
        
        # Malformed URLs should not crash
        malformed = [
            "https://",
            "://lh3.googleusercontent.com",
            "https:lh3.googleusercontent.com",
            "https://lh3.googleusercontent.com:not-a-port/test.png",
            "https://[invalid-ipv6]/test.png",
        ]
        
        for url in malformed:
            # Should handle gracefully (return False, not crash)
            result = validate_oauth_picture_url(url)
            assert isinstance(result, bool)