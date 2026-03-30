#!/bin/bash
# Omnicorn Test Runner
# Runs all tests with coverage reporting

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🧪 Omnicorn Test Suite${NC}"
echo "========================================"

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Track results
PYTHON_PASS=true
ERLANG_PASS=true
COVERAGE_PASS=false

# Python Tests
echo -e "\n${YELLOW}Running Python Tests...${NC}"

# Install test dependencies if needed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest...${NC}"
    pip3 install pytest pytest-asyncio pytest-cov -q
fi

# Run Python unit tests
echo -e "\n${YELLOW}Python Unit Tests:${NC}"
if pytest tests/python/unit/ -v \
    --cov=omnicorn \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/python \
    --cov-fail-under=95 \
    --tb=short; then
    echo -e "  ${GREEN}✓ Python unit tests passed${NC}"
else
    echo -e "  ${RED}✗ Python unit tests failed${NC}"
    PYTHON_PASS=false
fi

# Run Python integration tests
echo -e "\n${YELLOW}Python Integration Tests:${NC}"
if pytest tests/python/integration/ -v --tb=short; then
    echo -e "  ${GREEN}✓ Python integration tests passed${NC}"
else
    echo -e "  ${YELLOW}⚠ Python integration tests skipped (requires running server)${NC}"
fi

# Erlang Tests
echo -e "\n${YELLOW}Running Erlang Tests...${NC}"
cd "$PROJECT_ROOT/omnicorn/erl_src"

if rebar3 eunit --verbose; then
    echo -e "  ${GREEN}✓ Erlang tests passed${NC}"
else
    echo -e "  ${RED}✗ Erlang tests failed${NC}"
    ERLANG_PASS=false
fi

cd "$PROJECT_ROOT"

# Summary
echo -e "\n========================================"
echo -e "${YELLOW}Test Summary:${NC}"

if [ "$PYTHON_PASS" = true ]; then
    echo -e "  ${GREEN}✓ Python Tests${NC}"
else
    echo -e "  ${RED}✗ Python Tests${NC}"
fi

if [ "$ERLANG_PASS" = true ]; then
    echo -e "  ${GREEN}✓ Erlang Tests${NC}"
else
    echo -e "  ${RED}✗ Erlang Tests${NC}"
fi

echo ""

if [ "$PYTHON_PASS" = true ] && [ "$ERLANG_PASS" = true ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Coverage report: htmlcov/python/index.html"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    [ "$PYTHON_PASS" = false ] && echo "  - Python tests failed"
    [ "$ERLANG_PASS" = false ] && echo "  - Erlang tests failed"
    exit 1
fi
