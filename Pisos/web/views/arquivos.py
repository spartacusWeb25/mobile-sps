from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect

from core.utils import get_db_from_slug
from Pisos.services.pedido_arquivos_service import PedidoPisosArquivosService


def upload_pedido_pisos_arquivo(request, slug, pk):
    if request.method != "POST":
        raise Http404()

    banco = get_db_from_slug(slug)
    empresa_id = request.session.get("empresa_id")
    if not empresa_id:
        messages.error(request, "Sessão inválida: empresa não informada.")
        return redirect("PisosWeb:pedidos_pisos_editar", slug=slug, pk=pk)

    codigo = request.POST.get("arqu_cod_arqu") or 0
    nome = (request.POST.get("arqu_nome_arqu") or "").strip()
    arquivo = request.FILES.get("arqu_arqu")

    if not arquivo:
        messages.error(request, "Selecione um arquivo para enviar.")
        return redirect("PisosWeb:pedidos_pisos_editar", slug=slug, pk=pk)

    if not nome:
        nome = getattr(arquivo, "name", "") or "arquivo"

    try:
        conteudo = arquivo.read()
    except Exception:
        messages.error(request, "Falha ao ler o arquivo enviado.")
        return redirect("PisosWeb:pedidos_pisos_editar", slug=slug, pk=pk)

    try:
        PedidoPisosArquivosService.criar_ou_atualizar(
            banco,
            empresa_id=empresa_id,
            pedido_numero=pk,
            codigo_arquivo=codigo,
            nome_arquivo=nome,
            arquivo_bytes=conteudo,
        )
        messages.success(request, "Arquivo anexado com sucesso.")
    except Exception as exc:
        messages.error(request, f"Erro ao anexar arquivo: {exc}")

    return redirect("PisosWeb:pedidos_pisos_editar", slug=slug, pk=pk)


def download_pedido_pisos_arquivo(request, slug, pk, codigo):
    banco = get_db_from_slug(slug)
    empresa_id = request.session.get("empresa_id")
    if not empresa_id:
        raise Http404()

    obj = PedidoPisosArquivosService.obter(
        banco,
        empresa_id=empresa_id,
        pedido_numero=pk,
        codigo_arquivo=codigo,
    )
    if not obj or not getattr(obj, "arqu_arqu", None):
        raise Http404()

    nome = (getattr(obj, "arqu_nome_arqu", "") or f"arquivo_{codigo}").strip()
    content_type = PedidoPisosArquivosService.guess_content_type(nome)

    resp = HttpResponse(obj.arqu_arqu, content_type=content_type)
    resp["Content-Disposition"] = f'inline; filename="{nome}"'
    return resp

