from django.contrib import admin
from .models import Produit, Categorie, Fournisseur, Stock, Profile, Panier, PanierItem, Commande, CommandeItem


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'role')
    list_filter   = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display  = ('nom_categorie',)
    search_fields = ('nom_categorie',)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display  = ('nom_societe', 'contact', 'adresse')
    search_fields = ('nom_societe', 'contact')


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display  = ('produit', 'quantite')
    list_filter   = ('quantite',)
    search_fields = ('produit__nom',)


class StockInline(admin.StackedInline):
    model  = Stock
    extra  = 1


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display    = ('nom', 'categorie', 'fournisseur', 'prix', 'taille', 'date_achat')
    list_filter     = ('categorie', 'taille', 'fournisseur')
    search_fields   = ('nom', 'description')
    list_editable   = ('prix', 'taille')
    date_hierarchy  = 'date_achat'
    inlines         = [StockInline]
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'description', 'image')
        }),
        ('Prix & Taille', {
            'fields': ('prix', 'taille')
        }),
        ('Relations', {
            'fields': ('categorie', 'fournisseur')
        }),
        ('Date', {
            'fields': ('date_achat',)
        }),
    )


class PanierItemInline(admin.TabularInline):
    model  = PanierItem
    extra  = 0
    readonly_fields = ('sous_total',)


@admin.register(Panier)
class PanierAdmin(admin.ModelAdmin):
    list_display  = ('client', 'created_at', 'total')
    search_fields = ('client__username',)
    readonly_fields = ('created_at', 'total')
    inlines       = [PanierItemInline]


@admin.register(PanierItem)
class PanierItemAdmin(admin.ModelAdmin):
    list_display  = ('panier', 'produit', 'quantite', 'sous_total')
    search_fields = ('produit__nom', 'panier__client__username')

@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display  = ('id', 'client', 'statut', 'total', 'created_at')
    list_filter   = ('statut',)
    search_fields = ('client__username',)
    list_editable = ('statut',)

@admin.register(CommandeItem)
class CommandeItemAdmin(admin.ModelAdmin):
    list_display  = ('commande', 'produit', 'quantite', 'prix_unite')