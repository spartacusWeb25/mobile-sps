"""
core/util/__init__.py - VERSÃO COMPLETA

SUBSTITUA TODO O CONTEÚDO DO SEU core/util/__init__.py COM ISTO
"""

default_app_config = 'core.apps.CoreConfig'


def _habilitar_openssl_legacy_provider() -> bool:
    """Ativa legacy provider do OpenSSL para certificados antigos (RC2/3DES)."""
    try:
        from cryptography.hazmat.bindings.openssl.binding import Binding

        binding = Binding()
        lib = binding.lib
        ffi = binding.ffi

        if not hasattr(lib, "OSSL_PROVIDER_load"):
            return False

        lib.OSSL_PROVIDER_load(ffi.NULL, b"default")
        lib.OSSL_PROVIDER_load(ffi.NULL, b"legacy")
        return True
    except Exception:
        return False


def _normalizar_pfx_bytes(pfx_bytes: bytes) -> bytes:
    """
    Normaliza bytes do certificado PFX (raw ou base64).
    """
    import base64

    if not isinstance(pfx_bytes, (bytes, bytearray)) or not pfx_bytes:
        raise ValueError("Conteúdo do certificado A1 (pfx) inválido")

    pfx_bytes = bytes(pfx_bytes)

    if pfx_bytes[:2] == b"\x30\x82":
        return pfx_bytes

    try:
        decoded = base64.b64decode(pfx_bytes)
        if decoded[:2] == b"\x30\x82":
            return decoded
    except Exception:
        pass

    return pfx_bytes


def _resolver_openssl_exe() -> str | None:
    """Encontra o executável do openssl no sistema."""
    import os
    import shutil

    exe = shutil.which("openssl")
    if exe and os.path.isfile(exe):
        return exe

    candidatos = [
        r"C:\Program Files\Git\usr\bin\openssl.exe",
        r"C:\Program Files\Git\mingw64\bin\openssl.exe",
        r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
        r"C:\OpenSSL-Win64\bin\openssl.exe",
        r"C:\Program Files (x86)\OpenSSL-Win32\bin\openssl.exe",
        r"C:\OpenSSL-Win32\bin\openssl.exe",
    ]
    for p in candidatos:
        if os.path.isfile(p):
            return p

    return None


def _extrair_pem_via_openssl(pfx_bytes: bytes, senha_pfx: str):
    """
    Extrai chave e certificado usando openssl via subprocess.
    Último recurso quando cryptography falha.
    """
    import os
    import re
    import subprocess
    import tempfile

    openssl_exe = _resolver_openssl_exe()
    if not openssl_exe:
        raise FileNotFoundError("openssl não encontrado")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pfx") as tmp:
        tmp.write(pfx_bytes)
        pfx_path = tmp.name

    senha_str = senha_pfx or ""
    try:
        args = [
            openssl_exe,
            "pkcs12",
            "-in",
            pfx_path,
            "-passin",
            f"pass:{senha_str}",
            "-legacy",
            "-nodes",
        ]
        result = subprocess.run(args, capture_output=True)
        if result.returncode != 0:
            stderr_txt = (result.stderr or b"").decode(errors="ignore").lower()
            if "unknown option" in stderr_txt and "-legacy" in " ".join(args):
                args = [
                    openssl_exe,
                    "pkcs12",
                    "-in",
                    pfx_path,
                    "-passin",
                    f"pass:{senha_str}",
                    "-nodes",
                ]
                result = subprocess.run(args, capture_output=True)
    finally:
        try:
            os.unlink(pfx_path)
        except Exception:
            pass

    if result.returncode != 0:
        raise ValueError("PFX inválido ou senha incorreta")

    pem_output = (result.stdout or b"").decode(errors="ignore")
    key_match = re.search(
        r"(-----BEGIN (?:RSA )?PRIVATE KEY-----.*?-----END (?:RSA )?PRIVATE KEY-----)",
        pem_output,
        re.DOTALL,
    )
    cert_match = re.search(
        r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
        pem_output,
        re.DOTALL,
    )
    if not key_match or not cert_match:
        raise ValueError("PFX inválido ou senha incorreta")

    key_pem = key_match.group(1)
    cert_chain_pem = pem_output[pem_output.find(cert_match.group(1)) :].strip()
    return key_pem, cert_chain_pem


def extrair_key_pem_e_cert_chain_pem_de_pfx(pfx_bytes: bytes, senha_pfx: str):
    """
    Extrai chave privada e certificado do PFX com fallbacks.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption

    pfx_bytes = _normalizar_pfx_bytes(pfx_bytes)
    password = senha_pfx.encode("utf-8") if senha_pfx else None

    key = None
    cert = None
    addl = []

    try:
        key, cert, addl = pkcs12.load_key_and_certificates(pfx_bytes, password)
    except Exception:
        pass

    if key is None or cert is None:
        _habilitar_openssl_legacy_provider()
        try:
            key, cert, addl = pkcs12.load_key_and_certificates(pfx_bytes, password)
        except Exception:
            pass

    if key is None or cert is None:
        try:
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_pkcs12 as _load_pkcs12

            try:
                p12 = _load_pkcs12(pfx_bytes, password)
            except TypeError:
                from cryptography.hazmat.backends.openssl.backend import backend as _ossl

                p12 = _load_pkcs12(pfx_bytes, password, _ossl)

            key = getattr(p12, "key", None)
            cert = p12.cert.certificate if getattr(p12, "cert", None) else None
            addl = [c.certificate for c in (getattr(p12, "additional_certs", None) or [])]
        except Exception:
            pass

    if key is None or cert is None:
        try:
            return _extrair_pem_via_openssl(pfx_bytes, senha_pfx)
        except FileNotFoundError:
            raise ValueError("PFX inválido ou senha incorreta")

    key_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    cert_chain_pem = cert.public_bytes(Encoding.PEM).decode()
    if addl:
        for c in addl:
            try:
                cert_chain_pem += c.public_bytes(Encoding.PEM).decode()
            except Exception:
                pass

    return key_pem, cert_chain_pem


def criar_arquivos_pem_temporarios_de_pfx_bytes(pfx_bytes: bytes, senha_pfx: str):
    import tempfile
    try:
        key_pem, cert_chain_pem = extrair_key_pem_e_cert_chain_pem_de_pfx(pfx_bytes, senha_pfx)
    except Exception as e:
        raise ValueError(f"Certificado A1 (PFX) inválido ou senha incorreta. Erro: {str(e)}") from e

    cert_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    cert_tmp.write(cert_chain_pem.encode("utf-8"))
    cert_tmp.flush()
    cert_tmp.close()

    key_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_tmp.write(key_pem.encode("utf-8"))
    key_tmp.flush()
    key_tmp.close()

    return cert_tmp.name, key_tmp.name


def carregar_certificado_pfx(pfx_bytes: bytes, senha_pfx: str):
    if not isinstance(pfx_bytes, (bytes, bytearray)):
        raise TypeError(f"PFX deve ser bytes, recebido: {type(pfx_bytes)}")

    if not pfx_bytes:
        raise ValueError("Certificado PFX vazio")

    return criar_arquivos_pem_temporarios_de_pfx_bytes(pfx_bytes, senha_pfx)


def criar_arquivos_pem_temporarios_de_pfx_arquivo(
    caminho_pfx: str, senha_pfx: str
):
    """
    Carrega certificado PFX de um arquivo e cria arquivos PEM.
    
    Wrapper convenience que lê arquivo e chama carregar_certificado_pfx().
    """
    import os
    
    if not caminho_pfx or not os.path.isfile(caminho_pfx):
        raise ValueError("Certificado A1 (pfx) não encontrado no caminho")
    
    with open(caminho_pfx, "rb") as f:
        pfx_bytes = f.read()
    
    return carregar_certificado_pfx(pfx_bytes, senha_pfx)
