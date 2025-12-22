#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set PYTHONPATH to current directory
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run the application
python3 -m src.main "$@"
