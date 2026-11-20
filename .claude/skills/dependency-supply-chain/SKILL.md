---
name: dependency-supply-chain
description: Use when reviewing Python dependencies, GitHub Actions, package installation, build tooling, MCP servers, or third-party skills.
---

# Dependency and Supply-Chain Review

## Scope
Read-only review by default. Do not install, upgrade, execute, or remove dependencies without exact authorization.

## Checklist
- Identify direct and transitive dependencies and the feature that requires each.
- Prefer standard library or maintained free/open-source options where suitable; avoid paid runtime/API dependencies under project policy.
- Verify package identity, maintainer, source repository, release provenance, and immutable version.
- Prefer lockfiles and hashes; distinguish version pinning from cryptographic integrity.
- Review install-time hooks, post-install scripts, native extensions, executable entry points, and network behavior.
- For GitHub Actions, prefer immutable commit SHA pins and review permissions and token exposure.
- For MCP servers and skills, inspect source, declared capabilities, data flows, authentication, and arbitrary code execution.
- Avoid sending private source, secrets, personal data, or repository contents to remote documentation or agent services.
- Identify abandoned, compromised, typosquatted, or unnecessary packages.
- Record update policy, vulnerability response, and rollback strategy.
- Do not claim a dependency is safe solely because it is popular or open source.

## Output
Provide dependency inventory, provenance evidence, capability/permission review, risk severity, free/local alternatives, and a minimal remediation plan. State which checks were not performed.
