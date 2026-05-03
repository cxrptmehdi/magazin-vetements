from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from .models import Produit, Categorie, Panier, PanierItem, Profile, Stock, Commande, CommandeItem
from .decorators import role_required

def liste_produits(request):
    produits = Produit.objects.select_related('categorie', 'fournisseur').all()
    categories = Categorie.objects.all()
    categorie_id = request.GET.get('categorie')
    search = request.GET.get('q')
    fournisseur_id = request.GET.get('fournisseur')
    if fournisseur_id:
        produits = produits.filter(fournisseur__id=fournisseur_id)
    if search:
        produits = produits.filter(nom__icontains=search)
    if categorie_id:
        produits = produits.filter(categorie__id=categorie_id)
        
    return render(request, 'magazin/liste_produits.html', {
        'produits': produits,
        'categories': categories,
        'categorie_active': int(categorie_id) if categorie_id else None,
    })
    


def liste_categories(request):
    categories = Categorie.objects.all()
    return render(request, 'magazin/categories.html', {
        'categories': categories,
    })


@login_required
def voir_panier(request):
    panier, _ = Panier.objects.get_or_create(client=request.user)
    return render(request, 'magazin/panier.html', {'panier': panier})


@login_required
def ajouter_au_panier(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id)

    # Check stock exists and has quantity
    try:
        stock = produit.stock
    except Stock.DoesNotExist:
        messages.error(request, f'"{produit.nom}" est en rupture de stock.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    panier, _ = Panier.objects.get_or_create(client=request.user)
    item, created = PanierItem.objects.get_or_create(panier=panier, produit=produit)

    # Check requested quantity doesn't exceed stock
    quantite_dans_panier = item.quantite if not created else 0
    if quantite_dans_panier >= stock.quantite:
        messages.warning(request, f'Stock insuffisant pour "{produit.nom}" (max {stock.quantite}).')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    if not created:
        item.quantite += 1
        item.save()

    messages.success(request, f'"{produit.nom}" ajouté au panier.')
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def retirer_du_panier(request, item_id):
    item = get_object_or_404(PanierItem, id=item_id, panier__client=request.user)
    item.delete()
    messages.success(request, 'Article retiré du panier.')
    return redirect('panier')


@login_required
def modifier_quantite(request, item_id):
    item = get_object_or_404(PanierItem, id=item_id, panier__client=request.user)
    quantite = int(request.POST.get('quantite', 1))

    if quantite < 1:
        item.delete()
    else:
        try:
            stock = item.produit.stock
            if quantite > stock.quantite:
                messages.warning(request, f'Stock insuffisant (max {stock.quantite}).')
                quantite = stock.quantite
        except Stock.DoesNotExist:
            messages.error(request, 'Ce produit n\'est plus disponible.')
            item.delete()
            return redirect('panier')

        item.quantite = quantite
        item.save()

    return redirect('panier')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('produits')
    form = AuthenticationForm(data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f'Bienvenue, {user.username} !')
        return redirect(request.GET.get('next', 'produits'))
    return render(request, 'magazin/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Vous êtes déconnecté.')
    return redirect('produits')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('produits')
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Profile.objects.create(user=user, role='CLIENT')
        login(request, user)
        messages.success(request, f'Compte créé ! Bienvenue, {user.username} !')
        return redirect('produits')
    return render(request, 'magazin/register.html', {'form': form})

@login_required
def passer_commande(request):
    panier, _ = Panier.objects.get_or_create(client=request.user)

    if not panier.items.exists():
        messages.error(request, 'Votre panier est vide.')
        return redirect('panier')

    if request.method == 'POST':
        adresse = request.POST.get('adresse', '').strip()
        if not adresse:
            messages.error(request, 'Veuillez entrer une adresse de livraison.')
            return render(request, 'magazin/checkout.html', {'panier': panier})

        # Create the order
        commande = Commande.objects.create(
            client=request.user,
            adresse=adresse,
            total=panier.total(),
        )

        # Move items from cart to order and decrease stock
        for item in panier.items.all():
            CommandeItem.objects.create(
                commande=commande,
                produit=item.produit,
                quantite=item.quantite,
                prix_unite=item.produit.prix,
            )
            # Decrease stock
            try:
                stock = item.produit.stock
                stock.quantite -= item.quantite
                stock.save()
            except Stock.DoesNotExist:
                pass

        # Clear the cart
        panier.items.all().delete()

        messages.success(request, f'Commande #{commande.id} passée avec succès !')
        return redirect('mes_commandes')

    return render(request, 'magazin/checkout.html', {'panier': panier})


@login_required
def mes_commandes(request):
    commandes = Commande.objects.filter(client=request.user).order_by('-created_at')
    return render(request, 'magazin/commandes.html', {'commandes': commandes})

# ── Vendeur: add product ──
@login_required
@role_required('VENDEUR', 'ADMIN')
def ajouter_produit(request):
    from .forms import ProduitForm
    form = ProduitForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Produit ajouté avec succès.')
        return redirect('produits')
    return render(request, 'magazin/produit_form.html', {
        'form': form,
        'titre': 'Ajouter un produit',
    })


# ── Vendeur: edit product ──
@login_required
@role_required('VENDEUR', 'ADMIN')
def modifier_produit(request, produit_id):
    from .forms import ProduitForm
    produit = get_object_or_404(Produit, id=produit_id)
    form = ProduitForm(request.POST or None, request.FILES or None, instance=produit)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Produit modifié avec succès.')
        return redirect('produits')
    return render(request, 'magazin/produit_form.html', {
        'form': form,
        'titre': 'Modifier le produit',
        'produit': produit,
    })


# ── Vendeur: delete product ──
@login_required
@role_required('VENDEUR', 'ADMIN')
def supprimer_produit(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id)
    if request.method == 'POST':
        produit.delete()
        messages.success(request, 'Produit supprimé.')
        return redirect('produits')
    return render(request, 'magazin/produit_confirm_delete.html', {'produit': produit})


# ── Vendeur: manage stock ──
@login_required
@role_required('VENDEUR', 'ADMIN')
def gerer_stock(request):
    from .forms import StockForm
    produits = Produit.objects.select_related('stock').all()
    return render(request, 'magazin/stock.html', {'produits': produits})


@login_required
@role_required('VENDEUR', 'ADMIN')
def modifier_stock(request, produit_id):
    from .forms import StockForm
    produit = get_object_or_404(Produit, id=produit_id)
    stock, _ = Stock.objects.get_or_create(produit=produit)
    form = StockForm(request.POST or None, instance=stock)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Stock de "{produit.nom}" mis à jour.')
        return redirect('stock')
    return render(request, 'magazin/stock_form.html', {
        'form': form,
        'produit': produit,
    })