# ADR-0004: Local accounts in the MVP, Active Directory later

**Status:** accepted

## Context
Every log entry must have an author, so sign-in is mandatory. Integrating with Active Directory
requires coordination with IT and would slow down the MVP.

## Decision
The MVP uses standard Django authentication: users are created by an administrator.
Roles are Django groups: "Engineer" (read everything, add entries) and "Administrator"
(reference data and users).

## Consequences
- After the MVP, `django-auth-ldap` can be added, mapping domain accounts to existing users
  by username, with no model changes.
