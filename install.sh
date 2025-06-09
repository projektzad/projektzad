#!/bin/bash

# Przejdź do katalogu aplikacji
cd projektzad/myapp || exit 1

# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom aplikację Flask przez Gunicorn w tle
nohup gunicorn -w 4 run:app --bind 0.0.0.0:5000 > gunicorn.log 2>&1 &

echo "Aplikacja uruchomiona. Log: projektzad/myapp/gunicorn.log"
