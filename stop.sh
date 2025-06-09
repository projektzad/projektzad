#!/bin/bash

echo "Zatrzymywanie procesu Gunicorn..."

# Znajdź wszystkie procesy gunicorn działające w tle (np. uruchomione przez nohup)
PIDS=$(pgrep -f "gunicorn -w 4 run:app")

if [ -z "$PIDS" ]; then
    echo "Brak działających procesów Gunicorn."
else
    echo "Znalezione PID-y: $PIDS"
    kill $PIDS
    echo "Procesy zostały zatrzymane."
fi