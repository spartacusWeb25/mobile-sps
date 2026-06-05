import logging
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError, NotFound

from .models import NotaFiscalEntrada
from django.db.models import Q
from .serializers import NotaFiscalEntradaSerializer, NotaFiscalEntradaListSerializer
from Entidades.models import Entidades
from Licencas.models import Filiais
from core.utils import get_licenca_db_config
from contas_a_pagar.serializers import TitulospagarSerializer
from Entradas_Estoque.REST.serializers import EntradasEstoqueSerializer
from notificacoes.models import Notificacao
from contas_a_pagar.models import Titulospagar
from Produtos.models import Produtos, UnidadeMedida
import xml.etree.ElementTree as ET

logger = logging.getLogger('NotasDestinadas')

class NotasDestinadasViewSet(viewsets.ModelViewSet):
    serializer_class = NotaFiscalEntradaSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ['numero_nota_fiscal','emitente_razao_social','natureza_operacao']
    filterset_fields = ['empresa','filial','data_emissao','status_nfe']

    def get_queryset(self):
        banco = get_licenca_db_config(self.request)
        qs = NotaFiscalEntrada.objects.using(banco).all()
        # Coletar parâmetros de contexto
        cnpj = self.request.query_params.get('cnpj')
        empresa_id = (
            self.request.query_params.get('empresa_id') or
            self.request.headers.get('X-Empresa') or
            self.request.session.get('empresa_id')
        )
        filial_id = (
            self.request.query_params.get('filial_id') or
            self.request.headers.get('X-Filial') or
            self.request.session.get('filial_id')
        )
       
        if not cnpj and empresa_id and filial_id:
            try:
                filial = Filiais.objects.using(banco).filter(
                    empr_empr=int(filial_id),
                    empr_codi=int(empresa_id)
                ).first()
                if filial and filial.empr_docu:
                    import re
                    cnpj = re.sub(r"\D", "", filial.empr_docu)
            except Exception:
                cnpj = None
        # Filtro principal por CNPJ do destinatário
        if cnpj:
            import re
            cnpj_digits = re.sub(r"\D", "", str(cnpj))
            def mask(v):
                return f"{v[0:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:14]}" if len(v)==14 else v
            variants = [cnpj_digits, mask(cnpj_digits)]
            qs = qs.filter(Q(destinatario_cnpj__in=variants)).exclude(Q(emitente_cnpj__in=variants))
        # Fallback: tentar por empresa/filial, se fornecidos
        elif empresa_id and filial_id:
            try:
                qs = qs.filter(empresa=int(empresa_id), filial=int(filial_id))
            except Exception:
                pass
        qs = qs.order_by('-data_emissao','-numero_nota_fiscal')
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = NotaFiscalEntradaListSerializer(page, many=True, context={'banco': get_licenca_db_config(request)})
            return self.get_paginated_response(serializer.data)
        serializer = NotaFiscalEntradaListSerializer(queryset, many=True, context={'banco': get_licenca_db_config(request)})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request, *args, **kwargs):
        qs = self.get_queryset()
        total = qs.count()
        autorizadas = qs.filter(status_nfe=100).count()
        canceladas = qs.filter(cancelada=True).count()
        pendentes = qs.exclude(status_nfe=100).exclude(cancelada=True).count()
        from django.db.models import Sum
        valor_total = qs.aggregate(total=Sum('valor_total_nota'))['total'] or 0
        return Response({'total_notas': total,'autorizadas': autorizadas,'canceladas': canceladas,'pendentes': pendentes,'valor_total': valor_total})

    def _parse_itens(self, nota):
        itens = []
        try:
            if not nota.xml_nfe:
                return itens
            root = ET.fromstring(nota.xml_nfe)
            for det in root.findall('.//det'):
                prod = det.find('prod')
                if prod is None:
                    continue
                n_item = det.get('nItem') or ''
                cprod = (prod.findtext('cProd') or '').strip()
                xprod = (prod.findtext('xProd') or '').strip()
                ncm = (prod.findtext('NCM') or '').strip()
                cfop = (prod.findtext('CFOP') or '').strip()
                ucom = (prod.findtext('uCom') or '').strip()
                qcom = prod.findtext('qCom')
                vun = prod.findtext('vUnCom')
                vprod = prod.findtext('vProd')
                cean = (prod.findtext('cEAN') or '').strip()
                try:
                    qcom = float(qcom) if qcom is not None else None
                except:
                    qcom = None
                try:
                    vun = float(vun) if vun is not None else None
                except:
                    vun = None
                try:
                    vprod = float(vprod) if vprod is not None else None
                except:
                    vprod = None
                itens.append({
                    'nItem': n_item,
                    'forn_cod': cprod,
                    'descricao': xprod,
                    'ncm': ncm,
                    'cfop': cfop,
                    'unidade': ucom,
                    'quantidade': qcom,
                    'valor_unit': vun,
                    'valor_total': vprod,
                    'ean': cean
                })
        except Exception:
            itens = []
        return itens

    @action(detail=True, methods=['get'])
    def itens(self, request, pk=None, empresa=None, filial=None, numero=None, slug=None):
        banco = get_licenca_db_config(request)
        nota = None
        if pk:
            try:
                nota = NotaFiscalEntrada.objects.using(banco).filter(pk=int(pk)).first()
            except Exception:
                nota = None
        if not nota:
            empresa = empresa or request.query_params.get('empresa') or request.data.get('empresa')
            filial = filial or request.query_params.get('filial') or request.data.get('filial')
            numero = numero or request.query_params.get('numero') or request.data.get('numero')
            if not all([empresa, filial, numero]):
                return Response({'error': 'empresa, filial e numero são obrigatórios'}, status=400)
            nota = NotaFiscalEntrada.objects.using(banco).filter(empresa=empresa, filial=filial, numero_nota_fiscal=numero).first()
        if not nota:
            return Response({'error': 'Nota fiscal não encontrada'}, status=404)
        itens = self._parse_itens(nota)
        return Response({'itens': itens})

    @action(detail=True, methods=['get'])
    def preprocessar(self, request, pk=None, empresa=None, filial=None, numero=None, slug=None):
        banco = get_licenca_db_config(request)
        nota = None
        if pk:
            try:
                nota = NotaFiscalEntrada.objects.using(banco).filter(pk=int(pk)).first()
            except Exception:
                nota = None
        if not nota:
            empresa = empresa or request.query_params.get('empresa') or request.data.get('empresa')
            filial = filial or request.query_params.get('filial') or request.data.get('filial')
            numero = numero or request.query_params.get('numero') or request.data.get('numero')
            if not all([empresa, filial, numero]):
                return Response({'error': 'empresa, filial e numero são obrigatórios'}, status=400)
            nota = NotaFiscalEntrada.objects.using(banco).filter(empresa=empresa, filial=filial, numero_nota_fiscal=numero).first()
        if not nota:
            return Response({'error': 'Nota fiscal não encontrada'}, status=404)
        from .services.entrada_nfe_service import EntradaNFeService
        itens = EntradaNFeService.listar_itens(nota_entrada=nota)
        sugeridos = []
        for it in itens:
            prod = None
            if it.get('ean'):
                prod = Produtos.objects.using(banco).filter(prod_coba=it['ean'], prod_empr=str(nota.empresa)).first()
            if not prod and it.get('forn_cod'):
                prod = Produtos.objects.using(banco).filter(prod_codi=it['forn_cod'], prod_empr=str(nota.empresa)).first()
            su = dict(it)
            su['produto_sugerido'] = str(prod.prod_codi) if prod else None
            su['produto_nome'] = str(prod.prod_nome) if prod else None
            sugeridos.append(su)
        return Response({'itens': sugeridos})

    @action(detail=True, methods=['post'])
    def processar(self, request, pk=None, empresa=None, filial=None, numero=None, slug=None):
        try:
            banco = get_licenca_db_config(request)
            empresa = empresa or request.query_params.get('empresa') or request.data.get('empresa')
            filial = filial or request.query_params.get('filial') or request.data.get('filial')
            numero = numero or request.query_params.get('numero') or request.data.get('numero')
            if not all([empresa, filial, numero]):
                raise ValidationError({'error':'empresa, filial e numero são obrigatórios'})
            nota = NotaFiscalEntrada.objects.using(banco).filter(empresa=empresa, filial=filial, numero_nota_fiscal=numero).first()
            if not nota:
                raise NotFound('Nota fiscal não encontrada')
            if not request.data.get('entradas'):
                raise ValidationError({'error': 'entradas são obrigatórias para processamento'})
            from .services.entrada_nfe_service import EntradaNFeService
            result = EntradaNFeService.confirmar_processamento(
                nota_entrada=nota,
                entradas=list(request.data.get('entradas', [])),
                banco=banco,
                usuario_id=getattr(request.user, 'usua_codi', 0),
            )
            if result.get('status') == 'titulo_existente':
                return Response({'error': 'Título já existe', **result}, status=409)
            Notificacao.objects.using(banco).create(usuario=request.user,titulo='Processamento de NF',mensagem='NF destinada confirmada com contas a pagar e entradas de estoque.',tipo='NF')
            return Response({'message':'Processamento concluído.', **result})
        except ValidationError as e:
            return Response({'error': e.detail}, status=400)
        except Exception:
            return Response({'error': 'Erro ao processar nota destinada.'}, status=500)

    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None, empresa=None, filial=None, numero=None, slug=None):
        return self.processar(request, pk, empresa, filial, numero, slug)

    @action(detail=True, methods=['post'])
    def manifestar(self, request, pk=None, empresa=None, filial=None, numero=None, slug=None):
        try:
            banco = get_licenca_db_config(request)
            empresa = empresa or request.query_params.get('empresa') or request.data.get('empresa')
            filial = filial or request.query_params.get('filial') or request.data.get('filial')
            numero = numero or request.query_params.get('numero') or request.data.get('numero')
            if not all([empresa, filial, numero]):
                return Response({'error': 'empresa, filial e numero são obrigatórios'}, status=400)
            nota = NotaFiscalEntrada.objects.using(banco).filter(empresa=empresa, filial=filial, numero_nota_fiscal=numero).first()
            if not nota:
                return Response({'error': 'Nota fiscal não encontrada'}, status=404)
            uf = request.data.get('uf')
            cnpj = request.data.get('cnpj_destinatario')
            caminho_pfx = request.data.get('caminho_pfx')
            senha_pfx = request.data.get('senha_pfx')
            try:
                ambiente = int(request.data.get('ambiente') or 1)
            except Exception:
                ambiente = 1
            if not all([uf, cnpj, caminho_pfx, senha_pfx]):
                try:
                    f = Filiais.objects.using(banco).filter(empr_empr=int(filial), empr_codi=int(empresa)).first()
                    if f:
                        uf = uf or (f.empr_esta or '')
                        cnpj = cnpj or (f.empr_docu or '')
                        caminho_pfx = caminho_pfx or (f.empr_cert or '')
                        senha_pfx = senha_pfx or (f.empr_senh_cert or '')
                        try:
                            ambiente = ambiente or int(f.empr_ambi_nfe or 1)
                        except Exception:
                            ambiente = ambiente or 1
                        # Se senha estiver criptografada ou certificado binário estiver salvo, preparar corretamente
                        try:
                            from Licencas.crypto import decrypt_str, decrypt_bytes
                            import os
                            if f.empr_senh_cert:
                                try:
                                    senha_pfx = decrypt_str(f.empr_senh_cert)
                                except Exception:
                                    senha_pfx = senha_pfx
                            if (not caminho_pfx or not os.path.isfile(caminho_pfx)) and f.empr_cert_digi:
                                import tempfile
                                data = decrypt_bytes(f.empr_cert_digi)
                                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.p12')
                                tmp.write(data)
                                tmp.flush()
                                caminho_pfx = tmp.name
                        except Exception:
                            pass
                except Exception:
                    pass
                if not all([uf, cnpj, caminho_pfx, senha_pfx]):
                    return Response({'error': 'Campos obrigatórios: uf, cnpj_destinatario, caminho_pfx, senha_pfx'}, status=400)
            try:
                import re
                cnpj = re.sub(r"\D", "", str(cnpj or ''))
            except Exception:
                pass
            from .services.manifestacao_service import ManifestacaoService
            resp = ManifestacaoService.manifestar_ciencia(
                nota_entrada=nota,
                uf=uf,
                cnpj_destinatario=cnpj,
                caminho_pfx=caminho_pfx,
                senha_pfx=senha_pfx,
                ambiente=ambiente,
            )
            return Response({'status': 'manifestado', 'protocolo': getattr(resp, 'protocolo', None)})
        except Exception:
            return Response({'error': 'Erro ao manifestar ciência'}, status=500)

    @action(detail=True, methods=['post'])
    def criar_produto(self, request, pk=None, empresa=None, filial=None, numero=None, slug=None):
        try:
            banco = get_licenca_db_config(request)
            empresa = empresa or request.query_params.get('empresa') or request.data.get('empresa')
            filial = filial or request.query_params.get('filial') or request.data.get('filial')
            numero = numero or request.query_params.get('numero') or request.data.get('numero')
            if not all([empresa, filial, numero]):
                return Response({'error': 'empresa, filial e numero são obrigatórios'}, status=400)
            nota = NotaFiscalEntrada.objects.using(banco).filter(empresa=empresa, filial=filial, numero_nota_fiscal=numero).first()
            if not nota:
                return Response({'error': 'Nota fiscal não encontrada'}, status=404)
            item = request.data.get('item') or {}
            cod = (item.get('forn_cod') or item.get('cProd') or '').strip()
            nome = item.get('descricao') or item.get('xProd')
            un = item.get('unidade') or item.get('uCom')
            ncm = item.get('ncm') or ''
            ean = item.get('ean') or ''
            if not nome or not un:
                return Response({'error': 'Campos obrigatórios: nome, un'}, status=400)
            un_obj = UnidadeMedida.objects.using(banco).filter(unid_codi=un).first()
            if not un_obj:
                return Response({'error': 'Unidade não encontrada'}, status=404)
            empresa_str = str(nota.empresa)
            if cod:
                existente = Produtos.objects.using(banco).filter(prod_codi=cod, prod_empr=empresa_str).first()
                if existente:
                    return Response({'produto': existente.prod_codi, 'status': 'ja_existente'})
            else:
                ultimo = Produtos.objects.using(banco).filter(prod_empr=empresa_str).order_by('-prod_codi').first()
                try:
                    proximo = int(getattr(ultimo, 'prod_codi', '0')) + 1 if (ultimo and str(getattr(ultimo, 'prod_codi', '')).isdigit()) else 1
                except Exception:
                    proximo = 1
                while Produtos.objects.using(banco).filter(prod_codi=str(proximo), prod_empr=empresa_str).exists():
                    proximo += 1
                cod = str(proximo)
            novo = Produtos.objects.using(banco).create(
                prod_empr=empresa_str,
                prod_codi=cod,
                prod_codi_nume=cod,
                prod_nome=nome,
                prod_unme=un_obj,
                prod_ncm=ncm or '',
                prod_coba=ean or ''
            )
            return Response({'produto': novo.prod_codi, 'status': 'criado'})
        except Exception:
            return Response({'error': 'Erro ao criar produto a partir da nota'}, status=500)

    @action(detail=False, methods=['get'])
    def buscar_produtos(self, request, slug=None):
        banco = get_licenca_db_config(request)
        q = request.query_params.get('q') or ''
        empresa_id = (
            request.query_params.get('empresa_id') or
            request.headers.get('X-Empresa') or
            request.session.get('empresa_id')
        )
        if not q:
            return Response({'results': []})
        qs = Produtos.objects.using(banco).all()
        try:
            if empresa_id:
                qs = qs.filter(prod_empr=str(int(empresa_id)))
        except Exception:
            pass
        from django.db.models import Q as QD
        qs = qs.filter(QD(prod_codi__icontains=q) | QD(prod_nome__icontains=q) | QD(prod_coba__icontains=q)).select_related('prod_unme')[:20]
        results = []
        for p in qs:
            results.append({
                'codigo': p.prod_codi,
                'nome': p.prod_nome,
                'ean': p.prod_coba,
                'unidade': p.prod_unme.unid_codi if p.prod_unme else ''
            })
        return Response({'results': results})

    @action(detail=False, methods=['get'])
    def config(self, request, slug=None):
        banco = get_licenca_db_config(request)
        empresa_id = (
            request.headers.get('X-Empresa') or
            request.session.get('empresa_id') or
            request.query_params.get('empresa_id')
        )
        filial_id = (
            request.headers.get('X-Filial') or
            request.session.get('filial_id') or
            request.query_params.get('filial_id')
        )
        try:
            f = None
            if empresa_id and filial_id:
                f = Filiais.objects.using(banco).filter(empr_empr=int(filial_id), empr_codi=int(empresa_id)).first()
            if not f:
                return Response({'error': 'Filial não encontrada'}, status=404)
            import re
            cnpj_digits = re.sub(r"\D", "", str(f.empr_docu or ''))
            ambiente = None
            try:
                ambiente = int(f.empr_ambi_nfe or 1)
            except Exception:
                ambiente = 1
            return Response({
                'uf': f.empr_esta or '',
                'cnpj': cnpj_digits,
                'ultimo_nsu': str(f.empr_nsu or '0'),
                'caminho_pfx': f.empr_cert or '',
                'ambiente': ambiente,
                'empresa': int(empresa_id),
                'filial': int(filial_id),
            })
        except Exception:
            return Response({'error': 'Erro ao carregar configuração da filial'}, status=500)


class ImportarNotasDestinadasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from .serializers import (
            NotaFiscalEntradaSerializer,
            ImportarNotasDestinadasSerializer,
        )
        from .services.notas_destinadas_service import NotasDestinadasService
        from .services.entrada_nfe_service import EntradaNFeService
        from .services.manifestacao_service import ManifestacaoService
        banco = get_licenca_db_config(request)

        serializer = ImportarNotasDestinadasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        uf = data.get('uf')
        cnpj = data.get('cnpj')
        ultimo_nsu = data.get('ultimo_nsu') or '0'
        caminho_pfx = data.get('caminho_pfx')
        senha_pfx = data.get('senha_pfx')
        ambiente = data.get('ambiente') or 1
        empresa = (
            request.headers.get('X-Empresa') or
            request.session.get('empresa_id') or
            data.get('empresa')
        )
        filial = (
            request.headers.get('X-Filial') or
            request.session.get('filial_id') or
            data.get('filial')
        )
        cliente = data.get('cliente')
        gerar_estoque = data['gerar_estoque']
        gerar_contas_pagar = data['gerar_contas_pagar']
        manifestar_ciencia = data['manifestar_ciencia']

        try:
            f = Filiais.objects.using(banco).filter(empr_empr=int(filial), empr_codi=int(empresa)).first()
            if f:
                uf = (f.empr_esta or uf or '')
                cnpj = (f.empr_docu or cnpj or '')
                ultimo_nsu = (f.empr_nsu or ultimo_nsu or '0')
                caminho_pfx = (f.empr_cert or caminho_pfx or '')
                senha_pfx = (f.empr_senh_cert or senha_pfx or '')
                try:
                    from Licencas.crypto import decrypt_str
                    if f.empr_senh_cert:
                        senha_pfx = decrypt_str(f.empr_senh_cert)
                except Exception:
                    pass
                try:
                    if f.empr_cert_digi:
                        from Licencas.crypto import decrypt_bytes
                        import tempfile
                        data = decrypt_bytes(f.empr_cert_digi)
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pfx')
                        tmp.write(data)
                        tmp.flush()
                        tmp.close()
                        caminho_pfx = tmp.name
                except Exception:
                    pass
                try:
                    ambiente = int(f.empr_ambi_nfe or ambiente or 1)
                except Exception:
                    ambiente = ambiente or 1
        except Exception:
            pass

        try:
            import os
            caminho_pfx = (caminho_pfx or '').strip()
            logger.info(f'DF-e: caminho_pfx inicial="{caminho_pfx}"')
            if caminho_pfx.startswith('~'):
                caminho_pfx = os.path.expanduser(caminho_pfx)
            if caminho_pfx:
                caminho_pfx = os.path.normpath(caminho_pfx)
            if not caminho_pfx or not os.path.isfile(caminho_pfx):
                try:
                    f2 = Filiais.objects.using(banco).filter(empr_empr=int(filial), empr_codi=int(empresa)).first()
                    
                    if f2 and f2.empr_cert_digi:
                        from Licencas.crypto import decrypt_bytes
                        import tempfile
                        try:
                            token = f2.empr_cert_digi
                            pkcs12_invalid = False
                            invalid_token = False
                            try:
                                import cryptography.fernet
                                if isinstance(token, memoryview):
                                    token = token.tobytes()
                                elif isinstance(token, bytearray):
                                    token = bytes(token)
                                elif isinstance(token, str):
                                    token = token.encode('utf-8')
                                data = decrypt_bytes(token)
                            except cryptography.fernet.InvalidToken:
                                logger.exception('DF-e: token de certificado inválido (SECRET_KEY divergente?).')
                                invalid_token = True
                                data = None
                            if not data:
                                try:
                                    from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                                    load_key_and_certificates(token, (senha_pfx or '').encode('utf-8'))
                                    data = token
                                    logger.info('DF-e: usando token bruto como arquivo PKCS12 válido.')
                                except Exception:
                                    pkcs12_invalid = True
                                    data = None
                            if data:
                                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pfx')
                                tmp.write(data)
                                tmp.flush()
                                tmp.close()
                                caminho_pfx = tmp.name
                                logger.info('DF-e: certificado binário da filial gravado em arquivo temporário.')
                        except Exception:
                            logger.exception('DF-e: falha ao tratar certificado binário da filial.')
                except Exception:
                    pass
            if not caminho_pfx or not os.path.isfile(caminho_pfx):
                msg = 'Certificado A1 (pfx) não encontrado. Verifique se há certificado binário cadastrado na Filial ou informe o caminho válido.'
                try:
                    if 'invalid_token' in locals() and invalid_token:
                        msg = 'Certificado A1 criptografado com chave diferente. Reenvie o certificado na Filial para recriptografar com a chave atual.'
                    elif 'pkcs12_invalid' in locals() and pkcs12_invalid:
                        msg = 'Certificado binário inválido ou senha incorreta.'
                except Exception:
                    pass
                return Response({'error': msg}, status=400)
            if not senha_pfx:
                return Response({'error': 'Senha do certificado A1 é obrigatória.'}, status=400)
            else:
                logger.info('DF-e: senha do certificado obtida para a filial.')
        except Exception:
            return Response({'error': 'Erro ao validar certificado A1.'}, status=400)

        xmls, novo_ultimo_nsu = NotasDestinadasService.consultar_notas_destinadas(
            uf=uf,
            cnpj=cnpj,
            ultimo_nsu=ultimo_nsu,
            caminho_pfx=caminho_pfx,
            senha_pfx=senha_pfx,
            ambiente=ambiente,
        )

        notas_criadas = []
        for xml in xmls:
            entrada = EntradaNFeService.registrar_entrada(
                xml=xml,
                empresa=empresa,
                filial=filial,
                cliente=cliente,
                gerar_estoque=gerar_estoque,
                gerar_contas_pagar=gerar_contas_pagar,
                banco=banco,
                usuario_id=getattr(request.user, 'usua_codi', 0),
            )
            notas_criadas.append(entrada)

            if manifestar_ciencia:
                try:
                    ManifestacaoService.manifestar_ciencia(
                        nota_entrada=entrada,
                        uf=uf,
                        cnpj_destinatario=cnpj,
                        caminho_pfx=caminho_pfx,
                        senha_pfx=senha_pfx,
                        ambiente=ambiente,
                    )
                except Exception:
                    logger.exception('Erro ao manifestar ciência')

        try:
            if novo_ultimo_nsu:
                f = Filiais.objects.using(banco).filter(empr_empr=int(filial), empr_codi=int(empresa)).first()
                if f:
                    f.empr_nsu = str(novo_ultimo_nsu)
                    f.save(using=banco)
        except Exception:
            pass

        resp = {
            'mensagem': 'Importação concluída',
            'quantidade_xmls': len(xmls),
            'novo_ultimo_nsu': novo_ultimo_nsu,
            'notas_criadas': NotaFiscalEntradaSerializer(notas_criadas, many=True, context={'banco': banco}).data,
        }
        return Response(resp, status=status.HTTP_201_CREATED)


class ConsultarNfseDistribuicaoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from .serializers import ConsultarNfseDistribuicaoSerializer
        from .services.notas_destinadas_service import NfseDfeAdnService
        from Licencas.crypto import decrypt_bytes, decrypt_str
        import os
        import tempfile

        banco = get_licenca_db_config(request)

        serializer = ConsultarNfseDistribuicaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ultimo_nsu = (data.get("ultimo_nsu") or "0").strip() or "0"
        caminho_pfx = (data.get("caminho_pfx") or "").strip()
        senha_pfx = (data.get("senha_pfx") or "").strip()
        max_paginas = data.get("max_paginas")

        empresa = (
            request.headers.get("X-Empresa")
            or request.session.get("empresa_id")
            or data.get("empresa")
        )
        filial = (
            request.headers.get("X-Filial")
            or request.session.get("filial_id")
            or data.get("filial")
        )

        if not empresa or not filial:
            return Response({"error": "empresa e filial são obrigatórios"}, status=400)

        f = Filiais.objects.using(banco).filter(empr_empr=int(filial), empr_codi=int(empresa)).first()
        if not f:
            return Response({"error": "Filial não encontrada"}, status=404)

        senha_cert = ""
        senha_cert_nfs = ""
        try:
            if getattr(f, "empr_senh_cert", None):
                senha_cert = decrypt_str(f.empr_senh_cert) or ""
        except Exception:
            senha_cert = (getattr(f, "empr_senh_cert", "") or "").strip()

        try:
            if getattr(f, "empr_senh_cert_nfs", None):
                senha_cert_nfs = decrypt_str(f.empr_senh_cert_nfs) or ""
        except Exception:
            senha_cert_nfs = (getattr(f, "empr_senh_cert_nfs", "") or "").strip()

        if not senha_pfx:
            senha_pfx = (senha_cert_nfs or senha_cert or "").strip()

        if not caminho_pfx:
            caminho_pfx = (f.empr_cert_nfs or f.empr_cert or "").strip()

        tmp_pfx_path = None
        try:
            if getattr(f, "empr_cert_digi", None):
                try:
                    raw = f.empr_cert_digi
                    if isinstance(raw, memoryview):
                        raw = raw.tobytes()
                    elif isinstance(raw, bytearray):
                        raw = bytes(raw)
                    data_bytes = decrypt_bytes(raw)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pfx")
                    tmp.write(data_bytes)
                    tmp.flush()
                    tmp.close()
                    tmp_pfx_path = tmp.name
                    caminho_pfx = tmp_pfx_path
                    if senha_cert:
                        senha_pfx = (senha_cert or "").strip()
                except Exception:
                    pass

            if not caminho_pfx or not os.path.isfile(caminho_pfx):
                return Response({"error": "Certificado A1 (pfx) não encontrado"}, status=400)
            if not senha_pfx:
                return Response({"error": "Senha do certificado A1 é obrigatória"}, status=400)

            documentos, ult_nsu, max_nsu, paginas = NfseDfeAdnService.sincronizar(
                ultimo_nsu=ultimo_nsu,
                caminho_pfx=caminho_pfx,
                senha_pfx=senha_pfx,
                max_paginas=max_paginas,
            )
        except Exception as e:
            logger.exception(f"Erro ao consultar NFS-e DF-e (ADN): {e}")
            return Response({"error": "Falha ao consultar NFS-e DF-e (ADN)."}, status=400)
        finally:
            try:
                if tmp_pfx_path and os.path.exists(tmp_pfx_path):
                    os.remove(tmp_pfx_path)
            except Exception:
                pass

        parcial = bool(ult_nsu and max_nsu and ult_nsu != max_nsu)
        resp = {
            "ultimo_nsu_informado": ultimo_nsu,
            "novo_ultimo_nsu": ult_nsu,
            "max_nsu": max_nsu,
            "paginas": paginas,
            "parcial": parcial,
            "quantidade_documentos": len(documentos),
            "documentos": documentos,
        }
        return Response(resp, status=200)


class ImportarNfseTomadasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from .serializers import ImportarNfseTomadasSerializer
        from .services.notas_destinadas_service import NfseDfeAdnService, NfseTomadasService
        from Licencas.crypto import decrypt_bytes, decrypt_str
        import os
        import tempfile

        banco = get_licenca_db_config(request)

        serializer = ImportarNfseTomadasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ultimo_nsu = (data.get("ultimo_nsu") or "0").strip() or "0"
        caminho_pfx = (data.get("caminho_pfx") or "").strip()
        senha_pfx = (data.get("senha_pfx") or "").strip()
        max_paginas = data.get("max_paginas")

        empresa = (
            request.headers.get("X-Empresa")
            or request.session.get("empresa_id")
            or data.get("empresa")
        )
        filial = (
            request.headers.get("X-Filial")
            or request.session.get("filial_id")
            or data.get("filial")
        )

        if not empresa or not filial:
            return Response({"error": "empresa e filial são obrigatórios"}, status=400)

        f = Filiais.objects.using(banco).filter(empr_empr=int(filial), empr_codi=int(empresa)).first()
        if not f:
            return Response({"error": "Filial não encontrada"}, status=404)

        tomador_doc = ""
        try:
            tomador_doc = getattr(f, "empr_docu", "") or ""
        except Exception:
            tomador_doc = ""

        senha_cert = ""
        senha_cert_nfs = ""
        try:
            if getattr(f, "empr_senh_cert", None):
                senha_cert = decrypt_str(f.empr_senh_cert) or ""
        except Exception:
            senha_cert = (getattr(f, "empr_senh_cert", "") or "").strip()

        try:
            if getattr(f, "empr_senh_cert_nfs", None):
                senha_cert_nfs = decrypt_str(f.empr_senh_cert_nfs) or ""
        except Exception:
            senha_cert_nfs = (getattr(f, "empr_senh_cert_nfs", "") or "").strip()

        if not senha_pfx:
            senha_pfx = (senha_cert_nfs or senha_cert or "").strip()

        if not caminho_pfx:
            caminho_pfx = (f.empr_cert_nfs or f.empr_cert or "").strip()

        tmp_pfx_path = None
        try:
            if getattr(f, "empr_cert_digi", None):
                try:
                    raw = f.empr_cert_digi
                    if isinstance(raw, memoryview):
                        raw = raw.tobytes()
                    elif isinstance(raw, bytearray):
                        raw = bytes(raw)
                    data_bytes = decrypt_bytes(raw)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pfx")
                    tmp.write(data_bytes)
                    tmp.flush()
                    tmp.close()
                    tmp_pfx_path = tmp.name
                    caminho_pfx = tmp_pfx_path
                    if senha_cert:
                        senha_pfx = (senha_cert or "").strip()
                except Exception:
                    pass

            if not caminho_pfx or not os.path.isfile(caminho_pfx):
                return Response({"error": "Certificado A1 (pfx) não encontrado"}, status=400)
            if not senha_pfx:
                return Response({"error": "Senha do certificado A1 é obrigatória"}, status=400)

            documentos, ult_nsu, max_nsu, paginas = NfseDfeAdnService.sincronizar(
                ultimo_nsu=ultimo_nsu,
                caminho_pfx=caminho_pfx,
                senha_pfx=senha_pfx,
                max_paginas=max_paginas,
            )

            import_result = NfseTomadasService.importar_tomadas(
                banco=banco,
                empresa=int(empresa),
                filial=int(filial),
                documentos=documentos,
                tomador_doc=tomador_doc,
            )
        except Exception as e:
            logger.exception(f"Erro ao importar NFS-e tomadas (ADN): {e}")
            return Response({"error": "Falha ao importar NFS-e tomadas."}, status=400)
        finally:
            try:
                if tmp_pfx_path and os.path.exists(tmp_pfx_path):
                    os.remove(tmp_pfx_path)
            except Exception:
                pass

        parcial = bool(ult_nsu and max_nsu and ult_nsu != max_nsu)
        resp = {
            "mensagem": "Importação concluída",
            "ultimo_nsu_informado": ultimo_nsu,
            "novo_ultimo_nsu": ult_nsu,
            "max_nsu": max_nsu,
            "paginas": paginas,
            "parcial": parcial,
            "quantidade_documentos": len(documentos),
            "criadas": import_result.get("criadas", 0),
            "atualizadas": import_result.get("atualizadas", 0),
            "nfse_ids": import_result.get("ids", []),
        }
        return Response(resp, status=200)


class GerarContasPagarNfseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, nfse_id=None, *args, **kwargs):
        from .serializers import GerarContasPagarNfseSerializer
        from .services.notas_destinadas_service import NfseTomadasService

        banco = get_licenca_db_config(request)

        serializer = GerarContasPagarNfseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        empresa = request.headers.get("X-Empresa") or request.session.get("empresa_id")
        filial = request.headers.get("X-Filial") or request.session.get("filial_id")
        if not empresa or not filial:
            return Response({"error": "empresa e filial são obrigatórios"}, status=400)

        try:
            result = NfseTomadasService.gerar_contas_pagar(
                banco=banco,
                nfse_id=int(nfse_id),
                empresa=int(empresa),
                filial=int(filial),
                usuario_id=getattr(request.user, "usua_codi", 0),
                data_base=data.get("data_base"),
                parcelas=data.get("parcelas"),
                intervalo_dias=data.get("intervalo_dias"),
            )
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({"mensagem": "Contas a pagar geradas", **result}, status=200)


class ReferenciarNfseTomadaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, nfse_id=None, *args, **kwargs):
        from .services.notas_destinadas_service import NfseTomadasService

        banco = get_licenca_db_config(request)
        empresa = request.headers.get("X-Empresa") or request.session.get("empresa_id")
        filial = request.headers.get("X-Filial") or request.session.get("filial_id")
        if not empresa or not filial:
            return Response({"error": "empresa e filial são obrigatórios"}, status=400)

        try:
            result = NfseTomadasService.marcar_referenciada(
                banco=banco,
                empresa=int(empresa),
                filial=int(filial),
                nfse_id=int(nfse_id),
            )
            return Response({"mensagem": "NFS-e referenciada", **result}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


class ManifestarCienciaNfseTomadaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, nfse_id=None, *args, **kwargs):
        from .services.notas_destinadas_service import NfseTomadasService

        banco = get_licenca_db_config(request)
        empresa = request.headers.get("X-Empresa") or request.session.get("empresa_id")
        filial = request.headers.get("X-Filial") or request.session.get("filial_id")
        if not empresa or not filial:
            return Response({"error": "empresa e filial são obrigatórios"}, status=400)

        try:
            result = NfseTomadasService.manifestar_ciencia(
                banco=banco,
                empresa=int(empresa),
                filial=int(filial),
                nfse_id=int(nfse_id),
            )
            return Response({"mensagem": "Ciência registrada", **result}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
