from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.apps import apps

from .models import UsuarioPerfil, PermissaoPerfil, PerfilHeranca
from .permission_map import PERMISSION_MAP
from core.middleware import get_licenca_slug
from core.utils import get_db_from_slug


CACHE_TIMEOUT = 300

EXCLUDED_DBS = [
    'savexml1',
    'savexml206',
    'spartacus',
    'savexml144',
    'savexml1014',
]


def get_banco_atual():
    return get_db_from_slug(get_licenca_slug())


def todas_acoes():
    return {
        'criar',
        'editar',
        'excluir',
        'visualizar',
        'listar',
        'imprimir',
        'exportar',
    }


def get_perfil_ativo(usuario):
    if not usuario:
        return None

    banco = get_banco_atual()

    if banco in EXCLUDED_DBS:
        return None

    usuario_id = getattr(usuario, 'usua_codi', None) or getattr(usuario, 'pk', None)

    if not usuario_id:
        return None

    key = f'perfil_ativo_{banco}_{usuario_id}'
    perfil = cache.get(key)

    if perfil is not None:
        return perfil

    rels = list(
        UsuarioPerfil.objects.using(banco)
        .select_related('perf_perf')
        .filter(
            perf_usua_id=usuario_id,
            perf_ativ=True,
            perf_perf__perf_ativ=True,
        )
    )

    if not rels:
        cache.set(key, None, CACHE_TIMEOUT)
        return None

    melhor = None
    melhor_count = -1

    try:
        for rel in rels:
            perfil_rel = rel.perf_perf
            cadeia = _cadeia_perfis(perfil_rel)

            count = (
                PermissaoPerfil.objects.using(banco)
                .filter(perf_perf_id__in=cadeia)
                .count()
            )

            if count > melhor_count:
                melhor = perfil_rel
                melhor_count = count

        if melhor is None:
            melhor = rels[0].perf_perf

    except Exception:
        melhor = rels[0].perf_perf

    try:
        outros_ids = [
            rel.perf_perf_id
            for rel in rels
            if rel.perf_perf_id != melhor.id
        ]

        if outros_ids:
            (
                UsuarioPerfil.objects.using(banco)
                .filter(
                    perf_usua_id=usuario_id,
                    perf_perf_id__in=outros_ids,
                )
                .delete()
            )

    except Exception:
        pass

    cache.set(key, melhor, CACHE_TIMEOUT)

    return melhor


def _perfil_version(perfil_id):
    banco = get_banco_atual()

    key = f'perfil_ver_{banco}_{perfil_id}'
    ver = cache.get(key)

    if ver is None:
        ver = 1
        cache.set(key, ver, CACHE_TIMEOUT)

    return ver


def limpar_cache_perfil(perfil_id):
    banco = get_banco_atual()

    key = f'perfil_ver_{banco}_{perfil_id}'
    ver = cache.get(key) or 1

    cache.set(key, ver + 1, CACHE_TIMEOUT)


def _cadeia_perfis(perfil):
    if not perfil:
        return []

    banco = get_banco_atual()

    ids = [perfil.id]
    visitados = set(ids)

    pais = list(
        PerfilHeranca.objects.using(banco)
        .filter(perf_filho=perfil)
        .values_list('perf_pai_id', flat=True)
    )

    while pais:
        novo = []

        for pid in pais:
            if pid in visitados:
                continue

            ids.append(pid)
            visitados.add(pid)

            novo.extend(
                list(
                    PerfilHeranca.objects.using(banco)
                    .filter(perf_filho_id=pid)
                    .values_list('perf_pai_id', flat=True)
                )
            )

        pais = novo

    return ids


def normalizar_app_label(app_label):
    norm = (app_label or '').strip().lower()

    norm = norm.replace('-', '_').replace(' ', '_')

    while '__' in norm:
        norm = norm.replace('__', '_')

    if norm in {'dash', 'dashboards', 'dashboard', 'dash_board'}:
        return 'dash'

    return norm


def _app_labels_equivalentes(app_norm):
    if app_norm == 'dash':
        return ['dash', 'dashboards', 'dashboard', 'dash_board']

    return [app_norm]


def _normalizar_model_name(model_name):
    norm = (model_name or '').strip().lower()

    norm = norm.replace('-', '_').replace(' ', '_')

    while '__' in norm:
        norm = norm.replace('__', '_')

    return norm


def _buscar_contenttype(banco, app_label, model_name):
    app_norm = normalizar_app_label(app_label)
    model_norm = _normalizar_model_name(model_name)

    for app_try in _app_labels_equivalentes(app_norm):
        try:
            ct = ContentType.objects.using(banco).get(
                app_label__iexact=app_try,
                model__iexact=model_norm,
            )
            return ct, f'busca_direta_{app_try}'
        except ContentType.DoesNotExist:
            pass

    if app_norm == 'pedidos' and model_norm == 'pedidos':
        try:
            ct = ContentType.objects.using(banco).get(
                app_label__iexact='Pedidos',
                model__iexact='pedidovenda',
            )
            return ct, 'alias_pedidos_pedidovenda'
        except ContentType.DoesNotExist:
            pass

    if app_norm == 'contas_a_pagar':
        aliases = {
            'titulospagar': ['titulospagar', 'titulos_pagar', 'titulos-pagar'],
            'bapatitulos': ['bapatitulos', 'bapa_titulos', 'bapa-titulos'],
        }

        for model_real, apelidos in aliases.items():
            if model_norm in apelidos:
                try:
                    ct = ContentType.objects.using(banco).get(
                        app_label__iexact='contas_a_pagar',
                        model__iexact=model_real,
                    )
                    return ct, f'alias_{model_real}'
                except ContentType.DoesNotExist:
                    pass

    if app_norm == 'contas_a_receber':
        aliases = {
            'titulosreceber': ['titulosreceber', 'titulos_receber', 'titulos-receber'],
            'baretitulos': ['baretitulos', 'bare_titulos', 'bare-titulos'],
        }

        for model_real, apelidos in aliases.items():
            if model_norm in apelidos:
                try:
                    ct = ContentType.objects.using(banco).get(
                        app_label__iexact='contas_a_receber',
                        model__iexact=model_real,
                    )
                    return ct, f'alias_{model_real}'
                except ContentType.DoesNotExist:
                    pass

    if app_norm == 'listacasamento':
        aliases = {
            'listacasamento': [
                'listacasamento',
                'listascasamento',
                'lista_casamento',
                'listas_casamento',
            ],
            'itenslistacasamento': [
                'itenslistacasamento',
                'itenslistascasamento',
                'itens_lista_casamento',
                'itens_listas_casamento',
            ],
        }

        for model_real, apelidos in aliases.items():
            if model_norm in apelidos:
                try:
                    ct = ContentType.objects.using(banco).get(
                        app_label__iexact='listacasamento',
                        model__iexact=model_real,
                    )
                    return ct, f'alias_{model_real}'
                except ContentType.DoesNotExist:
                    pass

    variacoes_model = [
        model_norm,
        model_norm.capitalize(),
        ''.join(word.capitalize() for word in model_norm.split('_')),
        model_name,
    ]

    for app_try in _app_labels_equivalentes(app_norm):
        for var_model in variacoes_model:
            try:
                model_cls = apps.get_model(app_try, var_model)

                ct = ContentType.objects.db_manager(banco).get_for_model(
                    model_cls,
                    for_concrete_model=False,
                )

                return ct, f'get_model_{app_try}_{var_model}'

            except Exception:
                pass

    try:
        app_cands = set(_app_labels_equivalentes(app_norm))
        target_cfg = None

        for cfg in apps.get_app_configs():
            label = (cfg.label or '').lower()
            name = (cfg.name.split('.')[-1] or '').lower()

            if label in app_cands or name in app_cands:
                target_cfg = cfg
                break

        if target_cfg:
            for model_cls in target_cfg.get_models():
                if model_cls._meta.model_name.lower() == model_norm:
                    ct = ContentType.objects.db_manager(banco).get_for_model(
                        model_cls,
                        for_concrete_model=False,
                    )
                    return ct, 'appconfig'

    except Exception:
        pass

    if app_norm in {'dash', 'dre', 'gerencial', 'entidades', 'pedidos'}:
        try:
            canonical_app_label = (
                ContentType.objects.using(banco)
                .filter(app_label__iexact=app_norm)
                .values_list('app_label', flat=True)
                .first()
            ) or app_norm

            try:
                ct, _ = ContentType.objects.using(banco).get_or_create(
                    app_label=canonical_app_label,
                    model=model_norm,
                    defaults={'name': f'{app_norm}.{model_norm}'},
                )
            except Exception:
                ct, _ = ContentType.objects.using(banco).get_or_create(
                    app_label=canonical_app_label,
                    model=model_norm,
                )

            return ct, f'auto_create_virtual_{app_norm}'

        except Exception:
            pass

    return None, 'not_found'


def app_ignorado_perfil(app_label):
    app_norm = normalizar_app_label(app_label)

    return app_norm in [
        'ordemdeservico',
        'o_s',
        'ordens',
        'os',
        'produtos',
    ]


def tem_permissao(perfil, app_label, model, acao):
    app_norm = normalizar_app_label(app_label)

    if app_ignorado_perfil(app_norm):
        return True

    banco = get_banco_atual()

    if banco in EXCLUDED_DBS:
        return True

    if not perfil:
        return False

    if (getattr(perfil, 'perf_nome', '') or '').strip().lower() == 'superadmin':
        return True

    cadeia = _cadeia_perfis(perfil)
    ver = _perfil_version(perfil.id)
    model_norm = _normalizar_model_name(model)

    key = (
        f'perm_{banco}_{perfil.id}_v{ver}_'
        f'{",".join(map(str, cadeia))}_'
        f'{app_norm}_{model_norm}_{acao}'
    )

    permitido = cache.get(key)

    if permitido is not None:
        return permitido

    ct_ids = []

    ct1, _ = _buscar_contenttype(banco, app_label, model)

    if ct1:
        ct_ids.append(ct1.id)

    if app_norm == 'dash':
        for alias_label in _app_labels_equivalentes('dash'):
            try:
                ct2 = ContentType.objects.using(banco).get(
                    app_label__iexact=alias_label,
                    model__iexact=model_norm,
                )

                if ct2.id not in ct_ids:
                    ct_ids.append(ct2.id)

            except ContentType.DoesNotExist:
                pass

    if not ct_ids:
        return False

    permitido = (
        PermissaoPerfil.objects.using(banco)
        .filter(
            perf_perf_id__in=cadeia,
            perf_ctype_id__in=ct_ids,
            perf_acao=acao,
        )
        .exists()
    )

    cache.set(key, permitido, CACHE_TIMEOUT)

    return permitido


def acoes_permitidas(perfil, app_label, model):
    app_norm = normalizar_app_label(app_label)

    if app_ignorado_perfil(app_norm):
        return todas_acoes()

    banco = get_banco_atual()

    if banco in EXCLUDED_DBS:
        return todas_acoes()

    if not perfil:
        return set()

    if (getattr(perfil, 'perf_nome', '') or '').strip().lower() == 'superadmin':
        return todas_acoes()

    model_norm = _normalizar_model_name(model)

    ct_ids = []

    ct1, _ = _buscar_contenttype(banco, app_label, model)

    if ct1:
        ct_ids.append(ct1.id)

    if app_norm == 'dash':
        for alias_label in _app_labels_equivalentes('dash'):
            try:
                ct2 = ContentType.objects.using(banco).get(
                    app_label__iexact=alias_label,
                    model__iexact=model_norm,
                )

                if ct2.id not in ct_ids:
                    ct_ids.append(ct2.id)

            except ContentType.DoesNotExist:
                pass

    if not ct_ids:
        return set()

    cadeia = _cadeia_perfis(perfil)

    return set(
        PermissaoPerfil.objects.using(banco)
        .filter(
            perf_perf_id__in=cadeia,
            perf_ctype_id__in=ct_ids,
        )
        .values_list('perf_acao', flat=True)
    )


def listar_permissoes(perfil):
    if not perfil:
        return []

    banco = get_banco_atual()
    cadeia = _cadeia_perfis(perfil)

    qs = PermissaoPerfil.objects.using(banco).filter(
        perf_perf_id__in=cadeia,
    )

    cids = list(qs.values_list('perf_ctype_id', flat=True))

    ct_map = {
        rec['id']: (rec['app_label'], rec['model'])
        for rec in ContentType.objects.using(banco)
        .filter(id__in=set(cids))
        .values('id', 'app_label', 'model')
    }

    items = []

    for cid, acao in qs.values_list('perf_ctype_id', 'perf_acao'):
        app_model = ct_map.get(cid)

        if app_model:
            items.append({
                'app': app_model[0],
                'model': app_model[1],
                'acao': acao,
            })

    return items


def verificar_por_url(usuario, url_name):
    banco = get_banco_atual()

    if banco in EXCLUDED_DBS:
        return True

    regra = PERMISSION_MAP.get(url_name)

    if not regra:
        return True

    app_label, model, acao = regra

    if app_ignorado_perfil(app_label):
        return True

    perfil = get_perfil_ativo(usuario)

    return tem_permissao(
        perfil=perfil,
        app_label=app_label,
        model=model,
        acao=acao,
    )


# ============================================================
# DEBUG TOOL
# Mantida comentada para uso pontual em investigação.
# Não deixar ativa em produção, porque percorre usuários, perfis,
# heranças, permissões e ContentTypes.
# ============================================================

# from Licencas.models import Usuarios
#
#
# def auditar_permissoes_usuarios(banco=None):
#     if not banco:
#         banco = get_banco_atual()
#
#     if banco == 'default':
#         return
#
#     if banco in EXCLUDED_DBS:
#         return
#
#     try:
#         todos = list(Usuarios.objects.using(banco).all())
#     except Exception:
#         return
#
#     resultado = []
#
#     for usuario in todos:
#         try:
#             uid = getattr(usuario, 'usua_codi', None)
#             nome = (getattr(usuario, 'usua_nome', '') or '').strip()
#
#             rels = list(
#                 UsuarioPerfil.objects.using(banco)
#                 .filter(
#                     perf_usua_id=uid,
#                     perf_ativ=True,
#                 )
#                 .select_related('perf_perf')
#             )
#
#             perfis = [
#                 rel.perf_perf
#                 for rel in rels
#                 if getattr(rel, 'perf_perf', None)
#             ]
#
#             if not perfis:
#                 resultado.append({
#                     'usuario_id': uid,
#                     'usuario_nome': nome,
#                     'perfis': [],
#                     'total_permissoes': 0,
#                     'recursos': {},
#                 })
#                 continue
#
#             cadeia = []
#
#             for perfil in perfis:
#                 cadeia.extend(_cadeia_perfis(perfil))
#
#             cadeia = list(sorted(set(cadeia)))
#
#             qs = PermissaoPerfil.objects.using(banco).filter(
#                 perf_perf_id__in=cadeia,
#             )
#
#             cids = list(qs.values_list('perf_ctype_id', flat=True))
#
#             ct_map = {
#                 rec['id']: (rec['app_label'], rec['model'])
#                 for rec in ContentType.objects.using(banco)
#                 .filter(id__in=set(cids))
#                 .values('id', 'app_label', 'model')
#             }
#
#             recursos = {}
#
#             for cid, acao in qs.values_list('perf_ctype_id', 'perf_acao'):
#                 app_model = ct_map.get(cid)
#
#                 if not app_model:
#                     continue
#
#                 chave = f'{app_model[0]}.{app_model[1]}'
#                 recursos.setdefault(chave, set()).add(acao)
#
#             recursos = {
#                 chave: sorted(list(acoes))
#                 for chave, acoes in recursos.items()
#             }
#
#             resultado.append({
#                 'usuario_id': uid,
#                 'usuario_nome': nome,
#                 'perfis': [perfil.perf_nome for perfil in perfis],
#                 'total_permissoes': qs.count(),
#                 'recursos': recursos,
#             })
#
#         except Exception:
#             continue
#
#     return resultado