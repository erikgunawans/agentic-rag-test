---
title: "ADR-0006: Hybrid Frontend Deployment via Vercel + main Branch"
status: "Accepted"
date: "2026-04-28"
authors: "Erik Gunawan Supriatna (LexCore Engineering)"
tags: ["architecture", "decision", "deployment", "vercel", "git", "ci-cd"]
supersedes: ""
superseded_by: ""
---

# ADR-0006: Hybrid Frontend Deployment via Vercel + main Branch

## Status

**Accepted** — current production deployment pattern. Documented in `CLAUDE.md` gotchas and the `/deploy-lexcore` skill. The frontend at `https://frontend-one-rho-88.vercel.app` is deployed exclusively from the `main` branch.

## Context

LexCore's primary development branch is `master`, but Vercel was originally configured to auto-deploy from `main`. This dual-branch reality is a legacy artifact from initial project setup that has hardened over time. The choices were:

- **Reconfigure Vercel to deploy from `master`** — eliminate the dual-branch pattern entirely.
- **Switch development to `main`** — abandon `master` and conform to the Vercel default.
- **Accept the dual-branch pattern** — codify `git push origin master:main` as the deploy trigger and document the gotcha.
- **Remove auto-deploy entirely; use `vercel --prod` CLI only** — manual deploys, no branch coupling.

Considerations:

- **Migration cost** — git history, GitHub Actions, branch-protection rules, and team mental models are all built around `master`.
- **Risk of changing Vercel project settings** — production config drift, environment variable scope, custom domain bindings.
- **Discoverability** — anyone running `git push origin master` and expecting deployment will be confused.
- **Manual override path** — `npx vercel --prod` should always work as an escape hatch.
- **Team size** — small team; documenting the gotcha is cheaper than re-platforming.

## Decision

Keep the Vercel deployment trigger on `main`. Standardize the deployment command as **`git push origin master && git push origin master:main`** (push to both, in that order). Document the pattern explicitly in `CLAUDE.md`, the `/deploy-lexcore` skill, and the deployment section of the architecture blueprint. Provide `npx vercel --prod` as the manual override.

## Consequences

### Positive

- **POS-001**: Zero migration risk — Vercel project settings, custom domain, env vars, and team permissions remain untouched.
- **POS-002**: Manual override always available — `cd frontend && npx vercel --prod` works regardless of branch state.
- **POS-003**: Git history on `master` is the source of truth; `main` is a deploy mirror.
- **POS-004**: Decoupling commit and deploy — pushing to `master` alone allows for staged deploys (commit work, deploy later).
- **POS-005**: Captured as a project-level skill (`/deploy-lexcore`) so deploys are one command.

### Negative

- **NEG-001**: New contributors WILL forget to push to `main` and will be confused why their frontend changes don't appear.
- **NEG-002**: Two pushes per deploy is friction; the discipline depends on documentation and skill automation.
- **NEG-003**: If the two branches diverge accidentally (e.g., a hotfix lands on `main` but not `master`), reconciliation requires manual git work.
- **NEG-004**: The pattern is non-standard — open-source contributors and AI assistants must be explicitly briefed.
- **NEG-005**: This is a clear "tech debt by inertia" — the right fix is to remove the dual-branch pattern, but the cost is non-trivial and the impact is small.

## Alternatives Considered

### Reconfigure Vercel to Deploy from master

- **ALT-001**: **Description**: Update the Vercel project's production branch setting from `main` to `master`. Eliminate the dual-push pattern.
- **ALT-002**: **Rejection Reason**: Risk of production config drift (env vars, domain bindings, build settings) without commensurate benefit. The current pattern works; documentation neutralizes the gotcha.

### Abandon master, Develop on main

- **ALT-003**: **Description**: Switch all development to `main`; archive `master`.
- **ALT-004**: **Rejection Reason**: Git history, hooks, branch-protection rules, and team muscle memory are tied to `master`. Migration is more disruptive than the pain it would relieve.

### Manual Deploy Only (No Auto-Deploy)

- **ALT-005**: **Description**: Disable Vercel git auto-deploy; require `vercel --prod` for every deploy.
- **ALT-006**: **Rejection Reason**: Loses the auto-deploy convenience for documentation-only and minor frontend changes. Auto-deploy from `main` is a useful safety net when manual deploys are skipped.

### GitHub Actions Workflow on master

- **ALT-007**: **Description**: A GitHub Actions workflow watches `master` and runs `vercel --prod` on push.
- **ALT-008**: **Rejection Reason**: Adds CI/CD machinery for a problem that two well-documented git commands solve. Considered for the future when the team grows or deploy gating becomes necessary.

## Implementation Notes

- **IMP-001**: The deploy command sequence (manual): `git push origin master && git push origin master:main`. Backend is a separate `cd backend && railway up`.
- **IMP-002**: The `/deploy-lexcore` skill automates the full pipeline — frontend push to both branches + Railway backend deploy + smoke health check.
- **IMP-003**: Vercel dashboard project: `frontend-one-rho-88`. Production branch: `main`. Build command: `npm run build`. Output dir: `dist`.
- **IMP-004**: When in doubt, use `cd frontend && npx vercel --prod --yes` — it deploys the local working tree directly, bypassing git entirely.
- **IMP-005**: If `master` and `main` diverge, the reconciliation playbook is: `git checkout main && git reset --hard master && git push --force-with-lease origin main` (with caution and after team alert).
- **IMP-006**: This ADR will be superseded if/when GitHub Actions, Vercel project reconfiguration, or branch consolidation is undertaken — log a follow-up ADR at that time.

## References

- **REF-001**: ADR-0005 — Tests Against Production API (the production frontend that tests reach is the Vercel deploy).
- **REF-002**: `CLAUDE.md` — "Vercel deploys from main branch, NOT master" gotcha.
- **REF-003**: `/deploy-lexcore` skill — automated deployment pipeline.
- **REF-004**: `Project_Architecture_Blueprint.md` Section 11 — Deployment Architecture.
- **REF-005**: Vercel deployment documentation — https://vercel.com/docs/deployments
