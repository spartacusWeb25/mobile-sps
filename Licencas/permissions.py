from rest_framework.permissions import BasePermission
from django.core import signing
import logging

from perfilweb.services import get_perfil_ativo, tem_permissao

logger = logging.getLogger(__name__)

USUARIOS_PRIVILEGIADOS = {"admin", "mobile", "master", "web", "lais"}


def get_nome_usuario(request):
    user = getattr(request, "user", None)

    # Campo real do model Usuarios — prioridade máxima
    nome = getattr(user, "usua_nome", None)

    # Fallback: sessão (funciona mesmo antes do user ser populado)
    if not nome:
        try:
            nome = request.session.get("usua_nome")
        except Exception:
            nome = None

    # Fallback: cookie assinado (útil em requests sem sessão ativa)
    if not nome:
        try:
            raw = request.COOKIES.get("mobile_sps_auth_hint")
            if raw:
                payload = signing.loads(raw)
                nome = (payload or {}).get("u")
        except Exception:
            nome = None

    # Fallback: cookie simples (setado pelo frontend) para casos em que o Set-Cookie do login API não propagou
    if not nome:
        try:
            nome = request.COOKIES.get("mobile_sps_user_hint")
        except Exception:
            nome = None

    nome_final = (nome or "").strip().lower()
    logger.debug("[PERM] user=%s usua_nome_resolvido='%s'", user, nome_final)
    return nome_final



class UsuariosPermission(BasePermission):
    METHOD_ACTION_MAP = {
        'GET': 'listar',
        'HEAD': 'listar',
        'OPTIONS': 'listar',
        'POST': 'criar',
        'PUT': 'editar',
        'PATCH': 'editar',
        'DELETE': 'excluir',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        model_cls = None
        if getattr(view, 'queryset', None) is not None:
            model_cls = view.queryset.model
        elif hasattr(view, 'get_queryset'):
            try:
                model_cls = view.get_queryset().model
            except Exception:
                pass

        app_label = model_cls._meta.app_label if model_cls else None
        model_name = model_cls._meta.model_name if model_cls else None
        
        if not app_label or not model_name:
            return False

        acao = self.METHOD_ACTION_MAP.get(request.method, 'listar') # não considera visualizar...

        perfil = get_perfil_ativo(request.user)
        return tem_permissao(
            perfil=perfil,
            app_label=app_label,
            model=model_name,
            acao=acao
        )
        
        

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
