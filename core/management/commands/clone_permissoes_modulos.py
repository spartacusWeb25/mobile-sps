from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db import transaction
from django.db.utils import OperationalError

from core.licencas_loader import carregar_licencas_dict


def montar_db_config(lic):
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": lic["db_name"],
        "USER": lic["db_user"],
        "PASSWORD": lic["db_password"],
        "HOST": lic["db_host"],
        "PORT": lic["db_port"],
        "CONN_MAX_AGE": 60,
    }


class Command(BaseCommand):
    help = "Clona permissões de módulos da empresa/filial fonte (padrão empresa=1) para todas as empresas/filiais dos tenants ou para um tenant específico."

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, help="Slug do tenant específico. Se omitido, roda em todos os tenants.")
        parser.add_argument("--empr", type=int, help="Empresa fonte para clonar (default: 1)", default=1)
        parser.add_argument("--fili", type=int, help="Filial fonte para clonar (se omitido, usa todas as filiais da empresa fonte)", default=None)
        parser.add_argument("--dry-run", action="store_true", help="Listar operações sem gravar no banco")
        parser.add_argument("--only-create", action="store_true", help="Somente criar quando inexistente, não atualizar existentes")

    def handle(self, *args, **options):
        slug = options.get("slug")
        source_empr = options.get("empr")
        source_fili = options.get("fili")
        dry_run = options.get("dry_run")
        only_create = options.get("only_create")

        licencas = carregar_licencas_dict()
        if not licencas:
            raise CommandError("Nenhuma licença encontrada")

        if slug:
            licencas = [l for l in licencas if l.get("slug") == slug]
            if not licencas:
                raise CommandError(f"Nenhuma licença encontrada para slug={slug}")

        for lic in licencas:
            slug_val = lic.get('slug')
            # Prefer using the same db alias resolver used in the app; fall back to tenant_{slug}
            try:
                from core.utils import get_db_from_slug
                resolved_alias = get_db_from_slug(slug_val) or f"tenant_{slug_val}"
            except Exception:
                resolved_alias = f"tenant_{slug_val}"

            config = montar_db_config(lic)
            # ensure both possible aliases are configured so ORM lookups work consistently
            connections.databases[resolved_alias] = config
            compat_alias = f"tenant_{slug_val}"
            if compat_alias != resolved_alias:
                connections.databases[compat_alias] = config

            try:
                with connections[resolved_alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
            except OperationalError:
                self.stdout.write(self.style.ERROR(f"[{resolved_alias}] Banco de dados não encontrado ou inacessível. Pulando..."))
                continue

            self.stdout.write(self.style.WARNING(f"[{resolved_alias}] Iniciando clonagem de permissões (fonte empr={source_empr} fili={source_fili})..."))

            try:
                from parametros_admin.models import PermissaoModulo
                from parametros_admin.models import Modulo
                from Licencas.models import Filiais

                banco = resolved_alias

                # Ensure 'parametros_admin' is active everywhere if it's currently not liberado
                try:
                    from django.core.cache import cache
                    mod_param = Modulo.objects.using(banco).filter(modu_nome__iexact='parametros_admin').first()
                    if mod_param:
                        existe_param = PermissaoModulo.objects.using(banco).filter(perm_modu=mod_param, perm_ativ=True).exists()
                        if not existe_param:
                            # liberate parametros_admin in all filiais (including 1/1)
                            filiais_all = Filiais.objects.using(banco).all()
                            for ff in filiais_all:
                                PermissaoModulo.objects.using(banco).update_or_create(
                                    perm_empr=ff.empr_empr,
                                    perm_fili=ff.empr_codi,
                                    perm_modu=mod_param,
                                    defaults={'perm_ativ': True, 'perm_usua_libe': 1}
                                )
                            try:
                                cache.delete(f"modulos_licenca_{slug_val}_1_1")
                            except Exception:
                                pass
                            self.stdout.write(self.style.WARNING(f"[{resolved_alias}] 'parametros_admin' liberado em todas as filiais."))
                except Exception:
                    # não falhar se cache ou operação tiver problema
                    pass

                # Simplified behavior: always clone permissions from source_empr/source_fili (default 1/1) to ALL filiais
                fonte_empr = source_empr
                fonte_fili = source_fili or 1

                permissoes_fonte = list(PermissaoModulo.objects.using(banco).filter(perm_empr=fonte_empr, perm_fili=fonte_fili).values('perm_modu_id','perm_ativ','perm_usua_libe'))

                if not permissoes_fonte:
                    self.stdout.write(self.style.WARNING(f"[{resolved_alias}] Nenhuma permissão encontrada na fonte empr={fonte_empr} fili={fonte_fili}. Pulando."))
                    continue

                filiais_qs = Filiais.objects.using(banco).all().order_by('empr_empr','empr_codi')

                created = 0
                updated = 0
                actions = []
                for f in filiais_qs:
                    target_empr = f.empr_empr
                    target_fili = f.empr_codi

                    # skip source itself
                    if target_empr == fonte_empr and target_fili == fonte_fili:
                        continue

                    for p in permissoes_fonte:
                        perm_modu_id = p['perm_modu_id']
                        perm_ativ = p['perm_ativ']
                        perm_usua_libe = p.get('perm_usua_libe') or 0

                        if dry_run:
                            actions.append((target_empr, target_fili, perm_modu_id, perm_ativ, perm_usua_libe))
                            continue

                        if only_create:
                            exists = PermissaoModulo.objects.using(banco).filter(perm_empr=target_empr, perm_fili=target_fili, perm_modu_id=perm_modu_id).exists()
                            if exists:
                                continue

                        obj, was_created = PermissaoModulo.objects.using(banco).update_or_create(
                            perm_empr=target_empr,
                            perm_fili=target_fili,
                            perm_modu_id=perm_modu_id,
                            defaults={'perm_ativ':perm_ativ, 'perm_usua_libe':perm_usua_libe}
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1

                if dry_run:
                    self.stdout.write(self.style.WARNING(f"[{resolved_alias}] Dry-run: total actions={len(actions)}"))
                    for a in actions[:500]:
                        self.stdout.write(str(a))
                    continue

                self.stdout.write(self.style.SUCCESS(f"[{resolved_alias}] Concluído. Criados: {created} Atualizados: {updated}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{resolved_alias}] Erro ao clonar permissões: {e}"))
