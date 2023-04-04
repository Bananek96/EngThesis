from django.urls import path
from . import views

app_name = 'home'
urlpatterns = [
    path('', views.index_pl, name='index_pl'),
    path('en', views.index_en, name='index_en'),
]