#!/bin/sh

set -e

# --- Создание БД ---
if [ "$INIT_DB" = "true" ]; then
  echo "Initializing DB..."
  python src/tools/work_with_db/creating.py
fi

# --- Заполнение БД ---
if [ "$FILLING_DB" = "true" ]; then
  echo "Filling DB..."
  python src/tools/work_with_db/filling_database.py
fi

echo "INIT_DB='$INIT_DB'"
echo "FILLING_DB='$FILLING_DB'"

echo "Starting app..."
exec python src/main.py