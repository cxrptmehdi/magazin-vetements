from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.liste_produits, name='produits'),
    path('categories/', views.liste_categories, name='categories'),
    path('panier/', views.voir_panier, name='panier'),
    path('panier/ajouter/<int:produit_id>/', views.ajouter_au_panier, name='ajouter_panier'),
    path('panier/retirer/<int:item_id>/', views.retirer_du_panier, name='retirer_panier'),
    path('panier/modifier/<int:item_id>/', views.modifier_quantite, name='modifier_quantite'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    #commande
    path('checkout/',     views.passer_commande, name='checkout'),
    path('commandes/',    views.mes_commandes,   name='mes_commandes'),

    #crud
    path('produits/ajouter/',                views.ajouter_produit,   name='ajouter_produit'),
    path('produits/modifier/<int:produit_id>/', views.modifier_produit, name='modifier_produit'),
    path('produits/supprimer/<int:produit_id>/', views.supprimer_produit, name='supprimer_produit'),
    path('stock/',                           views.gerer_stock,        name='stock'),
    path('stock/modifier/<int:produit_id>/', views.modifier_stock,     name='modifier_stock'),
]