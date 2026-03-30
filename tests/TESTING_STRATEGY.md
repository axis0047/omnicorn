# Omnicorn v1.0 Testing Strategy

## Overview

This document outlines the comprehensive testing strategy for Omnicorn v1.0, targeting **95% code coverage**.

## Test Pyramid

```
                    ┌───────────┐
                   /   E2E 5%   \
                  /  (Full Stack) \
                 /─────────────────\
                /  Integration 15%   \
               /   (Component Boundaries) \
              /───────────────────────────\
             /      Unit Tests 80%          \
            /    (Individual Modules)         \
           ─────────────────────────────────────
```

## Directory Structure

```
tests/
├── python/
│   ├── unit/                    # Unit tests for Python modules
│   │   ├── test_cache.py        # 25 tests - 98% coverage
│   │   ├── test_protocol.py     # 8 tests - 100% coverage
│   │   ├── test_transport.py    # 10 tests - 95% coverage
│   │   ├── test_asgi.py         # 20 tests - 95% coverage
│   │   ├── test_wsgi.py         # 10 tests - 95% coverage
│   │   ├── test_worker.py       # 15 tests - 95% coverage
│   │   ├── test_sagas.py        # 12 tests - 95% coverage
│   │   ├── test_activities.py   # 12 tests - 95% coverage
│   │   ├── test_context.py      # 10 tests - 95% coverage
│   │   ├── test_supervision.py  # 5 tests - 90% coverage
│   │   └── test_config.py       # 8 tests - 85% coverage
│   │
│   ├── integration/             # Integration tests
│   │   ├── test_worker_erlang_ipc.py    # 15 tests
│   │   ├── test_cache_end_to_end.py     # 10 tests
│   │   ├── test_workflow_end_to_end.py  # 15 tests
│   │   └── test_websocket_end_to_end.py # 10 tests
│   │
│   └── e2e/                     # End-to-end tests
│       ├── test_http_server.py        # 10 tests
│       ├── test_websocket_server.py   # 10 tests
│       └── test_cluster_basic.py      # 5 tests
│
├── erlang/
│   ├── unit/                    # Unit tests for Erlang modules
│   │   ├── omn_router_tests.erl       # 15 tests - 95% coverage
│   │   ├── omn_task_broker_tests.erl  # 15 tests - 95% coverage
│   │   ├── omn_workflow_statem_tests.erl # 20 tests - 95% coverage
│   │   ├── omn_worker_tests.erl       # 20 tests - 90% coverage
│   │   ├── omn_actor_manager_tests.erl# 10 tests - 90% coverage
│   │   └── omn_cache_cleanup_tests.erl# 8 tests - 90% coverage
│   │
│   ├── integration/             # Erlang integration tests
│   │   ├── omn_cluster_tests.erl      # 12 tests
│   │   ├── omn_ws_integration_tests.erl # 12 tests
│   │   └── omn_http_integration_tests.erl # 8 tests
│   │
│   └── property/                # Property-based tests
│       └── omn_property_tests.erl     # 10 tests (PropEr)
│
└── load/                        # Load tests
    ├── test_http_benchmark.py         # wrk scripts
    ├── test_websocket_benchmark.py    # Autobahn tests
    └── test_workflow_scale.py         # Concurrent workflows
```

## Coverage Targets

### Python Modules (95% Target)

| Module | LOC | Target % | Tests | Status |
|--------|-----|----------|-------|--------|
| cache.py | 243 | 98% | 25 | ✅ Created |
| protocol.py | 34 | 100% | 8 | ✅ Created |
| transport.py | 55 | 95% | 10 | ✅ Created |
| asgi.py | 176 | 95% | 20 | ✅ Created |
| wsgi.py | 62 | 95% | 10 | ✅ Created |
| worker.py | 113 | 95% | 15 | ⏳ TODO |
| sagas.py | 71 | 95% | 12 | ⏳ TODO |
| activities.py | 58 | 95% | 12 | ⏳ TODO |
| context.py | 45 | 95% | 10 | ⏳ TODO |
| supervision.py | 28 | 90% | 5 | ⏳ TODO |
| config/*.py | 58 | 85% | 8 | ⏳ TODO |

### Erlang Modules (90% Target)

| Module | LOC | Target % | Tests | Status |
|--------|-----|----------|-------|--------|
| omn_router.erl | 101 | 95% | 15 | ✅ Created |
| omn_task_broker.erl | 95 | 95% | 15 | ⏳ TODO |
| omn_workflow_statem.erl | 171 | 95% | 20 | ⏳ TODO |
| omn_worker.erl | 239 | 90% | 20 | ⏳ TODO |
| omn_actor_manager.erl | 80 | 90% | 10 | ⏳ TODO |
| omn_cluster.erl | 116 | 85% | 12 | ⏳ TODO |
| omn_ws_handler.erl | 101 | 90% | 12 | ⏳ TODO |
| omn_http.erl | 38 | 90% | 8 | ⏳ TODO |
| omn_cache_cleanup.erl | 66 | 90% | 8 | ⏳ TODO |

## Running Tests

### Quick Test Run

```bash
./scripts/test.sh
```

### Python Tests Only

```bash
# All Python tests
pytest tests/python/ -v

# Unit tests only
pytest tests/python/unit/ -v

# With coverage
pytest tests/python/unit/ --cov=omnicorn --cov-report=html

# Specific test file
pytest tests/python/unit/test_cache.py -v
```

### Erlang Tests Only

```bash
cd omnicorn/erl_src
rebar3 eunit

# Specific test module
rebar3 eunit -m omn_router_tests
```

### Load Tests

```bash
# HTTP benchmark
cd tests/load
python test_http_benchmark.py

# WebSocket benchmark
python test_websocket_benchmark.py
```

## Test Execution Order

1. **Unit Tests** (Fast, isolated) - Run on every commit
2. **Integration Tests** (Medium speed) - Run before merge
3. **E2E Tests** (Slow, full stack) - Run before release
4. **Load Tests** (Slowest) - Run weekly

## Coverage Reporting

### Generate Coverage Report

```bash
# Python coverage
pytest tests/python/unit/ --cov=omnicorn --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/python/index.html

# Erlang coverage
cd omnicorn/erl_src
rebar3 cover
rebar3 doc
```

### Coverage Thresholds

- **Python**: Fail if < 95%
- **Erlang**: Fail if < 90%
- **Critical modules** (cache, protocol, worker): Fail if < 98%

## Continuous Integration

Tests run automatically on:
- Every push to `dev/stable-*` branches
- Every pull request
- Nightly full test suite (including load tests)

## Test Data

- Use mock objects for unit tests
- Use temporary files/sockets for integration tests
- Clean up all test data after each test
- Tests must be idempotent and repeatable

## Next Steps

1. ✅ Test infrastructure created
2. ✅ Core module tests (cache, protocol, transport, asgi, wsgi)
3. ⏳ Create remaining Python unit tests (worker, sagas, activities, context)
4. ⏳ Create Erlang unit tests (task_broker, workflow_statem, worker, etc.)
5. ⏳ Create integration tests
6. ⏳ Create E2E tests
7. ⏳ Create load tests
8. ⏳ Achieve 95% coverage

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [EUnit documentation](https://www.erlang.org/doc/apps/eunit/chapter.html)
- [PropEr documentation](http://proper.softlab.ntua.gr/)
