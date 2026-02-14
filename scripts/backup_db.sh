#!/bin/bash
# Joi Database Backup Script
# Run nightly to backup joi_db to ~/joi_backups, keep 14 days

BACKUP_DIR=~/joi_backups
mkdir -p $BACKUP_DIR

DATE=$(date +\%F)
DUMP_FILE=$BACKUP_DIR/joi_$DATE.dump

# Dump the database
pg_dump -h 127.0.0.1 -p 5454 -U joi_user -F c -f $DUMP_FILE joi_db

# Remove backups older than 14 days
find $BACKUP_DIR -name 'joi_*.dump' -mtime +14 -delete

echo "Backup completed: $DUMP_FILE"
