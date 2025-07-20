#!/usr/bin/env python3
"""
Test the OAuth profile picture URL validation.
"""
from ciris_engine.logic.adapters.api.services.oauth_security import validate_oauth_picture_url

# Test cases
test_urls = [
    # Valid URLs
    ("https://lh3.googleusercontent.com/a/ACg8ocKt3P4yBmK8sLB2uPCmpvR0N7V_ybpGmQ", True, "Google avatar"),
    ("https://cdn.discordapp.com/avatars/123456/abcdef.png", True, "Discord avatar"),
    ("https://avatars.githubusercontent.com/u/12345?v=4", True, "GitHub avatar"),
    ("https://secure.gravatar.com/avatar/abcdef123456", True, "Gravatar"),
    
    # Invalid URLs
    ("http://lh3.googleusercontent.com/test.png", False, "HTTP not HTTPS"),
    ("https://evil.com/malicious.png", False, "Not whitelisted domain"),
    ("https://lh3.googleusercontent.com/../../../etc/passwd", False, "Path traversal"),
    ("javascript:alert('xss')", False, "JavaScript URL"),
    ("", True, "Empty URL is safe"),
    (None, True, "None is safe"),
]

print("Testing OAuth profile picture URL validation:")
print("-" * 60)

for url, expected, description in test_urls:
    result = validate_oauth_picture_url(url)
    status = "✓" if result == expected else "✗"
    print(f"{status} {description}")
    print(f"  URL: {url}")
    print(f"  Expected: {expected}, Got: {result}")
    if result != expected:
        print("  ERROR: Validation result doesn't match expected!")
    print()

print("-" * 60)
print("All tests completed!")