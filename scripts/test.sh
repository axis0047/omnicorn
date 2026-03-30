#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧪 Running Omnicorn Tests${NC}"
echo "========================================"

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERL_SRC="$PROJECT_ROOT/omnicorn/erl_src"

# Track test results
PYTHON_PASS=true
ERLANG_PASS=true

# Python tests
echo -e "\n${YELLOW}Running Python tests...${NC}"
if command -v pytest &> /dev/null; then
    cd "$PROJECT_ROOT"
    # Check if pytest-cov is installed
    if python3 -c "import pytest_cov" 2>/dev/null; then
        if pytest tests/ -v --cov=omnicorn --cov-report=term-missing; then
            echo -e "  ${GREEN}✓ Python tests passed${NC}"
        else
            echo -e "  ${RED}✗ Python tests failed${NC}"
            PYTHON_PASS=false
        fi
    else
        # Run without coverage
        if pytest tests/ -v; then
            echo -e "  ${GREEN}✓ Python tests passed${NC}"
        else
            echo -e "  ${RED}✗ Python tests failed${NC}"
            PYTHON_PASS=false
        fi
    fi
else
    echo -e "  ${YELLOW}⚠ pytest not found, skipping Python tests${NC}"
    echo "   Install with: pip install -e '.[dev]'"
fi

# Erlang tests
echo -e "\n${YELLOW}Running Erlang tests...${NC}"
if [ -d "$ERL_SRC" ]; then
    cd "$ERL_SRC"
    if rebar3 eunit; then
        echo -e "  ${GREEN}✓ Erlang tests passed${NC}"
    else
        echo -e "  ${RED}✗ Erlang tests failed${NC}"
        ERLANG_PASS=false
    fi
else
    echo -e "  ${YELLOW}⚠ Erlang source not found, skipping${NC}"
fi

# Summary
echo -e "\n========================================"
if [ "$PYTHON_PASS" = true ] && [ "$ERLANG_PASS" = true ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    [ "$PYTHON_PASS" = false ] && echo "  - Python tests failed"
    [ "$ERLANG_PASS" = false ] && echo "  - Erlang tests failed"
    exit 1
fi
