from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('VENDEUR', 'Vendeur'),
        ('CLIENT', 'Client'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.role}"



class Categorie(models.Model):
    nom_categorie = models.CharField(max_length=100)

    def __str__(self):
        return self.nom_categorie



class Fournisseur(models.Model):
    nom_societe = models.CharField(max_length=150)
    contact = models.CharField(max_length=150)
    adresse = models.TextField()

    def __str__(self):
        return self.nom_societe



class Produit(models.Model):
    TAILLES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
    ]

    nom = models.CharField(max_length=150)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    taille = models.CharField(max_length=2, choices=TAILLES)
    date_achat = models.DateField()

    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE)
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.CASCADE)

    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='produits/', null=True, blank=True)

    def __str__(self):
        return self.nom


class Stock(models.Model):
    produit = models.OneToOneField(Produit, on_delete=models.CASCADE)
    quantite = models.IntegerField()

    def __str__(self):
        return f"{self.produit.nom} - {self.quantite}"
    

class Panier(models.Model):
    client = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Panier de {self.client.username}"

    def total(self):
        return sum(item.sous_total() for item in self.items.all())


class PanierItem(models.Model):
    panier = models.ForeignKey(Panier, on_delete=models.CASCADE, related_name='items')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantite = models.IntegerField(default=1)

    def sous_total(self):
        return self.produit.prix * self.quantite

    def __str__(self):
        return f"{self.quantite}x {self.produit.nom}"
    
class Commande(models.Model):
    STATUS_CHOICES = [
        ('EN_ATTENTE',  'En attente'),
        ('CONFIRMEE',   'Confirmée'),
        ('EXPEDIEE',    'Expédiée'),
        ('LIVREE',      'Livrée'),
        ('ANNULEE',     'Annulée'),
    ]

    client      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commandes')
    statut      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='EN_ATTENTE')
    created_at  = models.DateTimeField(auto_now_add=True)
    adresse     = models.TextField()
    total       = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Commande #{self.id} — {self.client.username}"


class CommandeItem(models.Model):
    commande    = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name='items')
    produit     = models.ForeignKey(Produit, on_delete=models.SET_NULL, null=True)
    quantite    = models.IntegerField()
    prix_unite  = models.DecimalField(max_digits=10, decimal_places=2)

    def sous_total(self):
        return self.prix_unite * self.quantite

    def __str__(self):
        return f"{self.quantite}x {self.produit.nom}"