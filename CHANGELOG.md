# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1.0] - 2026-04-04

### Added
- Deploy backend to Railway with Dockerized FastAPI container (non-root user, exec-form CMD)
- Deploy frontend to Vercel with auto-detected Vite build
- Configurable CORS origins via `FRONTEND_URL` environment variable (comma-separated, empty-string safe)
- Production Dockerfile for backend (python:3.12-slim, uvicorn)
- `.dockerignore` to exclude dev artifacts, tests, plan files, and git history from container builds

### Fixed
- TypeScript build error in ToolCallCard where `unknown` type wasn't assignable to `ReactNode`
- Unused React import warning in scroll-area component
- CORS empty-string vulnerability when `FRONTEND_URL` has trailing comma
