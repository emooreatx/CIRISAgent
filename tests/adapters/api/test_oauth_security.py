"""
Tests for OAuth security validation module.

Tests the profile picture URL validation to ensure:
- Only HTTPS URLs are allowed
- Only whitelisted domains are accepted
- Path traversal attempts are blocked
- URL length limits are enforced
"""
import pytest
from ciris_engine.logic.adapters.api.services.oauth_security import (
    validate_oauth_picture_url,
    ALLOWED_AVATAR_DOMAINS
)


class TestOAuthPictureValidation:
    """Test OAuth profile picture URL validation."""
    
    def test_empty_url_is_safe(self):
        """Test that empty URLs are considered safe."""
        assert validate_oauth_picture_url(None) is True
        assert validate_oauth_picture_url("") is True
    
    def test_valid_google_avatar(self):
        """Test valid Google avatar URLs."""
        valid_urls = [
            "https://lh3.googleusercontent.com/a/ACg8ocKt3P4yBmK8sLB2uP",
            "https://lh3.googleusercontent.com/a-/AOh14GjXYZ",
            "https://lh3.googleusercontent.com/a/default-user",
        ]
        for url in valid_urls:
            assert validate_oauth_picture_url(url) is True
    
    def test_valid_discord_avatar(self):
        """Test valid Discord avatar URLs."""
        valid_urls = [
            "https://cdn.discordapp.com/avatars/123456789/abcdef.png",
            "https://cdn.discordapp.com/avatars/987654321/xyz123.jpg",
            "https://cdn.discordapp.com/embed/avatars/0.png",
        ]
        for url in valid_urls:
            assert validate_oauth_picture_url(url) is True
    
    def test_valid_github_avatar(self):
        """Test valid GitHub avatar URLs."""
        valid_urls = [
            "https://avatars.githubusercontent.com/u/12345?v=4",
            "https://avatars.githubusercontent.com/u/67890",
            "https://avatars.githubusercontent.com/in/12345",
        ]
        for url in valid_urls:
            assert validate_oauth_picture_url(url) is True
    
    def test_valid_gravatar(self):
        """Test valid Gravatar URLs."""
        valid_urls = [
            "https://secure.gravatar.com/avatar/abc123",
            "https://secure.gravatar.com/avatar/def456?s=200",
            "https://secure.gravatar.com/avatar/xyz789?d=identicon",
        ]
        for url in valid_urls:
            assert validate_oauth_picture_url(url) is True
    
    def test_http_urls_rejected(self):
        """Test that non-HTTPS URLs are rejected."""
        invalid_urls = [
            "http://lh3.googleusercontent.com/a/valid",
            "http://cdn.discordapp.com/avatars/123/abc.png",
            "http://avatars.githubusercontent.com/u/123",
            "http://secure.gravatar.com/avatar/abc",
        ]
        for url in invalid_urls:
            assert validate_oauth_picture_url(url) is False
    
    def test_non_whitelisted_domains_rejected(self):
        """Test that non-whitelisted domains are rejected."""
        invalid_urls = [
            "https://evil.com/fake-avatar.png",
            "https://lh3.googleusercontent.evil.com/a/fake",
            "https://cdn.discordapp.com.evil.com/avatar",
            "https://fake-github.com/avatar.png",
            "https://example.com/../../etc/passwd",
        ]
        for url in invalid_urls:
            assert validate_oauth_picture_url(url) is False
    
    def test_path_traversal_rejected(self):
        """Test that path traversal attempts are rejected."""
        invalid_urls = [
            "https://lh3.googleusercontent.com/../../../etc/passwd",
            "https://cdn.discordapp.com/avatars/../../../sensitive",
            "https://avatars.githubusercontent.com//double//slash",
            "https://secure.gravatar.com/avatar/..%2F..%2Fetc",
        ]
        for url in invalid_urls:
            assert validate_oauth_picture_url(url) is False
    
    def test_long_urls_rejected(self):
        """Test that excessively long URLs are rejected."""
        # Create a URL that's over 2000 characters
        long_path = "a" * 1970
        long_url = f"https://lh3.googleusercontent.com/{long_path}"
        assert len(long_url) > 2000
        assert validate_oauth_picture_url(long_url) is False
    
    def test_malformed_urls_rejected(self):
        """Test that malformed URLs are safely rejected."""
        invalid_urls = [
            "not-a-url",
            "ftp://lh3.googleusercontent.com/avatar",
            "javascript:alert('xss')",
            "data:image/png;base64,abc123",
            "//lh3.googleusercontent.com/no-protocol",
            "https://",
            "https:///triple-slash",
        ]
        for url in invalid_urls:
            assert validate_oauth_picture_url(url) is False
    
    def test_url_with_query_params(self):
        """Test that URLs with query parameters are accepted."""
        valid_urls = [
            "https://lh3.googleusercontent.com/a/default?sz=100",
            "https://avatars.githubusercontent.com/u/123?v=4&s=200",
            "https://secure.gravatar.com/avatar/abc?s=80&d=mp",
        ]
        for url in valid_urls:
            assert validate_oauth_picture_url(url) is True
    
    def test_url_with_fragments(self):
        """Test that URLs with fragments are accepted."""
        valid_urls = [
            "https://lh3.googleusercontent.com/a/avatar#section",
            "https://cdn.discordapp.com/avatars/123/abc.png#cached",
        ]
        for url in valid_urls:
            assert validate_oauth_picture_url(url) is True
    
    def test_subdomain_variations(self):
        """Test that exact domain matching is enforced."""
        # These should fail because they're not exact matches
        invalid_urls = [
            "https://evil.lh3.googleusercontent.com/fake",
            "https://lh3.googleusercontent.com.evil.com/fake",
            "https://cdn.discordapp.com.attacker.com/fake",
        ]
        for url in invalid_urls:
            assert validate_oauth_picture_url(url) is False
    
    def test_case_sensitivity(self):
        """Test URL validation with different cases."""
        # urlparse normalizes scheme to lowercase, so HTTPS works
        assert validate_oauth_picture_url("HTTPS://lh3.googleusercontent.com/a/valid") is True
        # Domain with different case should still match (case-insensitive)
        assert validate_oauth_picture_url("https://LH3.googleusercontent.com/a/valid") is True
        assert validate_oauth_picture_url("https://lh3.GOOGLEUSERCONTENT.com/a/valid") is True


class TestAllowedDomains:
    """Test the allowed domains configuration."""
    
    def test_allowed_domains_is_frozen(self):
        """Test that ALLOWED_AVATAR_DOMAINS is immutable."""
        assert isinstance(ALLOWED_AVATAR_DOMAINS, frozenset)
    
    def test_expected_domains_present(self):
        """Test that all expected OAuth providers are in whitelist."""
        expected_domains = {
            'lh3.googleusercontent.com',      # Google
            'cdn.discordapp.com',             # Discord
            'avatars.githubusercontent.com',   # GitHub  
            'secure.gravatar.com',            # Gravatar
            'www.gravatar.com'                # Gravatar (www)
        }
        assert expected_domains == ALLOWED_AVATAR_DOMAINS
    
    def test_no_unexpected_domains(self):
        """Test that no unexpected domains are in whitelist."""
        assert len(ALLOWED_AVATAR_DOMAINS) == 5