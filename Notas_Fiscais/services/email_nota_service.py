from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend

from Licencas.models import Filiais

from ..models import Nota

try:
    from brazilfiscalreport.danfe import Danfe
except ImportError:
    Danfe = None


def _to_bool(v) -> bool:
    return bool(v) if v is not None else False


def _obter_xml(nota: Nota) -> str:
    xml_content = nota.xml_autorizado or nota.xml_assinado or ""
    if isinstance(xml_content, (bytes, bytearray)):
        xml_content = xml_content.decode("utf-8", errors="ignore")
    xml_content = str(xml_content or "").strip()
    if xml_content:
        return xml_content
    try:
        xml_content = nota.gerar_xml()
    except Exception:
        xml_content = ""
    xml_content = str(xml_content or "").strip()
    if not xml_content:
        raise ValidationError("Nota não possui XML gerado.")
    return xml_content


def _smtp_backend_from_filial(filial: Filiais):
    host = str(getattr(filial, "empr_smtp_host", "") or "").strip()
    port_raw = str(getattr(filial, "empr_smtp_port", "") or "").strip()
    username = str(getattr(filial, "empr_smtp_usua", "") or "").strip() or None
    password = str(getattr(filial, "empr_smtp_senh", "") or "").strip() or None
    from_email = str(getattr(filial, "empr_smtp_emai", "") or "").strip() or str(getattr(filial, "empr_emai", "") or "").strip()

    if not host:
        raise ValidationError("SMTP Host não configurado na filial.")
    if not port_raw:
        raise ValidationError("SMTP Port não configurado na filial.")
    try:
        port = int(port_raw)
    except Exception:
        raise ValidationError("SMTP Port inválido na filial.")
    if not from_email:
        raise ValidationError("E-mail remetente (SMTP Email) não configurado na filial.")

    use_tls = _to_bool(getattr(filial, "empr_tls", None))
    use_ssl = _to_bool(getattr(filial, "empr_ssl", None))

    backend = EmailBackend(
        host=host,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        timeout=30,
        fail_silently=False,
    )
    return backend, from_email


def enviar_nota_por_email(
    *,
    banco: str,
    nota_id: int,
    destinatarios: list[str],
    assunto: str,
    mensagem: str,
    anexar_pdf: bool = True,
    anexar_xml: bool = True,
):
    destinatarios = [str(e or "").strip() for e in (destinatarios or []) if str(e or "").strip()]
    if not destinatarios:
        raise ValidationError("Informe ao menos um e-mail de destino.")

    nota = Nota.objects.using(banco).filter(id=nota_id).first()
    if not nota:
        raise ValidationError("Nota não encontrada.")

    filial = (
        Filiais.objects.using(banco)
        .defer("empr_cert_digi")
        .filter(empr_empr=nota.empresa, empr_codi=nota.filial)
        .first()
    )
    if not filial:
        raise ValidationError("Filial não encontrada para envio.")

    backend, from_email = _smtp_backend_from_filial(filial)

    xml_content = _obter_xml(nota)
    modelo = str(getattr(nota, "modelo", "") or "").strip()
    serie = str(getattr(nota, "serie", "") or "").strip()
    numero = str(getattr(nota, "numero", "") or "").strip()
    chave = str(getattr(nota, "chave_acesso", "") or "").strip()
    ident = chave or f"{modelo}_{serie}_{numero}_{nota.id}"

    assunto = (assunto or "").strip() or f"NF-e {modelo}-{serie} Nº {numero}"
    mensagem = (mensagem or "").strip() or f"Segue em anexo a NF-e {modelo}-{serie} Nº {numero}."

    email = EmailMessage(
        subject=assunto,
        body=mensagem,
        from_email=from_email,
        to=destinatarios,
        connection=backend,
    )

    if anexar_xml:
        email.attach(f"{ident}.xml", xml_content.encode("utf-8"), "application/xml")

    if anexar_pdf:
        if modelo == "65":
            from ..api.emitir_view import _nfce_40col_html

            html = _nfce_40col_html(xml_content)
            email.attach(f"{ident}.html", html.encode("utf-8"), "text/html")
        else:
            if Danfe is None:
                raise ValidationError("Biblioteca de impressão não instalada (BrazilFiscalReport).")
            danfe = Danfe(xml_content)
            pdf_str = danfe.output(dest="S")
            if isinstance(pdf_str, (bytes, bytearray)):
                pdf_bytes = bytes(pdf_str)
            else:
                pdf_bytes = pdf_str.encode("latin-1")
            email.attach(f"{ident}.pdf", pdf_bytes, "application/pdf")

    email.send(fail_silently=False)
    return {"nota_id": nota.id, "destinatarios": destinatarios, "assunto": assunto}
