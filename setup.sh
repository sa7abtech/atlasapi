#!/bin/bash

# ATLAS Setup Script
# Automated setup for ATLAS AI Assistant

set -e  # Exit on error

echo "======================================"
echo "  ATLAS AI Assistant Setup"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.11 or higher is required${NC}"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please edit .env file with your credentials${NC}"
    echo -e "${YELLOW}  Required: SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY, TELEGRAM_BOT_TOKEN${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Create logs directory
echo ""
echo "Creating logs directory..."
mkdir -p logs
echo -e "${GREEN}✓ Logs directory created${NC}"

# Create knowledge data directory
echo ""
echo "Creating knowledge data directory..."
mkdir -p knowledge/data
echo -e "${GREEN}✓ Knowledge data directory created${NC}"

echo ""
echo "======================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials:"
echo "   nano .env"
echo ""
echo "2. Run the database migration in Supabase SQL Editor:"
echo "   cat supabase/migrations/001_initial_schema.sql"
echo ""
echo "3. Place your markdown knowledge base in:"
echo "   knowledge/data/your_playbook.md"
echo ""
echo "4. Process and upload knowledge base:"
echo "   source venv/bin/activate"
echo "   python knowledge/loader.py knowledge/data/your_playbook.md"
echo ""
echo "5. Start the services:"
echo "   Terminal 1: python api/app.py"
echo "   Terminal 2: python bot/main.py"
echo ""
echo "Or use Docker:"
echo "   cd docker && docker-compose up -d"
echo ""
echo "======================================"
