# Security

## Reporting

Do not open public issues for security-sensitive problems involving:

- destructive guard bypass
- arbitrary project deletion or unsafe mutation
- credential or token leakage
- host-environment command injection

Report privately to the maintainers using the contact path described in [SUPPORT](SUPPORT.md).

## Scope

Security issues include:

- bypassing `allow_destructive` protections
- escaping managed asset boundaries
- leaking private machine paths through export surfaces
- unsafe host execution behavior

## Response Goal

Public Alpha aims for prompt triage, containment, and a documented fix path.
