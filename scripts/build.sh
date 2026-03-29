#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🦄 Building Omnicorn v1.0...${NC}"
echo "========================================"

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERL_SRC="$PROJECT_ROOT/omnicorn/erl_src"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "  ✓ Python $PYTHON_VERSION"

# Check Erlang
if ! command -v erl &> /dev/null; then
    echo -e "${RED}❌ Erlang not found${NC}"
    exit 1
fi
ERLANG_VERSION=$(erl -eval 'erlang:display(erlang:system_info(otp_release)), halt().' -noshell | tr -d '\n')
echo "  ✓ Erlang/OTP $ERLANG_VERSION"

# Check rebar3
if ! command -v rebar3 &> /dev/null; then
    echo -e "${RED}❌ rebar3 not found${NC}"
    echo "   Install from https://www.rebar3.org/"
    exit 1
fi
REBAR_VERSION=$(rebar3 --version | head -n1)
echo "  ✓ rebar3 $REBAR_VERSION"

# Build Erlang backend
echo -e "\n${YELLOW}Building Erlang backend...${NC}"
cd "$ERL_SRC"

echo "  Cleaning..."
rebar3 clean

echo "  Compiling..."
rebar3 compile

echo "  Creating release..."
rebar3 release

cd "$PROJECT_ROOT"

# Install Python package
echo -e "\n${YELLOW}Installing Python package...${NC}"
python3 -m pip install -e .

echo -e "\n${GREEN}✅ Build complete!${NC}"
echo "========================================"
echo ""
echo "To run Omnicorn:"
echo "  omnicorn your_app:app --config config.yaml"
echo ""
echo "To run tests:"
echo "  ./scripts/test.sh"
