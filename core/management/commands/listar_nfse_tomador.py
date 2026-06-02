from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone
from core.registry import get_licenca_db_config
from Licencas.models import Filiais
from Licencas.crypto import decrypt_bytes, decrypt_str
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
import json


class Command(BaseCommand):
    help = "Valida certificado A1 (opcional) e lista NFS-e para um tomador (CPF/CNPJ). Saída em JSON."

    def add_arguments(self, parser):
        parser.add_argument("--tomador", type=str, required=True, help="Documento do tomador (CPF/CNPJ) a buscar no campo nfse_tom_doc")
        parser.add_argument("--empresa", type=int, default=None, help="(opcional) empresa para validar certificado")
        parser.add_argument("--filial", type=int, default=None, help="(opcional) filial para validar certificado")
        parser.add_argument("--alias", type=str, default=None, help="(opcional) alias de DB Django (ex: default)")
        parser.add_argument("--slug", type=str, default=None, help="(opcional) slug da licença para resolver alias via loader")

    def handle(self, *args, **options):
        tomador = options.get("tomador")
        empresa = options.get("empresa")
        filial = options.get("filial")
        alias = options.get("alias")
        slug = options.get("slug")

        if slug:
            alias = get_licenca_db_config(slug)
        if not alias:
            alias = "default"

        if alias not in connections:
            raise CommandError(f"Alias de banco de dados inválido: {alias}")

        result = {
            "query_tomador": tomador,
            "alias": alias,
            "validated_cert": False,
            "cert_subject": None,
            "cert_issuer": None,
            "nfse_count": 0,
            "nfse": [],
            "timestamp": timezone.now().isoformat(),
        }

        # if empresa+filial provided, try to validate certificate like test_cert_a1
        if empresa and filial:
            filial_obj = (
                Filiais.objects.using(alias).filter(empr_empr=empresa, empr_codi=filial).first()
            )
            if not filial_obj:
                raise CommandError(f"Filial não encontrada (empresa={empresa}, filial={filial}) no alias {alias}")

            if getattr(filial_obj, 'empr_cert_digi', None):
                senha_token = filial_obj.empr_senh_cert
                cert_token = filial_obj.empr_cert_digi

                # decrypt senha
                try:
                    senha = decrypt_str(senha_token)
                except Exception:
                    senha = senha_token

                # decrypt certificado
                try:
                    cert_bytes = decrypt_bytes(cert_token)
                except Exception:
                    cert_bytes = cert_token
                    if hasattr(cert_bytes, "tobytes"):
                        cert_bytes = cert_bytes.tobytes()

                if not isinstance(cert_bytes, (bytes, bytearray)):
                    # keep going but mark as invalid
                    result["validated_cert"] = False
                else:
                    try:
                        key, cert, add_certs = load_key_and_certificates(
                            cert_bytes,
                            senha.encode("utf-8") if isinstance(senha, str) else senha,
                        )
                        if cert is not None:
                            result["validated_cert"] = True
                            result["cert_subject"] = cert.subject.rfc4514_string() if hasattr(cert, 'subject') else None
                            result["cert_issuer"] = cert.issuer.rfc4514_string() if hasattr(cert, 'issuer') else None
                        else:
                            result["validated_cert"] = False
                    except Exception as e:
                        result["validated_cert"] = False
                        result["cert_error"] = repr(e)
            else:
                result["validated_cert"] = False
                result["cert_error"] = "Filial sem empr_cert_digi"

        # Query NFSe table for tomador document
        try:
            from nfse.models import Nfse
        except Exception:
            raise CommandError("Aplicação nfse não encontrada no projeto")

        q = Nfse.objects.using(alias).filter(nfse_tom_doc=tomador)
        # if empresa/filial provided, further filter
        if empresa:
            q = q.filter(nfse_empr=empresa)
        if filial:
            q = q.filter(nfse_fili=filial)

        # select fields
        qs = q.values(
            'nfse_id', 'nfse_empr', 'nfse_fili', 'nfse_nume', 'nfse_rps_nume',
            'nfse_pres_nome', 'nfse_pres_doc',
            'nfse_tom_nome', 'nfse_tom_doc',
            'nfse_val_serv', 'nfse_data_emis', 'nfse_statu', 'nfse_muni_nome'
        ).order_by('nfse_empr', 'nfse_fili', 'nfse_data_emis', 'nfse_nume')

        items = list(qs)
        result['nfse_count'] = len(items)
        # convert decimals/datetimes to strings via default=str in json dump
        result['nfse'] = items

        # output JSON
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
