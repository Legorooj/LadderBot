#!/bin/bash

DAY=$(date +%A)
TARGET=/home/legorooj/backups/polyladder_bak-${DAY}.sqlc
FULLTARGET=/home/legorooj/backups/polyladder_full_backup.sqlc

/usr/bin/pg_dump -U legorooj -Fc polyladder > $TARGET
/usr/bin/pg_dump -U legorooj -Fc polyladder > $FULLTARGET

if [ $? -eq 0 ]
then
  echo "Backup successful to file $TARGET"
  exit 0
else
  echo "Error during pg_dump" >&2
  exit 1
fi
