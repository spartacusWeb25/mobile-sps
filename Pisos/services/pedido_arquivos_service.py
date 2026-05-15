import mimetypes

from django.db import IntegrityError

from Pisos.models import PedidosPisosArquivos


class PedidoPisosArquivosService:
    @staticmethod
    def listar(banco, *, empresa_id, pedido_numero):
        qs = PedidosPisosArquivos.objects.using(banco).filter(
            arqu_empr=int(empresa_id),
            arqu_pedi=int(pedido_numero),
        )
        try:
            return list(qs.order_by("arqu_cod_arqu"))
        except Exception:
            return list(qs)

    @staticmethod
    def obter(banco, *, empresa_id, pedido_numero, codigo_arquivo):
        qs = PedidosPisosArquivos.objects.using(banco).filter(
            arqu_empr=int(empresa_id),
            arqu_pedi=int(pedido_numero),
            arqu_cod_arqu=int(codigo_arquivo),
        )
        try:
            return qs.order_by("-arqu_cod_arqu").first()
        except Exception:
            return qs.first()

    @staticmethod
    def criar_ou_atualizar(banco, *, empresa_id, pedido_numero, codigo_arquivo, nome_arquivo, arquivo_bytes):
        empresa_id_int = int(empresa_id)
        pedido_numero_int = int(pedido_numero)
        codigo_int = int(codigo_arquivo) if str(codigo_arquivo).strip() != "" else 0
        nome = (str(nome_arquivo or "").strip()[:100]) or "arquivo"
        conteudo = arquivo_bytes or b""

        try:
            obj = PedidosPisosArquivos.objects.using(banco).create(
                arqu_empr=empresa_id_int,
                arqu_pedi=pedido_numero_int,
                arqu_cod_arqu=codigo_int,
                arqu_nome_arqu=nome,
                arqu_arqu=conteudo,
            )
            return obj
        except IntegrityError:
            obj = PedidosPisosArquivos.objects.using(banco).filter(
                arqu_empr=empresa_id_int,
                arqu_pedi=pedido_numero_int,
                arqu_cod_arqu=codigo_int,
            ).first()
            if not obj:
                obj = PedidosPisosArquivos.objects.using(banco).filter(
                    arqu_empr=empresa_id_int,
                    arqu_pedi=pedido_numero_int,
                ).first()
            if not obj:
                raise
            obj.arqu_nome_arqu = nome
            obj.arqu_arqu = conteudo
            obj.arqu_cod_arqu = codigo_int
            obj.save(using=banco)
            return obj

    @staticmethod
    def guess_content_type(nome_arquivo):
        name = str(nome_arquivo or "").strip()
        ctype, _ = mimetypes.guess_type(name)
        return ctype or "application/octet-stream"

