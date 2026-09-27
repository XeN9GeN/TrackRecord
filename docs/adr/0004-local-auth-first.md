# ADR-0004: Local accounts in the MVP, Active Directory later

**Status:** accepted

## Context
Every log entry must have an author, so sign-in is mandatory. Integrating with Active Directory
requires coordination with IT and would slow down the MVP.

## Decision
- The MVP uses standard Django authentication; users are created by an administrator.
  Users sign in with a username (not e-mail), matching future domain logins.
- Roles are Django groups: "Engineer" (read everything, add entries) and "Administrator"
  (reference data and users). The same group names will be used in AD.
- Brute-force protection with `django-axes`.
- A local administrator account stays available as a fallback when directory sign-in is added.

## Consequences
- After the MVP, `django-auth-ldap` (LDAPS only, read-only service account, group mirroring)
  can be enabled with settings only, mapping domain accounts to existing users by username.
- If the company has an SSO provider (Keycloak, ADFS), OIDC via `mozilla-django-oidc` is the
  preferred alternative to direct LDAP.
