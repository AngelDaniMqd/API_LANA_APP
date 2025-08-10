#!/bin/bash
PORT="${PORT:-8000}"
uvicorn main:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 75 --workers 4