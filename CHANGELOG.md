# Changelog

All notable changes to Omnicorn will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial v1.0 stable release structure
- Comprehensive test infrastructure
- CI/CD pipeline with GitHub Actions
- Development and contribution guidelines
- Branch strategy for stable release
- Dead Letter Queue (DLQ) for failed activities
- Activity retry counter with proper decrement logic
- Worker pool overload protection (max 1000 waiters)

### Changed
- Project structure for maintainability
- Moved to dev/stable-phase-X branch naming convention
- Cache API now uses asyncio.Lock for thread safety
- Cache API uses itertools.count() for atomic request IDs
- Worker pool now filters dead workers iteratively (max 5 retries)
- WebSocket disconnect now properly cancels and awaits tasks

### Fixed
- **CRITICAL**: Worker pool deadlock risk in omn_router.erl
- **CRITICAL**: Activity retry logic never decremented counter
- **CRITICAL**: Missing ets_delete handler in omn_worker.erl
- **CRITICAL**: Worker check-in missing on error responses
- **CRITICAL**: WebSocket connection leak in ASGI adapter
- **CRITICAL**: Cache RPC call race condition with non-atomic counter
- **HIGH**: Worker pool backpressure with max waiter queue size
- **HIGH**: Missing error cleanup in cache._rpc_call

## [0.0.0] - 2024-XX-XX

### Added
- Initial prototype
- WSGI/ASGI support
- Basic workflow orchestration
- ETS cache integration
- WebSocket support

### Known Issues
- See GitHub issues for prototype limitations
- v1.0 will address critical and high severity bugs
