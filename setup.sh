#!/bin/bash

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${GREEN}Instagram Caption Downloader Bot Setup${NC}"
echo -e "${YELLOW}========================================${NC}"

# Check Python installation
echo -e "\n${YELLOW}Checking Python installation...${NC}"
if command -v python3 &>/dev/null; then
    python_cmd="python3"
    echo -e "${GREEN}✓ Python 3 is installed.${NC}"
elif command -v python &>/dev/null; then
    python_cmd="python"
    echo -e "${GREEN}✓ Python is installed.${NC}"
else
    echo -e "${RED}✗ Python is not installed. Please install Python 3.7 or higher.${NC}"
    exit 1
fi

# Create virtual environment
echo -e "\n${YELLOW}Setting up virtual environment...${NC}"
$python_cmd -m venv venv
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to create virtual environment.${NC}"
    echo -e "${YELLOW}Installing venv module...${NC}"
    $python_cmd -m pip install virtualenv
    $python_cmd -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to create virtual environment. Continuing without it.${NC}"
    else
        echo -e "${GREEN}✓ Virtual environment created.${NC}"
    fi
else
    echo -e "${GREEN}✓ Virtual environment created.${NC}"
fi

# Activate virtual environment
if [ -d "venv" ]; then
    echo -e "\n${YELLOW}Activating virtual environment...${NC}"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    echo -e "${GREEN}✓ Virtual environment activated.${NC}"
fi

# Install dependencies
echo -e "\n${YELLOW}Installing required packages...${NC}"
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to install dependencies.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Dependencies installed successfully.${NC}"
fi

# Get Bot Token
echo -e "\n${YELLOW}Configuration Setup${NC}"
echo -e "Your Telegram Bot Token is already configured in the bot.py file."
echo -e "If you need to change it, please edit the TOKEN variable in bot.py."

# Start the bot
echo -e "\n${YELLOW}Starting the bot...${NC}"
echo -e "${GREEN}The bot is now running! Press Ctrl+C to stop.${NC}"
$python_cmd bot.py

exit 0