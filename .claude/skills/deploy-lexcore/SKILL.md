---
name: deploy-lexcore
description: Deploy LexCore frontend (Vercel) and backend (Railway) to production
disable-model-invocation: true
---

# Deploy LexCore

Deploy both frontend and backend to production. Run health checks after each.

## Steps

### 1. Pre-flight checks

```bash
# Ensure working tree is clean
git status --porcelain
```

If there are uncommitted changes, ask the user whether to commit first or abort.

### 2. Push to git

```bash
git push origin master
git push origin master:main
```

The frontend auto-deploys from `main` via Vercel. The `master:main` sync is required because Vercel watches `main`, not `master`.

### 3. Deploy backend

```bash
cd backend && railway up
```

Wait for the deploy to complete.

### 4. Health checks

```bash
# Backend health
curl -s https://api-production-cde1.up.railway.app/health

# Frontend reachability
curl -s -o /dev/null -w "%{http_code}" https://frontend-one-rho-88.vercel.app/
```

**Expected:**
- Backend: `{"status":"ok"}`
- Frontend: HTTP 200

### 5. Report

Print deployment status:
- Git push status
- Backend deploy status
- Health check results
- Frontend URL: https://frontend-one-rho-88.vercel.app
- Backend URL: https://api-production-cde1.up.railway.app

If any step fails, stop and report the error. Do not continue to subsequent steps.
