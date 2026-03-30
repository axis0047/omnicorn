# Changelog

All notable changes to Omnicorn will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (Phase 1)
- Initial v1.0 stable release structure
- Comprehensive test infrastructure
- CI/CD pipeline with GitHub Actions
- Development and contribution guidelines
- Branch strategy for stable release
- Dead Letter Queue (DLQ) for failed activities
- Activity retry counter with proper decrement logic
- Worker pool overload protection (max 1000 waiters)

### Changed (Phase 1)
- Project structure for maintainability
- Moved to dev/stable-phase-X branch naming convention
- Cache API now uses asyncio.Lock for thread safety
- Cache API uses itertools.count() for atomic request IDs
- Worker pool now filters dead workers iteratively (max 5 retries)
- WebSocket disconnect now properly cancels and awaits tasks

### Fixed (Phase 1)
- **CRITICAL**: Worker pool deadlock risk in omn_router.erl
- **CRITICAL**: Activity retry logic never decremented counter
- **CRITICAL**: Missing ets_delete handler in omn_worker.erl
- **CRITICAL**: Worker check-in missing on error responses
- **CRITICAL**: WebSocket connection leak in ASGI adapter
- **CRITICAL**: Cache RPC call race condition with non-atomic counter
- **HIGH**: Worker pool backpressure with max waiter queue size
- **HIGH**: Missing error cleanup in cache._rpc_call

### Fixed (Phase 2 - High Severity)
- **HIGH**: Mnesia schema creation on every boot (omnicorn_app.erl)
  - Fixed boot order: schema created before starting Mnesia
  - Added proper error handling for already_exists
  - Configurable timeout via OMNICORN_MNESIA_TIMEOUT env var
- **HIGH**: Async operation timeout monitoring (omn_worker.erl)
  - Added 60-second timeout for async operations
  - Logs timeout events for debugging
- **HIGH**: Python worker exit cleanup (omn_worker.erl)
  - Proper worker checkin on terminate
  - Socket and port cleanup on exit
- **HIGH**: WebSocket handshake timeout (asgi.py)
  - Increased from 3s to 30s for slow networks/heavy load
  - Added specific timeout error handling
- **FIXED**: Cowboy router dispatch configuration (omnicorn_app.erl)
  - Fixed route tuple structure for proper compilation

### Added (Phase 3 - gen_statem Migration)
- Workflow orchestration migrated from gen_server to gen_statem
- Proper state machine semantics for workflow lifecycle
- Two states: waiting_for_worker and suspended
- Built-in workflow cancellation support via cancel_workflow/1
- Workflow listing API via get_workflows/0
- Better state persistence and recovery
- Cleaner state transitions with hibernation support

### Added (Phase 4 - Cache API Cleanup)
- Comprehensive type hints for all cache functions
- Custom exceptions: CacheError, CacheConnectionError, CacheNotInitializedError
- Cache stats API via cache.stats()
- Automatic TTL enforcement with background cleanup process
- Cleanup runs every 60 seconds to remove expired entries
- Better error messages with context

### Changed (Phase 4 - Cache API Cleanup)
- Cache API now returns proper types with type hints
- Value serialization handled entirely by Erlang (no user-side encoding)
- TTL now properly enforced - expired entries automatically removed
- Improved documentation with usage examples

### Added (Phase 5 - Multi-Node Support - Experimental)
- Basic clustering support via omn_cluster module
- Static node discovery method
- Distributed Mnesia table configuration
- Cluster status API via omn_cluster:status/0
- Cluster join/leave API
- Environment variable configuration:
  - OMNICORN_NODE - Node name (default: omnicorn@127.0.0.1)
  - OMNICORN_COOKIE - Shared cookie (default: omnicorn_dev_cookie)
  - OMNICORN_CLUSTER_ENABLED - Enable clustering (default: false)
- Cluster configuration example file (cluster.example.yaml)

### Changed (Phase 5 - Multi-Node Support)
- Mnesia tables now support distributed replicas
- Cluster module integrated into supervisor tree

### Usage (Phase 5 - Experimental)

Start node 1:
```bash
OMNICORN_NODE=omnicorn@192.168.1.10 \
OMNICORN_COOKIE=secret123 \
OMNICORN_CLUSTER_ENABLED=true \
omnicorn myapp:app --config cluster.yaml
```

Start node 2 and join cluster:
```bash
OMNICORN_NODE=omnicorn@192.168.1.11 \
OMNICORN_COOKIE=secret123 \
OMNICORN_CLUSTER_ENABLED=true \
omnicorn myapp:app --config cluster.yaml

# From Erlang shell on node 2:
omn_cluster:join(["omnicorn@192.168.1.10"]).
```

Check cluster status:
```erlang
omn_cluster:status().
omn_cluster:connected_nodes().
```

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
