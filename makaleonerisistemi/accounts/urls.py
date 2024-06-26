from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home, name='home'),
    path('register', views.userRegister, name='register'),
    path('login', views.userLogin, name='login'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('logout', views.userLogout, name='logout'),
    path('updatefullname', views.updatefullname, name='updatefullname'),
    path('updateInterestAreas', views.updateInterestAreas, name='updateInterestAreas'),
    path('updateInterestAreasForm', views.updateInterestAreasForm, name='updateInterestAreasForm'),
    path('articleDetail/<str:id>', views.articleDetail, name='articleDetail'),
    path('search/', views.search, name='search'),
    path('removeArticle/<str:kullanici_mail>/<str:makale_id>', views.removeArticle, name='removeArticle'),

]