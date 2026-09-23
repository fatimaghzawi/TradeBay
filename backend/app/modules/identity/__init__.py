"""Identity domain — users, companies, RBAC, invitations, sessions.

Read in this order when learning the module:

1. ``models.py`` / ``constants.py``     — entities and statuses
2. ``permissions.py``                   — ``resource.action`` catalog
3. ``dependencies.py``                  — AuthContext, require_permission
4. ``service.py``                       — AuthService (login/register) + BusinessService
5. ``directory.py``                     — members, roles, invitations
6. ``auth_router.py`` / ``identity_router.py`` / ``business_router.py`` — HTTP

``router.py`` only re-exports the auth router for older imports.
"""
