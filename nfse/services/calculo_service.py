from decimal import Decimal, ROUND_HALF_UP


class CalculoNfseService:
    @staticmethod
    def aplicar(data: dict, context=None) -> dict:
        payload = dict(data or {})

        # Apply taxation from service registration if servico_id is provided
        servico_id = payload.get('servico_id')
        if servico_id and context:
            try:
                from Produtos.models import Produtos
                servico = Produtos.objects.using(context.db_alias).filter(
                    prod_codi=servico_id,
                    prod_e_serv=True,
                    prod_empr=str(context.empresa_id)
                ).first()
                
                if servico:
                    # Apply service taxation if not already set
                    if not payload.get('aliquota_iss') and servico.prod_iss:
                        payload['aliquota_iss'] = Decimal(str(servico.prod_iss))
                    
                    if not payload.get('cnae_codigo') and servico.prod_cnae:
                        payload['cnae_codigo'] = servico.prod_cnae
                    
                    if not payload.get('servico_codigo') and servico.prod_codi_serv:
                        payload['servico_codigo'] = servico.prod_codi_serv
                    
                    if not payload.get('servico_descricao') and servico.prod_desc_serv:
                        payload['servico_descricao'] = servico.prod_desc_serv
                    
                    # Set ISS exigibility
                    if servico.prod_exig_iss:
                        # 1=Exigível, 2=Não Exigível, 3=Isenção, 4=Exportação
                        payload['iss_retido'] = servico.prod_exig_iss == 1
            except Exception:
                # If service lookup fails, continue with provided data
                pass

        # Apply tomador data from Entidades if tomador_id is provided
        tomador_id = payload.get('tomador_id')
        if tomador_id and context:
            try:
                from Entidades.models import Entidades
                tomador = Entidades.objects.using(context.db_alias).filter(
                    enti_clie=tomador_id,
                    enti_empr=str(context.empresa_id)
                ).first()
                
                if tomador:
                    # Apply tomador data if not already set
                    if not payload.get('tomador_documento'):
                        payload['tomador_documento'] = tomador.enti_cnpj or tomador.enti_cpf or ''
                    
                    if not payload.get('tomador_nome'):
                        payload['tomador_nome'] = tomador.enti_nome or ''
                    
                    if not payload.get('tomador_email'):
                        payload['tomador_email'] = tomador.enti_email or ''
                    
                    if not payload.get('tomador_telefone'):
                        payload['tomador_telefone'] = tomador.enti_fone or ''
                    
                    if not payload.get('tomador_endereco'):
                        payload['tomador_endereco'] = tomador.enti_ende or ''
                    
                    if not payload.get('tomador_numero'):
                        payload['tomador_numero'] = tomador.enti_nume or ''
                    
                    if not payload.get('tomador_bairro'):
                        payload['tomador_bairro'] = tomador.enti_bair or ''
                    
                    if not payload.get('tomador_cep'):
                        payload['tomador_cep'] = tomador.enti_cepe or ''
                    
                    if not payload.get('tomador_cidade'):
                        payload['tomador_cidade'] = tomador.enti_cida or ''
                    
                    if not payload.get('tomador_uf'):
                        payload['tomador_uf'] = tomador.enti_esta or ''
                    
                    if not payload.get('tomador_ie'):
                        payload['tomador_ie'] = tomador.enti_ie or ''
                    
                    if not payload.get('tomador_im'):
                        payload['tomador_im'] = tomador.enti_im or ''
            except Exception:
                # If tomador lookup fails, continue with provided data
                pass

        itens = payload.get('itens') or []
        if itens and not payload.get('valor_servico'):
            total_itens = sum(Decimal(str(i.get('valor_total') or 0)) for i in itens)
            payload['valor_servico'] = total_itens

        valor_servico = Decimal(str(payload.get('valor_servico') or 0))
        valor_deducao = Decimal(str(payload.get('valor_deducao') or 0))
        valor_desconto = Decimal(str(payload.get('valor_desconto') or 0))
        valor_iss = Decimal(str(payload.get('valor_iss') or 0))
        aliquota_iss = Decimal(str(payload.get('aliquota_iss') or 0))
        base_iss = max(valor_servico - valor_deducao, Decimal('0.00'))

        if valor_iss <= 0 and aliquota_iss > 0 and base_iss > 0:
            valor_iss = (base_iss * (aliquota_iss / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            payload['valor_iss'] = valor_iss

        if aliquota_iss <= 0 and valor_iss > 0 and base_iss > 0:
            aliquota_iss = ((valor_iss / base_iss) * Decimal('100')).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            payload['aliquota_iss'] = aliquota_iss

        if not payload.get('valor_liquido'):
            payload['valor_liquido'] = (
                valor_servico
                - valor_deducao
                - valor_desconto
                - Decimal(str(payload.get('valor_iss') or 0))
                - Decimal(str(payload.get('valor_inss') or 0))
                - Decimal(str(payload.get('valor_irrf') or 0))
                - Decimal(str(payload.get('valor_csll') or 0))
                - Decimal(str(payload.get('valor_cofins') or 0))
                - Decimal(str(payload.get('valor_pis') or 0))
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return payload
