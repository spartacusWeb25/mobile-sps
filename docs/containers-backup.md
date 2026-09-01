# Containers e Backup do PostgreSQL

> Operação do container `pg_backup`: backup diário de todas as bases e regeneração da `base_modelo`.

## O que roda

Um container Docker `pg_backup` (imagem `postgres:16`) em loop diário que:

1. Lista todas as bases não-template do PostgreSQL (`host 172.17.0.2`);
2. Faz `pg_dump -F c` comprimido (gzip) de cada base em `/backups/<base>/<base>_AAAAMMDD_HHMM.dump.gz`;
3. Apaga backups com mais de **7 dias** (`find -mtime +7 -delete`);
4. Recria a **`base_modelo`** a partir da estrutura (somente schema, `pg_dump -s`) da `saveweb001` — a base modelo deve sempre refletir a estrutura mais recente, pois é o template usado na criação de novos tenants;
5. Dorme 24h (`sleep 86400`).

- Horário observado: ~11:29 · Volume no host: `/home/ubuntu/pg_backups/` · Env: `/home/ubuntu/pg_backup.env`.

## Comandos úteis

```bash
docker ps -a                                  # containers e status
docker logs -f pg_backup                      # acompanhar execução
docker logs --tail 50 pg_backup               # últimas linhas
docker exec pg_backup ls -lh /backups/        # bases com backup
docker exec pg_backup ls -lh /backups/saveweb001/   # dumps de uma base
docker inspect pg_backup | grep -A 20 '"Env"'       # variáveis de ambiente
```

## Recriar o container

```bash
docker stop pg_backup && docker rm pg_backup

docker run -d \
  --name pg_backup \
  --env-file /home/ubuntu/pg_backup.env \
  -v /home/ubuntu/pg_backups:/backups \
  postgres:16 \
  bash -c "
while true; do
  DATABASES=\$(psql -h 172.17.0.2 -U postgres -d postgres -t -c \"SELECT datname FROM pg_database WHERE datistemplate = false;\");
  for DB in \$DATABASES; do
    mkdir -p /backups/\$DB;
    pg_dump -h 172.17.0.2 -U postgres -F c -b \$DB | gzip > /backups/\$DB/\${DB}_\$(date +%Y%m%d_%H%M).dump.gz;
  done;
  find /backups -type f -mtime +7 -delete;

  # Atualiza base_modelo com a estrutura da saveweb001
  pg_dump -h 172.17.0.2 -U postgres -s saveweb001 > /tmp/base_modelo.sql;
  psql -h 172.17.0.2 -U postgres -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'base_modelo';\";
  psql -h 172.17.0.2 -U postgres -d postgres -c \"DROP DATABASE IF EXISTS base_modelo;\";
  psql -h 172.17.0.2 -U postgres -d postgres -c \"CREATE DATABASE base_modelo;\";
  psql -h 172.17.0.2 -U postgres -d base_modelo < /tmp/base_modelo.sql;
  rm /tmp/base_modelo.sql;

  sleep 86400;
done"
```

## Pontos de atenção

- Confirmar se o `pg_backup` roda também no servidor de **produção** (observado no de treinamento) — pendência registrada em [infraestrutura.md](infraestrutura.md).
- Não há cópia off-site conhecida dos backups — mesma pendência.

---

*Padronizado em 2026-09-01. Fonte: `readme_containers.md` (raiz).*
