# Security Notice

## Hardcoded OAuth Credentials
- CLIENT_ID: `XhygisuebbrqQ80byOuU5VncxLIm8E6H` (const.py line 6)
- X_CLIENT_ID: `41843fb4-691d-4970-85c7-2673e8ecef40` (const.py line 7)
- Authorization server: identity.porsche.com

## Password in Credentials NamedTuple
The Credentials class stores the plaintext password as an immutable
NamedTuple field (oauth2.py line 42). This password persists in memory
for the lifetime of the connection and is sent to the auth endpoint
(oauth2.py line 335).

## Recommendations
1. Use token-based auth after initial login — discard password
2. Move CLIENT_ID to environment variable or config
3. Consider using the OS keychain for credential storage
