from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from core.utils import get_db_from_slug
from O_S.models import Os
from processos.models import ChecklistItem, ChecklistModelo, Processo
from processos.rest.serializers import (
    ChecklistItemSerializer,
    ChecklistModeloSerializer,
    ProcessoChecklistRespostaSerializer,
    ProcessoSerializer,
)
from processos.services.checklist_service import ChecklistService
from processos.services.processo_service import ProcessoService
from processos.services.validacao_service import ValidacaoProcessoService


class BaseMultiDBViewSet(viewsets.ModelViewSet):
    """Base REST do app Processos com roteamento por slug + escopo empresa/filial."""

    def _scope_value(self, session_key, header_key, query_key):
        return (
            self.request.session.get(session_key)
            or self.request.headers.get(header_key)
            or self.request.query_params.get(query_key)
        )

    def _ctx(self):
        slug = self.kwargs.get("slug")
        empresa = self._scope_value("empresa_id", "X-Empresa", "empresa")
        filial = self._scope_value("filial_id", "X-Filial", "filial")

        if not empresa or not filial:
            raise ValidationError(
                {
                    "detail": "Informe empresa e filial pela sessão, headers X-Empresa/X-Filial ou query params empresa/filial."
                }
            )

        try:
            empresa = int(empresa)
            filial = int(filial)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"detail": "Empresa e filial devem ser inteiros."}
            ) from exc

        return {
            "slug": slug,
            "db_alias": get_db_from_slug(slug) if slug else "default",
            "empresa": empresa,
            "filial": filial,
            "usuario_id": self.request.session.get("usuario_id")
            or self.request.headers.get("X-Usuario")
            or self.request.data.get("usuario_id")
            or self.request.query_params.get("usuario_id"),
        }

    def _not_found(
        self, message="Registro não encontrado para a empresa/filial informada."
    ):
        raise NotFound({"detail": message})


class ChecklistModeloViewSet(BaseMultiDBViewSet):
    serializer_class = ChecklistModeloSerializer

    def get_queryset(self):
        cfg = self._ctx()
        return (
            ChecklistModelo.objects.using(cfg["db_alias"])
            .filter(chmo_empr=cfg["empresa"], chmo_fili=cfg["filial"])
            .order_by("chmo_nome")
        )

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        modelo = ChecklistService.criar_modelo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            nome=data["chmo_nome"],
            ativo=data.get("chmo_ativ", True),
        )
        return Response(
            self.get_serializer(modelo).data, status=status.HTTP_201_CREATED
        )


class ChecklistItemViewSet(BaseMultiDBViewSet):
    serializer_class = ChecklistItemSerializer

    def get_queryset(self):
        cfg = self._ctx()
        return (
            ChecklistItem.objects.using(cfg["db_alias"])
            .filter(chit_empr=cfg["empresa"], chit_fili=cfg["filial"])
            .select_related("chit_mode")
            .order_by("chit_mode_id")
        )

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            modelo = ChecklistModelo.objects.using(cfg["db_alias"]).get(
                id=data["chit_mode_id"],
                chmo_empr=cfg["empresa"],
                chmo_fili=cfg["filial"],
                chmo_ativ=True,
            )
        except ObjectDoesNotExist:
            self._not_found(
                "Modelo de checklist não encontrado/ativo para a empresa e filial informadas."
            )

        item = ChecklistService.criar_item(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            modelo=modelo,
            descricao=data["chit_desc"],
            obrigatorio=data.get("chit_obri", True),
        )
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)


class ProcessoViewSet(BaseMultiDBViewSet):
    serializer_class = ProcessoSerializer

    def get_queryset(self):
        cfg = self._ctx()
        queryset = ProcessoService.listar(
            db_alias=cfg["db_alias"], empresa=cfg["empresa"], filial=cfg["filial"]
        ).prefetch_related("respostas__pchr_item")
        os_id = self.request.query_params.get("os")
        if os_id:
            queryset = queryset.filter(proc_os_id=os_id)
        return queryset

    def create(self, request, *args, **kwargs):
        cfg = self._ctx()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            os_obj = Os.objects.using(cfg["db_alias"]).get(
                os_os=data["proc_os_id"],
                os_empr=cfg["empresa"],
                os_fili=cfg["filial"],
            )
        except ObjectDoesNotExist:
            self._not_found("OS não encontrada para a empresa/filial informada.")
        if Processo.objects.using(cfg["db_alias"]).filter(
            proc_empr=cfg["empresa"], proc_fili=cfg["filial"], proc_os=os_obj
        ).exists():
            raise ValidationError({"detail": "Esta OS já possui um processo."})
        try:
            processo = ProcessoService.criar(
                db_alias=cfg["db_alias"],
                empresa=cfg["empresa"],
                filial=cfg["filial"],
                modelo_id=data["proc_mode_id"],
                descricao=data.get("proc_desc"),
                usuario_id=cfg["usuario_id"],
                os=os_obj,
            )
        except ObjectDoesNotExist:
            self._not_found("Modelo de checklist não encontrado ou inativo.")
        return Response(
            self.get_serializer(processo).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"], url_path="os-disponiveis")
    def os_disponiveis(self, request, slug=None):
        cfg = self._ctx()
        os_list = ProcessoService.listar_os_sem_processo(
            db_alias=cfg["db_alias"], empresa=cfg["empresa"], filial=cfg["filial"]
        )
        return Response(
            [
                {
                    "os_os": o.os_os,
                    "os_data_aber": o.os_data_aber,
                    "os_clie": o.os_clie,
                    "clie_nome": o.clie_nome,
                }
                for o in os_list
            ]
        )

    @action(detail=True, methods=["get"], url_path="checklist")
    def checklist(self, request, pk=None, slug=None):
        cfg = self._ctx()
        processo = self.get_object()
        respostas = (
            processo.respostas.using(cfg["db_alias"])
            .filter(pchr_empr=cfg["empresa"], pchr_fili=cfg["filial"])
            .select_related("pchr_item")
        )
        temp_resp = False
        atuais = respostas.filter(pchr_vers__isnull=True)
        if not atuais.exists():
            atuais = respostas.filter(pchr_vers=processo.proc_vers)
            temp_resp = True
        return Response(
            {
                "temp_resp": temp_resp,
                "respostas": ProcessoChecklistRespostaSerializer(atuais, many=True).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="sincronizar-checklist")
    def sincronizar_checklist(self, request, pk=None, slug=None):
        cfg = self._ctx()
        processo = self.get_object()
        resultado = ChecklistService.sincronizar_respostas_para_processo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo=processo,
        )
        return Response(
            {
                "ok": True,
                "criadas": resultado["criadas"],
                "modelo_id": getattr(resultado["modelo"], "id", None),
                "respostas": ProcessoChecklistRespostaSerializer(
                    resultado["respostas"], many=True
                ).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="salvar-checklist")
    def salvar_checklist(self, request, pk=None, slug=None):
        cfg = self._ctx()
        dados = request.data.get("respostas", {})
        respostas = ChecklistService.salvar_respostas(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_id=pk,
            dados=dados,
        )
        return Response(
            {
                "ok": True,
                "respostas": ProcessoChecklistRespostaSerializer(
                    respostas, many=True
                ).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="validar")
    def validar(self, request, pk=None, slug=None):
        cfg = self._ctx()
        processo = self.get_object()
        if processo.proc_stat == Processo.STATUS_APROVADO:
            raise ValidationError({"detail": "Processo já foi aprovado."})
        responsavel_id = request.data.get("responsavel_id")
        documento = request.data.get("documento")
        if not responsavel_id or not documento:
            raise ValidationError(
                {"detail": "Informe responsavel_id e documento para validar."}
            )
        try:
            assinatura_valida = ValidacaoProcessoService.validar_assinatura(
                db_alias=cfg["db_alias"],
                empresa=cfg["empresa"],
                responsavel_id=responsavel_id,
                documento_inserido=documento,
            )
        except ObjectDoesNotExist:
            self._not_found("Responsável não encontrado.")
        if not assinatura_valida:
            raise ValidationError({"detail": "Documento inválido."})
        dados = ChecklistService._normalizar_dados_respostas(
            request.data.get("respostas", {})
        )
        dados["temp_resp"] = bool(request.data.get("temp_resp", False))
        resultado = ValidacaoProcessoService.validar_processo(
            db_alias=cfg["db_alias"],
            empresa=cfg["empresa"],
            filial=cfg["filial"],
            processo_id=pk,
            usuario_id=cfg["usuario_id"],
            responsavel_id=responsavel_id,
            dados=dados,
        )
        return Response(resultado)

    @action(detail=False, methods=["get"], url_path="responsaveis")
    def responsaveis(self, request, slug=None):
        cfg = self._ctx()
        entidades = ProcessoService.listar_entidades_responsaveis(
            db_alias=cfg["db_alias"], empresa=cfg["empresa"]
        )
        return Response(
            [{"enti_clie": e.enti_clie, "enti_nome": e.enti_nome} for e in entidades]
        )
