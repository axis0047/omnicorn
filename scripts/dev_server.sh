#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Omnicorn Development Server${NC}"
echo "========================================"

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default values
APP_PATH="${APP_PATH:-examples.fastapi_app:app}"
CONFIG="${CONFIG:-.omnicorn.dev.yaml}"
PORT="${PORT:-8080}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app)
            APP_PATH="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--app APP_PATH] [--config CONFIG] [--port PORT]"
            echo ""
            echo "Options:"
            echo "  --app     Application path (default: examples.fastapi_app:app)"
            echo "  --config  Config file path (default: .omnicorn.dev.yaml)"
            echo "  --port    Server port (default: 8080)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if config exists
if [ ! -f "$PROJECT_ROOT/$CONFIG" ]; then
    echo -e "${YELLOW}⚠ Config not found: $CONFIG${NC}"
    echo "   Creating default config..."
    cat > "$PROJECT_ROOT/$CONFIG" << EOF
server:
  port: $PORT
  socket: "127.0.0.1:$PORT"

workers:
  count: 2
  timeout: 30000

upstream:
  app_path: "$APP_PATH"
  mode: "auto"

logging:
  level: "debug"
  format: "text"
EOF
    echo -e "  ${GREEN}✓ Created $CONFIG${NC}"
fi

# Set environment variables
export OMNICORN_PORT="$PORT"

# Start server
echo -e "\n${YELLOW}Starting server...${NC}"
echo "  App:    $APP_PATH"
echo "  Config: $CONFIG"
echo "  Port:   $PORT"
echo ""
echo -e "${GREEN}Press Ctrl+C to stop${NC}"
echo "========================================"
echo ""

cd "$PROJECT_ROOT"
omnicorn "$APP_PATH" --config "$CONFIG"
