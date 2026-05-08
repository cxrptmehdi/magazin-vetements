from django import forms
from .models import Produit, Stock, Fournisseur


class ProduitForm(forms.ModelForm):
    class Meta:
        model  = Produit
        fields = ['nom', 'prix', 'taille', 'date_achat',
                  'categorie', 'fournisseur', 'description', 'image']
        widgets = {
            'nom':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du produit'}),
            'prix':       forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'taille':     forms.Select(attrs={'class': 'form-select'}),
            'date_achat': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'categorie':  forms.Select(attrs={'class': 'form-select'}),
            'fournisseur':forms.Select(attrs={'class': 'form-select'}),
            'description':forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image':      forms.FileInput(attrs={'class': 'form-control'}),
        }


class StockForm(forms.ModelForm):
    class Meta:
        model  = Stock
        fields = ['quantite']
        widgets = {
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ['nom_societe', 'contact', 'adresse']
        widgets = {
            'nom_societe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du fournisseur'}),
            'contact':     forms.TextInput(attrs={'class': 'form-control'}),
            'adresse':     forms.TextInput(attrs={'class': 'form-control'}),
        }