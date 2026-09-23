"""Application core — config, security, HTTP errors, middleware, logging.

Read in this order:

1. ``config.py``       — Settings / environment
2. ``constants.py``    — API prefix, cookies, ErrorCode, permission enums
3. ``exceptions.py``   — AppError hierarchy + response handlers
4. ``security.py``     — JWT, password hashing, token helpers
5. ``middleware.py``   — request ID, rate limit, security headers
6. ``logging.py``      — structured logging
"""
