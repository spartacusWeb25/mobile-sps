# notas_fiscais/assinador_service.py

from lxml import etree
from signxml import XMLSigner, methods
from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    PrivateFormat,
    NoEncryption,
)

from .exceptions import ErroEmissao

NFE_NS = "http://www.portalfiscal.inf.br/nfe"


class AssinadorA1Service:
    """
    Serviço para assinar XML de NF-e/NFC-e usando certificado A1 (PFX/P12).

    - Recebe OBRIGATORIAMENTE os bytes crus do certificado.
    - Não mexe com criptografia, quem controla isso é o caller.
    - Garante assinatura envelopada padrão SEFAZ (xmldsig).
    """

    def __init__(self, pfx_bytes: bytes, pfx_pass: str):
        if not isinstance(pfx_bytes, (bytes, bytearray)):
            raise ErroEmissao("Certificado inválido: pfx_bytes deve ser bytes puros.")

        self.pfx_bytes = pfx_bytes
        self.pfx_pass = pfx_pass

    def _extract_key_and_cert(self):
        """
        Extrai chave privada e certificado PEM do PFX carregado na memória.

        Certificados emitidos por ACs brasileiras costumam usar RC2/3DES
        (legacy encryption, padrão do Windows). O cryptography >= 38 rejeita
        esse formato por padrão com load_key_and_certificates — nesse caso
        cai no fallback via pyOpenSSL que aceita legacy sem configuração extra.
        """
        password = self.pfx_pass.encode("utf-8") if self.pfx_pass else None

        key = None
        cert = None
        addl = []

        # Tentativa 1: API moderna do cryptography (PFX com PBES2/AES)
        try:
            key, cert, addl = pkcs12.load_key_and_certificates(self.pfx_bytes, password)
        except Exception:
            pass

        # Tentativa 2: fallback via rust/openssl legacy provider do cryptography.
        # Certificados emitidos por ACs brasileiras usam RC2/3DES (legacy encryption,
        # padrão do Windows). cryptography >= 38 rejeita via load_key_and_certificates
        # mas aceita via serialize_key_and_certificates com o backend legacy explícito,
        # ou via subprocess openssl como último recurso.
        if key is None or cert is None:
            try:
                # cryptography >= 42 expõe load_pkcs12 no módulo pkcs12 com suporte legacy
                from cryptography.hazmat.primitives.serialization.pkcs12 import (
                    load_pkcs12 as _load_pkcs12,
                )
                from cryptography.hazmat.backends.openssl.backend import backend as _ossl

                p12 = _load_pkcs12(self.pfx_bytes, password, _ossl)
                key = p12.key
                cert = p12.cert.certificate if p12.cert else None
                addl = [c.certificate for c in (p12.additional_certs or [])]

            except Exception:
                # Último recurso: subprocess openssl pkcs12 — sempre disponível no Windows
                # junto com o Python já que o cryptography instala as DLLs OpenSSL
                try:
                    import subprocess, tempfile, os

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pfx") as tmp:
                        tmp.write(self.pfx_bytes)
                        pfx_path = tmp.name

                    senha_str = self.pfx_pass or ""

                    result = subprocess.run(
                        [
                            "openssl", "pkcs12",
                            "-in", pfx_path,
                            "-passin", f"pass:{senha_str}",
                            "-legacy",
                            "-nodes",
                        ],
                        capture_output=True,
                    )
                    os.unlink(pfx_path)

                    if result.returncode != 0:
                        raise ErroEmissao(
                            f"Falha ao carregar PFX via openssl: {result.stderr.decode()}"
                        )

                    pem_output = result.stdout.decode()

                    # Extrai key e cert do PEM combinado
                    import re
                    key_match = re.search(
                        r"(-----BEGIN (?:RSA )?PRIVATE KEY-----.*?-----END (?:RSA )?PRIVATE KEY-----)",
                        pem_output, re.DOTALL
                    )
                    cert_match = re.search(
                        r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
                        pem_output, re.DOTALL
                    )

                    if not key_match or not cert_match:
                        raise ErroEmissao("PFX não contém chave ou certificado válido.")

                    return key_match.group(1), cert_match.group(1)

                except ErroEmissao:
                    raise
                except Exception as e:
                    raise ErroEmissao(
                        f"Falha ao carregar PFX: senha incorreta ou arquivo inválido. ({e})"
                    )

        if key is None or cert is None:
            raise ErroEmissao("Certificado A1 inválido ou incompleto.")

        # Converte para PEM (caminho moderno — chegou aqui, então funcionou)
        key_pem = key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption(),
        ).decode()

        cert_pem = cert.public_bytes(Encoding.PEM).decode()

        chain_pem = ""
        if addl:
            for c in addl:
                try:
                    chain_pem += c.public_bytes(Encoding.PEM).decode()
                except Exception:
                    pass

        return key_pem, cert_pem + chain_pem

    def assinar_xml(self, xml_str: str) -> str:
        """
        Assina o XML de NF-e/NFC-e, posicionando a <Signature> como irmã de <infNFe>.
        """
        try:
            root = etree.fromstring(xml_str.encode("utf-8"))
        except Exception:
            raise ErroEmissao("XML inválido para assinatura.")

        ns = {"nfe": NFE_NS}
        inf_list = root.xpath("//nfe:infNFe", namespaces=ns)

        if not inf_list:
            raise ErroEmissao("Elemento infNFe não encontrado para assinatura.")

        inf = inf_list[0]

        inf_id = inf.get("Id") or "NFeTEMP"
        inf.set("Id", inf_id)

        key_pem, cert_chain_pem = self._extract_key_and_cert()

        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
        )

        signed_root = signer.sign(
            root,
            key=key_pem,
            cert=cert_chain_pem,
            reference_uri=f"#{inf_id}",
        )

        ns_ds = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        signatures = signed_root.xpath("//ds:Signature", namespaces=ns_ds)

        if signatures:
            sig = signatures[0]
            parent = sig.getparent()

            if parent is not None and parent.tag.endswith("infNFe"):
                parent.remove(sig)
                signed_root.append(sig)

        return etree.tostring(
            signed_root,
            encoding="utf-8",
            pretty_print=False,
            xml_declaration=False,
        ).decode()