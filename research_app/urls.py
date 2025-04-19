from django.urls import path
from . import views

app_name = 'research_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('start_research/', views.start_research_session, name='start_research'),
    path('session_status/<uuid:session_id>/', views.get_session_status, name='session_status'),
    path('download_report/<uuid:session_id>/', views.download_report, name='download_report'),
]
