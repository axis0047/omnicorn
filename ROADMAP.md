# Omnicorn Roadmap

This document outlines the development roadmap for Omnicorn.

## Version 1.0 (Stable Release) - Target: Q2 2025

### Phase 0: Foundation (Current)

- [x] Branch strategy setup
- [x] Project structure reorganization
- [x] Build and test infrastructure
- [x] CI/CD pipeline
- [x] Development documentation

### Phase 1: Critical Bug Fixes

- [ ] Worker pool deadlock prevention
- [ ] Activity retry logic with DLQ
- [ ] Workflow race condition fixes
- [ ] WebSocket connection leak fixes
- [ ] Cache RPC race condition fixes
- [ ] Missing ETS operation handlers
- [ ] Worker check-in on errors

### Phase 2: High Severity Fixes

- [ ] Safe Mnesia boot sequence
- [ ] Async operation timeouts
- [ ] Worker exit cleanup
- [ ] WebSocket handshake timeout
- [ ] Worker pool backpressure

### Phase 3: gen_statem Migration

- [ ] Workflow state machine implementation
- [ ] State persistence improvements
- [ ] Better error state handling
- [ ] Workflow cancellation support

### Phase 4: Cache API Cleanup

- [ ] Remove user-side byte encoding
- [ ] Add comprehensive type hints
- [ ] Better error messages
- [ ] TTL enforcement

### Phase 5: Multi-Node Support (Experimental)

- [ ] Basic clustering
- [ ] Distributed Mnesia tables
- [ ] Node discovery (static)
- [ ] Cross-node communication

### Phase 6: Testing & Documentation

- [ ] Unit test coverage >70%
- [ ] Integration tests
- [ ] Load testing baseline
- [ ] API documentation
- [ ] Deployment guide
- [ ] Example applications

## Version 1.1 (Post-Stable) - Target: Q3 2025

### Planned Features

- [ ] HTTPS/TLS termination
- [ ] Admin dashboard
- [ ] Prometheus metrics
- [ ] Distributed tracing
- [ ] Rate limiting
- [ ] Plugin system
- [ ] Hot code reloading
- [ ] Kubernetes operator

### Improvements

- [ ] Performance optimization
- [ ] Memory usage reduction
- [ ] Better error reporting
- [ ] Enhanced security

## Version 2.0 (Future) - Target: 2026

### Vision

- Production-ready clustering
- Cloud-native deployment
- Enterprise features
- Extended ecosystem

## Getting Involved

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.

### Priority Areas for Contributors

1. Test coverage improvement
2. Documentation
3. Example applications
4. Bug fixes
5. Performance optimization

## Release Schedule

| Version | Target Date | Status         |
| ------- | ----------- | -------------- |
| 1.0.0   | Q2 2025     | In Development |
| 1.0.1   | Q2 2025     | Planned        |
| 1.1.0   | Q3 2025     | Planned        |
| 2.0.0   | 2026        | Vision         |

---

_Last updated: 2025-03-29_
