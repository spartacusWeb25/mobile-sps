from django.http import HttpResponseForbidden
from django.urls import resolve
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
)

from django.contrib import messages
from django.shortcuts import redirect
from django.conf import settings

from .services import (
    verificar_por_url,
    tem_permissao,
    get_perfil_ativo,
    normalizar_app_label,
    EXCLUDED_DBS,
)

from .permission_map import PERMISSION_MAP

from core.middleware import get_licenca_slug
from core.middleware import set_licenca_slug
from core.utils import get_db_from_slug

from Licencas.models import Usuarios
from Licencas.permissions import (
    usuario_privilegiado,
    get_nome_usuario,
)

from core.licenca_context import get_licencas_map

import jwt


class PerfilPermissionMiddleware:

    WEB_APP_MAP = {
        'contas-a-pagar': ('contas_a_pagar', 'titulospagar'),
        'contas-a-receber': ('contas_a_receber', 'titulosreceber'),
        'caixa-diario': ('CaixaDiario', 'caixageral'),
        'dre': ('DRE', 'dre'),
        'perfil': ('perfilweb', 'perfil'),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        usuario = (
            request.user
            if getattr(request, 'user', None)
            and request.user.is_authenticated
            else None
        )

        path = request.path or ""

        if not (
            path.startswith('/web/')
            or path.startswith('/api/')
        ):
            return self.get_response(request)

        try:
            parts_init = path.strip('/').split('/')
            slug_res = None

            if len(parts_init) >= 2 and parts_init[0] == 'web':

                if parts_init[1] == 'home':

                    if (
                        len(parts_init) >= 3
                        and parts_init[2] != 'selecionar-empresa'
                    ):

                        cand = (
                            parts_init[2]
                            .strip()
                            .lower()
                        )

                        if any(
                            (
                                x.get('slug') or ''
                            ).strip().lower() == cand
                            for x in get_licencas_map()
                        ):
                            slug_res = cand

                else:

                    if len(parts_init) >= 3:

                        cand = (
                            parts_init[1]
                            .strip()
                            .lower()
                        )

                        if any(
                            (
                                x.get('slug') or ''
                            ).strip().lower() == cand
                            for x in get_licencas_map()
                        ):
                            slug_res = cand

            elif len(parts_init) >= 2 and parts_init[0] == 'api':

                cand = (
                    parts_init[1]
                    .strip()
                    .lower()
                )

                if cand not in ('null', 'undefined'):

                    if any(
                        (
                            x.get('slug') or ''
                        ).strip().lower() == cand
                        for x in get_licencas_map()
                    ):
                        slug_res = cand

            if not slug_res:

                try:
                    auth = request.headers.get('Authorization', '')

                    if auth.startswith('Bearer '):

                        token = auth.split(' ')[1]

                        claims = jwt.decode(
                            token,
                            settings.SECRET_KEY,
                            algorithms=['HS256'],
                        )

                        slug_res = (
                            claims.get('lice_slug')
                            or slug_res
                        )

                except Exception:
                    pass

            if slug_res:

                try:
                    set_licenca_slug(slug_res)
                except Exception:
                    pass

        except Exception:
            pass

        if (
            path.startswith('/api/licencas/mapa/')
            or path.startswith('/api/planos/signup/trial/')
            or '/api/selecionar-empresa/' in path
            or '/api/entidades-login/' in path
        ):
            return self.get_response(request)

        parts = path.strip('/').split('/')

        if (
            len(parts) >= 4
            and parts[2] == 'entidades'
            and parts[3] == 'login'
        ):
            return self.get_response(request)

        if (
            '/parametros-admin/' in path
            or '/notificacoes/' in path
        ):
            return self.get_response(request)

        if (
            path.startswith('/api/schema/')
            or path.startswith('/api/schemas/')
            or path.startswith('/api/swagger')
        ):
            return self.get_response(request)

        if path.startswith('/api/'):

            parts = path.strip('/').split('/')

            if (
                len(parts) >= 3
                and parts[2] in ('licencas', 'auth')
            ):
                return self.get_response(request)

        if path.startswith('/web/'):

            parts = path.strip('/').split('/')

            if (
                len(parts) >= 3
                and parts[0] == 'web'
                and parts[1] == 'home'
                and parts[2] == 'selecionar-empresa'
            ):
                return self.get_response(request)

            if path.startswith('/web/login/'):
                return self.get_response(request)

        if (
            path.startswith('/static/')
            or path.startswith('/media/')
        ):
            return self.get_response(request)

        if not usuario and request.path.startswith('/api/'):

            session_id = (
                request.headers.get('X-Session-ID')
                or request.GET.get('session_id')
            )

            if session_id:
                return self.get_response(request)

        if not usuario and request.path.startswith('/web/'):

            try:
                slug_ctx = get_licenca_slug()

                banco_ctx = (
                    get_db_from_slug(slug_ctx)
                    if slug_ctx
                    else None
                )

                uname = get_nome_usuario(request)

                if banco_ctx and uname:

                    usuario = (
                        Usuarios.objects
                        .using(banco_ctx)
                        .filter(usua_nome__iexact=uname)
                        .first()
                    )

            except Exception:
                pass

        if not usuario and request.path.startswith('/api/'):

            auth = request.headers.get('Authorization', '')

            if auth.startswith('Bearer '):

                try:
                    token = auth.split(' ')[1]

                    claims = jwt.decode(
                        token,
                        settings.SECRET_KEY,
                        algorithms=['HS256'],
                    )

                    uid = (
                        claims.get('usuario_id')
                        or claims.get('user_id')
                    )

                    try:
                        uid = int(uid) if uid else None
                    except Exception:
                        uid = None

                    uname = (
                        claims.get('username')
                        or claims.get('usua_nome')
                    )

                    slug_claim = claims.get('lice_slug')

                    try:
                        slug_ctx = (
                            get_licenca_slug()
                            or slug_claim
                        )

                        banco_ctx = get_db_from_slug(slug_ctx)

                    except Exception:
                        slug_ctx = slug_claim

                        banco_ctx = (
                            get_db_from_slug(slug_ctx)
                            if slug_ctx
                            else None
                        )

                    if slug_ctx:

                        try:
                            set_licenca_slug(slug_ctx)
                        except Exception:
                            pass

                    if banco_ctx:

                        if uid:

                            usuario = (
                                Usuarios.objects
                                .using(banco_ctx)
                                .filter(usua_codi=uid)
                                .first()
                            )

                        if not usuario and uname:

                            usuario = (
                                Usuarios.objects
                                .using(banco_ctx)
                                .filter(usua_nome__iexact=uname)
                                .first()
                            )

                except Exception:
                    pass

        try:
            perfil_snap = get_perfil_ativo(usuario)
        except Exception:
            perfil_snap = None

        if usuario and not perfil_snap:

            try:
                slug = get_licenca_slug()
                banco = get_db_from_slug(slug)

                if (
                    banco
                    and banco not in EXCLUDED_DBS
                    and usuario_privilegiado(request)
                ):

                    from django.core.cache import cache
                    from perfilweb.sync import bootstrap_inicial

                    bootstrap_key = f'perfil_bootstrap_ok_{banco}'

                    if not cache.get(bootstrap_key):

                        bootstrap_inicial(banco=banco)

                        cache.set(
                            bootstrap_key,
                            1,
                            3600,
                        )

                    perfil_snap = get_perfil_ativo(usuario)

            except Exception:
                pass

            if not perfil_snap:
                return self.get_response(request)

        try:
            slug = get_licenca_slug()
            banco = get_db_from_slug(slug)

            if banco in EXCLUDED_DBS:
                return self.get_response(request)

        except Exception:
            pass

        try:
            match = resolve(request.path_info)
        except Exception:
            match = None

        view_func = (
            getattr(match, 'func', None)
            if match
            else None
        )

        view_class = (
            getattr(view_func, 'view_class', None)
            if view_func
            else None
        )

        if view_class:

            model = getattr(view_class, 'model', None)

            if model:

                app_label = getattr(
                    model._meta,
                    'app_label',
                    None,
                )

                model_name = getattr(
                    model._meta,
                    'model_name',
                    None,
                )

                if app_label and model_name:

                    app_label = normalizar_app_label(app_label)

                    if issubclass(view_class, CreateView):
                        acao = 'criar'

                    elif issubclass(view_class, UpdateView):
                        acao = 'editar'

                    elif issubclass(view_class, DeleteView):
                        acao = 'excluir'

                    elif issubclass(view_class, ListView):
                        acao = 'listar'

                    elif issubclass(view_class, DetailView):
                        acao = 'visualizar'

                    else:
                        acao = 'visualizar'

                    perfil = get_perfil_ativo(usuario)

                    permitido = tem_permissao(
                        perfil,
                        app_label,
                        model_name,
                        acao,
                    )

                    if not permitido:

                        try:
                            messages.error(
                                request,
                                'Acesso negado',
                            )
                        except Exception:
                            pass

                        return redirect('/web/home/')

                    return self.get_response(request)

        if request.path.startswith('/api/'):

            try:
                parts = request.path.strip('/').split('/')

                app_label = (
                    parts[2]
                    if len(parts) > 2
                    else None
                )

                model_token = (
                    parts[3]
                    if len(parts) > 3
                    else None
                )

                obj_id = (
                    parts[4]
                    if len(parts) > 4
                    else None
                )

                if app_label and model_token:

                    app_label = normalizar_app_label(app_label)

                    model_name = (
                        model_token
                        .strip()
                        .lower()
                        .replace('-', '_')
                    )

                    while '__' in model_name:
                        model_name = model_name.replace('__', '_')

                    if obj_id and not str(obj_id).isdigit():
                        obj_id = None

                    method = request.method.upper()

                    if method == 'GET':
                        acao = 'visualizar' if obj_id else 'listar'

                    elif method == 'POST':
                        acao = 'criar'

                    elif method in ('PUT', 'PATCH'):
                        acao = 'editar'

                    elif method == 'DELETE':
                        acao = 'excluir'

                    else:
                        acao = 'visualizar'

                    perfil = get_perfil_ativo(usuario)

                    permitido = tem_permissao(
                        perfil,
                        app_label,
                        model_name,
                        acao,
                    )

                    if not permitido:
                        return HttpResponseForbidden('Acesso negado')

            except Exception:
                pass

        elif request.path.startswith('/web/'):

            try:
                parts = request.path.strip('/').split('/')

                app_slug = None
                oper = ''

                if (
                    len(parts) >= 4
                    and parts[0] == 'web'
                    and parts[1] == 'home'
                ):

                    app_slug = parts[3]
                    oper = parts[4] if len(parts) > 4 else ''

                elif (
                    len(parts) >= 3
                    and parts[0] == 'web'
                ):

                    app_slug = parts[2]
                    oper = parts[3] if len(parts) > 3 else ''

                if app_slug:

                    app_label, default_model = (
                        self.WEB_APP_MAP.get(
                            app_slug,
                            (None, None),
                        )
                    )

                    if app_label and default_model:

                        app_label = normalizar_app_label(app_label)

                        if oper.startswith('novo'):
                            acao = 'criar'

                        elif oper.startswith('editar'):
                            acao = 'editar'

                        elif oper.startswith('excluir'):
                            acao = 'excluir'

                        elif (
                            oper.startswith('api')
                            or oper.startswith('sincronizar')
                            or oper.startswith('bootstrap')
                        ):
                            acao = 'editar'

                        elif oper.startswith('autocomplete'):
                            acao = 'visualizar'

                        else:
                            acao = 'listar'

                        perfil = get_perfil_ativo(usuario)

                        permitido = tem_permissao(
                            perfil,
                            app_label,
                            default_model,
                            acao,
                        )

                        if not permitido:

                            try:
                                messages.error(
                                    request,
                                    'Acesso negado',
                                )
                            except Exception:
                                pass

                            return redirect('/web/home/')

            except Exception:
                pass

        if not match:
            return self.get_response(request)

        view_key = (
            getattr(match, 'view_name', None)
            or getattr(match, 'url_name', None)
        )

        rule = PERMISSION_MAP.get(view_key)

        if not rule:
            return self.get_response(request)

        ok = (
            verificar_por_url(usuario, view_key)
            if usuario
            else True
        )

        if not ok:

            try:
                messages.error(
                    request,
                    'Acesso negado',
                )
            except Exception:
                pass

            return redirect('/web/home/')

        return self.get_response(request)