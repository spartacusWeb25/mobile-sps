from django.db import connection
from django.contrib.auth.hashers import make_password
from core.middleware import get_licenca_slug
from core.registry import get_licenca_db_config
from django.http import HttpRequest

from perfilweb.services import get_perfil_ativo, tem_permissao
from .models import Usuarios, Empresas, Filiais
from django.db.models import Max

def proximo_usuario(request: HttpRequest):
    """Gera próximo número de usuário"""
    banco = get_licenca_db_config(request) or 'default'
    
    return get_proximo_usuario(banco)

def atualizar_senha(username, nova_senha, request=None):

    try:
        if request:
            banco = get_licenca_db_config(request) or 'default'
            if banco != "default":
                # Usar SQL direto para evitar problemas com tabelas de permissões
                from django.db import connections
                db_connection = connections[banco]
                with db_connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE usuarios SET usua_senh_mobi = %s WHERE usua_nome = %s",
                        [nova_senha, username]
                    )
                    if cursor.rowcount == 0:
                        raise Exception(f"Usuário {username} não encontrado no banco {banco}.")
                    print(f"Senha do usuário {username} atualizada com sucesso no banco {banco}.")
                    return True
        
        # Fallback para conexão padrão
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE usuarios SET usua_senh_mobi = %s WHERE usua_nome = %s",
                [nova_senha, username]
            )
            if cursor.rowcount == 0:
                raise Exception(f"Usuário {username} não encontrado.")
        print(f"Senha do usuário {username} atualizada com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao atualizar a senha do usuário {username}: {e}")
        raise e


def get_proximo_usuario(banco):
    """Gera próximo número de usuário"""
    maior = Usuarios.objects.using(banco).aggregate(Max('usua_codi'))['usua_codi__max'] or 0
    print(f"Maior usuário encontrado: {maior}")
    return maior + 1


def get_proxima_empresa(banco):
    """Gera próximo número de empresa"""
    maior = Empresas.objects.using(banco).aggregate(Max('empr_codi'))['empr_codi__max'] or 0
    print(f"Maior empresa encontrado: {maior}")
    return maior + 1

def get_proxima_filial(banco):
    """Gera próximo número de filial"""
    maior = Filiais.objects.using(banco).aggregate(Max('empr_codi'))['empr_codi__max'] or 0
    print(f"Maior filial encontrado: {maior}")
    return maior + 1

def get_proxima_filial_empr(banco):
    """Gera próximo número de filial"""
    maior = Filiais.objects.using(banco).aggregate(Max('empr_empr'))['empr_empr__max'] or 0
    print(f"Maior filial encontrado: {maior}")
    return maior + 1

def buscar_endereco(cep):
    """Busca endereço a partir de um CEP"""
    import requests
    url = f"https://viacep.com.br/ws/{cep}/json/"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'erro' not in data:
            ibge = str(data.get('ibge') or '')
            estado_codigo = ibge[:2] if ibge else None
            return {
                "cep": data.get("cep"),
                "logradouro": data.get("logradouro"),
                "complemento": data.get("complemento"),
                "bairro": data.get("bairro"),
                "cidade": data.get("localidade"),
                "estado": data.get("uf"),
                "pais": "Brasil",
                "codi_pais": "1058",
                "ibge": ibge,
                "estado_codigo": estado_codigo,
            }
    return None

def buscar_endereco_por_cep(cep):
    """Alias para compatibilidade: retorna o mesmo que buscar_endereco"""
    return buscar_endereco(cep)

def get_auth_menu_flags(usuario):
    perfil = get_perfil_ativo(usuario)
    AUTH_MENU_FLAGS = [{
        "nome": "perfis",
        "acao": "listar",
        "app_label": "Licencas",
        "model": "usuarios"
    },{
        "nome": "empresas",
        "acao": "listar",
        "app_label": "Licencas",
        "model": "empresas"
    },{
        "nome": "filiais",
        "acao": "listar",
        "app_label": "Licencas",
        "model": "filiais"
    },{
        "nome": "cfop",
        "acao": "listar",
        "app_label": "cfop",
        "model": "cfop"
    },{
        "nome": "series",
        "acao": "listar",
        "app_label": "series",
        "model": "series"
    },{
        "nome": "importador de produtos",
        "acao": "criar",
        "app_label": "Produtos",
        "model": "produtos"
    },{
        "nome": "importador de entidades",
        "acao": "criar",
        "app_label": "Entidades",
        "model": "entidades"
    },{
        "nome": "perfis/usuários",
        "acao": "listar",
        "app_label": "Licencas",
        "model": "usuarios"
    },{
        "nome": "parametrizações de módulos",
        "acao": "listar",
        "app_label": "parametros_admin",
        "model": "modulos"
    },{
        "nome": "parametrizações de parâmetros",
        "acao": "listar",
        "app_label": "parametros_admin",
        "model": "parametrossistema"
    }]

    return { flag["nome"]: tem_permissao(
            perfil=perfil,
            app_label=flag["app_label"],
            model=flag["model"],
            acao=flag["acao"]
        ) 
        for flag in AUTH_MENU_FLAGS }
        
