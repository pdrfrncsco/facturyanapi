#!/bin/bash
set -e

# Configurações
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATABASE_NAME=${POSTGRES_DB:-ndfatura}
BACKUP_FILE="${BACKUP_DIR}/${DATABASE_NAME}_${TIMESTAMP}.sql.gz"

echo "Iniciando backup da base de dados ${DATABASE_NAME}..."

# Garantir que o diretório de backup existe
mkdir -p ${BACKUP_DIR}

# Executar backup
pg_dump -h localhost -U ${POSTGRES_USER} ${DATABASE_NAME} | gzip > ${BACKUP_FILE}

# Remover backups mais antigos que 7 dias
find ${BACKUP_DIR} -type f -name "*.sql.gz" -mtime +7 -delete

echo "Backup concluído com sucesso: ${BACKUP_FILE}"
