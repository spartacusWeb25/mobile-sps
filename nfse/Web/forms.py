from decimal import Decimal

from django import forms
from django.forms import formset_factory


class NfseForm(forms.Form):
    municipio_codigo = forms.CharField(
        label='Código Município',
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    rps_numero = forms.CharField(
        label='Número RPS',
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    rps_serie = forms.CharField(
        label='Série RPS',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    prestador_documento = forms.CharField(
        label='Documento Prestador',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    prestador_nome = forms.CharField(
        label='Nome Prestador',
        max_length=120,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    tomador_documento = forms.CharField(
        label='Documento Tomador',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_nome = forms.CharField(
        label='Nome Tomador',
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_email = forms.EmailField(
        label='Email Tomador',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    tomador_telefone = forms.CharField(
        label='Telefone Tomador',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_endereco = forms.CharField(
        label='Endereço Tomador',
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_numero = forms.CharField(
        label='Número',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_bairro = forms.CharField(
        label='Bairro',
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_cep = forms.CharField(
        label='CEP',
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_cidade = forms.CharField(
        label='Cidade',
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_uf = forms.CharField(
        label='UF',
        max_length=2,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_ie = forms.CharField(
        label='IE',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    tomador_im = forms.CharField(
        label='IM',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    servico_codigo = forms.CharField(
        label='Código Serviço',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'servico-codigo'})
    )
    servico_descricao = forms.CharField(
        label='Descrição Serviço',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'id': 'servico-descricao'})
    )
    servico_autocomplete = forms.CharField(
        label='Serviço',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite para buscar serviço...', 'id': 'servico-autocomplete'})
    )
    prestador_ie = forms.CharField(
        label='IE (Inscrição Estadual)',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    cnae_codigo = forms.CharField(
        label='CNAE',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    lc116_codigo = forms.CharField(
        label='Código LC 116',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    natureza_operacao = forms.CharField(
        label='Natureza Operação',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    valor_servico = forms.DecimalField(
        label='Valor Serviço',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_deducao = forms.DecimalField(
        label='Valor Dedução',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_desconto = forms.DecimalField(
        label='Valor Desconto',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_inss = forms.DecimalField(
        label='Valor INSS',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_irrf = forms.DecimalField(
        label='Valor IRRF',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_csll = forms.DecimalField(
        label='Valor CSLL',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_cofins = forms.DecimalField(
        label='Valor COFINS',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_pis = forms.DecimalField(
        label='Valor PIS',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_iss = forms.DecimalField(
        label='Valor ISS',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    valor_liquido = forms.DecimalField(
        label='Valor Líquido',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    aliquota_iss = forms.DecimalField(
        label='Alíquota ISS',
        max_digits=7,
        decimal_places=4,
        required=False,
        initial=Decimal('0.0000'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'})
    )

    iss_retido = forms.BooleanField(
        label='ISS Retido',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()

        valor_servico = cleaned_data.get('valor_servico') or Decimal('0.00')
        valor_iss = cleaned_data.get('valor_iss') or Decimal('0.00')
        valor_liquido = cleaned_data.get('valor_liquido')

        if not valor_liquido:
            cleaned_data['valor_liquido'] = (
                valor_servico
                - (cleaned_data.get('valor_deducao') or Decimal('0.00'))
                - (cleaned_data.get('valor_desconto') or Decimal('0.00'))
                - valor_iss
                - (cleaned_data.get('valor_inss') or Decimal('0.00'))
                - (cleaned_data.get('valor_irrf') or Decimal('0.00'))
                - (cleaned_data.get('valor_csll') or Decimal('0.00'))
                - (cleaned_data.get('valor_cofins') or Decimal('0.00'))
                - (cleaned_data.get('valor_pis') or Decimal('0.00'))
            )

        return cleaned_data



class NfseItemForm(forms.Form):
    descricao = forms.CharField(
        label='Descrição Item',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )
    quantidade = forms.DecimalField(
        label='Quantidade',
        max_digits=15,
        decimal_places=4,
        initial=Decimal('1.0000'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'})
    )
    valor_unitario = forms.DecimalField(
        label='Valor Unitário',
        max_digits=15,
        decimal_places=6,
        initial=Decimal('0.000000'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'})
    )
    valor_total = forms.DecimalField(
        label='Valor Total',
        max_digits=15,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    servico_codigo = forms.CharField(
        label='Código Serviço',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    cnae_codigo = forms.CharField(
        label='CNAE',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    lc116_codigo = forms.CharField(
        label='LC 116',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()

        quantidade = cleaned_data.get('quantidade') or Decimal('0')
        valor_unitario = cleaned_data.get('valor_unitario') or Decimal('0')
        valor_total = cleaned_data.get('valor_total')

        if not valor_total:
            cleaned_data['valor_total'] = quantidade * valor_unitario

        return cleaned_data


NfseItemFormSet = formset_factory(
    NfseItemForm,
    extra=1,
    can_delete=True
)