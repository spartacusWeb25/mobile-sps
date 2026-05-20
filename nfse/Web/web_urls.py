from django.urls import path
from nfse.Web.Views.criar import NfseCreateView
from nfse.Web.Views.list import NfseListView
from nfse.Web.Views.deletar import NfseDeleteView
from nfse.Web.Views.editar import NfseEditView
from nfse.Web.Views.consultar import NfseConsultarView
from nfse.Web.Views.cancelar import NfseCancelarView



app_name = 'nfse_web'

urlpatterns = [
    path('nfse/', NfseListView.as_view(), name='list'),
    path('nfse/novo/', NfseCreateView.as_view(), name='criar'),
    path('nfse/<int:pk>/editar/', NfseEditView.as_view(), name='editar'),
    path('nfse/<int:pk>/deletar/', NfseDeleteView.as_view(), name='deletar'),
    path('nfse/<int:pk>/consultar/', NfseConsultarView.as_view(), name='consultar'),
    path('nfse/<int:pk>/cancelar/', NfseCancelarView.as_view(), name='cancelar'),
]
