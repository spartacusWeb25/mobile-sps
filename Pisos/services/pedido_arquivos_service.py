import mimetypes

from typing import Optional

from django.db import IntegrityError

from Pisos.models import PedidosPisosArquivos


class PedidoPisosArquivosService:
    PREVIEW_EXTS = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".txt",
        ".csv",
    }

    DOWNLOAD_EXTS = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".txt",
        ".csv",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
    }

    @staticmethod
    def _ext(nome_arquivo: str) -> str:
        name = (str(nome_arquivo or "").strip() or "").lower()
        if "." not in name:
            return ""
        return "." + name.rsplit(".", 1)[-1]

    @classmethod
    def pode_exibir(cls, nome_arquivo: str) -> bool:
        return cls._ext(nome_arquivo) in cls.PREVIEW_EXTS

    @classmethod
    def pode_baixar(cls, nome_arquivo: str) -> bool:
        return cls._ext(nome_arquivo) in cls.DOWNLOAD_EXTS

    @classmethod
    def normalizar_nome(cls, nome_informado: str, nome_original_upload: Optional[str] = None) -> str:
        nome = (str(nome_informado or "").strip()[:100]) or "arquivo"
        if "." in nome:
            return nome
        ext = cls._ext(nome_original_upload or "")
        if not ext:
            return nome
        if len(nome) + len(ext) > 100:
            nome = nome[: 100 - len(ext)]
        return f"{nome}{ext}"

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
    def excluir(banco, *, empresa_id, pedido_numero, codigo_arquivo) -> bool:
        qs = PedidosPisosArquivos.objects.using(banco).filter(
            arqu_empr=int(empresa_id),
            arqu_pedi=int(pedido_numero),
            arqu_cod_arqu=int(codigo_arquivo),
        )
        try:
            deleted, _ = qs.delete()
        except Exception:
            try:
                obj = qs.first()
                if not obj:
                    return False
                obj.delete(using=banco)
                return True
            except Exception:
                return False
        return deleted > 0

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

