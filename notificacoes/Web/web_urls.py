from django.urls import path
from .web_views import (
    NotificacoesDashboardView,
    TitulosCriadosHojeListView,
    TitulosAPagarListView,
    TitulosAReceberListView,
    OrcamentosHojeListView,
    PedidosHojeListView,
    ExportarTitulosCriadosHojeView,
    ExportarTitulosAPagarListView,
    ExportarTitulosAReceberListView,
    ExportarOrcamentosHojeListView,
    ExportarPedidosHojeListView,
    NotificacoesPorEmpresaFilialView,
    ImprimirPagarView,
    ImprimirReceberView,
    ImprimirOrcamentosView,
    ImprimirPedidosView,
    ImprimirTitulosView,
)

app_name = 'notificacoes_web'

urlpatterns = [
    path('', NotificacoesDashboardView.as_view(), name='dashboard'),
    path('titulos-criados-hoje/', TitulosCriadosHojeListView.as_view(), name='titulos_criados_hoje'),
    path('titulos-criados-hoje/exportar/', ExportarTitulosCriadosHojeView.as_view(), name='exportar_titulos_criados_hoje'),
    path('titulos-criados-hoje/imprimir/', ImprimirTitulosView.as_view(), name='imprimir_titulos_criados_hoje'),
    path('pagar/', TitulosAPagarListView.as_view(), name='pagar'),
    path('pagar/exportar/', ExportarTitulosAPagarListView.as_view(), name='exportar_pagar'),
    path('pagar/imprimir/', ImprimirPagarView.as_view(), name='imprimir_pagar'),
    path('receber/', TitulosAReceberListView.as_view(), name='receber'),
    path('receber/exportar/', ExportarTitulosAReceberListView.as_view(), name='exportar_receber'),
    path('receber/imprimir/', ImprimirReceberView.as_view(), name='imprimir_receber'),
    path('orcamentos/', OrcamentosHojeListView.as_view(), name='orcamentos_hoje'),
    path('orcamentos/exportar/', ExportarOrcamentosHojeListView.as_view(), name='exportar_orcamentos_hoje'),
    path('orcamentos/imprimir/', ImprimirOrcamentosView.as_view(), name='imprimir_orcamentos_hoje'),
    path('pedidos/', PedidosHojeListView.as_view(), name='pedidos_hoje'),
    path('pedidos/exportar/', ExportarPedidosHojeListView.as_view(), name='exportar_pedidos_hoje'),
    path('pedidos/imprimir/', ImprimirPedidosView.as_view(), name='imprimir_pedidos_hoje'),
    path('resumo-empresas-filiais/', NotificacoesPorEmpresaFilialView.as_view(), name='resumo_empresas_filiais'),
]

