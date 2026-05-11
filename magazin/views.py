from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from .models import Produit, Categorie, Panier, PanierItem, Profile, Stock, Commande, CommandeItem, Fournisseur
from .decorators import role_required


# ── Public views ──────────────────────────────────────────────────────────────

def liste_produits(request):
    """Display all products with optional filtering by category, supplier, size, or search query."""
    produits = Produit.objects.select_related('categorie', 'fournisseur').all()
    categories = Categorie.objects.all()
    fournisseurs = Fournisseur.objects.all()
    tailles = Produit.TAILLES

    # Read filter params from the query string
    categorie_id = request.GET.get('categorie')
    search = request.GET.get('q')
    fournisseur_id = request.GET.get('fournisseur')
    taille = request.GET.get('taille')

    # Apply each active filter
    if fournisseur_id:
        produits = produits.filter(fournisseur__id=fournisseur_id)
    if taille:
        produits = produits.filter(taille=taille)
    if search:
        produits = produits.filter(nom__icontains=search)
    if categorie_id:
        produits = produits.filter(categorie__id=categorie_id)

    return render(request, 'magazin/liste_produits.html', {
        'produits': produits,
        'categories': categories,
        'fournisseurs': fournisseurs,
        'tailles': tailles,
        # Pass back active filter values so the template can highlight them
        'fournisseur_actif': int(fournisseur_id) if fournisseur_id else None,
        'taille_active': taille or '',
        'categorie_active': int(categorie_id) if categorie_id else None,
    })


def liste_categories(request):
    """Simple view that lists all product categories."""
    categories = Categorie.objects.all()
    return render(request, 'magazin/categories.html', {'categories': categories})


# ── Cart ──────────────────────────────────────────────────────────────────────

@login_required
def voir_panier(request):
    """Show the current user's cart, creating it if it doesn't exist yet."""
    panier, _ = Panier.objects.get_or_create(client=request.user)
    return render(request, 'magazin/panier.html', {'panier': panier})


@login_required
def ajouter_au_panier(request, produit_id):
    """Add one unit of a product to the cart, respecting stock limits."""
    produit = get_object_or_404(Produit, id=produit_id)

    # Abort early if the product has no stock record at all
    try:
        stock = produit.stock
    except Stock.DoesNotExist:
        messages.error(request, f'"{produit.nom}" est en rupture de stock.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    panier, _ = Panier.objects.get_or_create(client=request.user)
    item = PanierItem.objects.filter(panier=panier, produit=produit).first()
    quantite_dans_panier = item.quantite if item else 0

    # Don't allow adding more than what's physically in stock
    if stock.quantite <= 0 or quantite_dans_panier >= stock.quantite:
        messages.warning(request, f'Stock insuffisant pour "{produit.nom}" (max {stock.quantite}).')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    if item:
        item.quantite += 1
        item.save()
    else:
        PanierItem.objects.create(panier=panier, produit=produit, quantite=1)

    messages.success(request, f'"{produit.nom}" ajouté au panier.')
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def retirer_du_panier(request, item_id):
    """Remove a cart item entirely."""
    item = get_object_or_404(PanierItem, id=item_id, panier__client=request.user)
    item.delete()
    messages.success(request, 'Article retiré du panier.')
    return redirect('panier')


@login_required
def modifier_quantite(request, item_id):
    """Update the quantity of a cart item; deletes it if quantity drops below 1."""
    item = get_object_or_404(PanierItem, id=item_id, panier__client=request.user)
    try:
        quantite = int(request.POST.get('quantite', 1))
    except (TypeError, ValueError):
        messages.warning(request, 'Quantité invalide.')
        return redirect('panier')

    if quantite < 1:
        item.delete()
    else:
        try:
            stock = item.produit.stock
            # Cap quantity at available stock instead of raising an error
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


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    """Handle login. Redirects authenticated users away immediately."""
    if request.user.is_authenticated:
        return redirect('produits')
    form = AuthenticationForm(data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f'Bienvenue, {user.username} !')
        # Honor the ?next= param so users land back where they came from
        return redirect(request.GET.get('next', 'produits'))
    return render(request, 'magazin/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Vous êtes déconnecté.')
    return redirect('produits')


def register_view(request):
    """Register a new user and assign the default CLIENT role."""
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


# ── Orders ────────────────────────────────────────────────────────────────────

@login_required
def passer_commande(request):
    """
    Convert the current cart into a confirmed order.
    Uses a database transaction + select_for_update to prevent overselling
    when multiple users checkout at the same time.
    """
    panier, _ = Panier.objects.get_or_create(client=request.user)

    if not panier.items.exists():
        messages.error(request, 'Votre panier est vide.')
        return redirect('panier')

    if request.method == 'POST':
        adresse = request.POST.get('adresse', '').strip()
        if not adresse:
            messages.error(request, 'Veuillez entrer une adresse de livraison.')
            return render(request, 'magazin/checkout.html', {'panier': panier})

        with transaction.atomic():
            # Lock rows so concurrent checkouts can't read stale stock values
            items = list(panier.items.select_related('produit').select_for_update())

            # Re-validate stock at the last moment before writing anything
            for item in items:
                try:
                    stock = Stock.objects.select_for_update().get(produit=item.produit)
                except Stock.DoesNotExist:
                    messages.error(request, f'"{item.produit.nom}" n\'est plus disponible.')
                    return redirect('panier')
                if item.quantite > stock.quantite:
                    messages.error(
                        request,
                        f'Stock insuffisant pour "{item.produit.nom}" (max {stock.quantite}).',
                    )
                    return redirect('panier')

            commande = Commande.objects.create(
                client=request.user,
                adresse=adresse,
                total=panier.total(),
            )

            for item in items:
                CommandeItem.objects.create(
                    commande=commande,
                    produit=item.produit,
                    quantite=item.quantite,
                    prix_unite=item.produit.prix,  # snapshot price at purchase time
                )
                # Deduct from stock
                stock = Stock.objects.select_for_update().get(produit=item.produit)
                stock.quantite -= item.quantite
                stock.save()

            panier.items.all().delete()  # Clear the cart after a successful order

        messages.success(request, f'Commande #{commande.id} passée avec succès !')
        return redirect('mes_commandes')

    return render(request, 'magazin/checkout.html', {'panier': panier})


@login_required
def mes_commandes(request):
    """Show the logged-in user's own order history, newest first."""
    commandes = Commande.objects.filter(client=request.user).order_by('-created_at')
    return render(request, 'magazin/commandes.html', {'commandes': commandes})


# ── Staff: order management ───────────────────────────────────────────────────

@login_required
@role_required('ADMIN', 'VENDEUR')
def gestion_commandes(request):
    """Admin/vendor view: list all orders with client and item details."""
    commandes = (
        Commande.objects
        .select_related('client')
        .prefetch_related('items__produit')
        .order_by('-created_at')
    )
    return render(request, 'magazin/gestion_commandes.html', {
        'commandes': commandes,
        'status_choices': Commande.STATUS_CHOICES,
    })


@login_required
@role_required('ADMIN', 'VENDEUR')
def modifier_statut_commande(request, commande_id):
    """Update an order's status (e.g. pending → shipped). POST only."""
    commande = get_object_or_404(Commande, id=commande_id)
    if request.method != 'POST':
        return redirect('gestion_commandes')

    nouveau_statut = request.POST.get('statut')
    statuts_valides = {code for code, _ in Commande.STATUS_CHOICES}
    if nouveau_statut not in statuts_valides:
        messages.error(request, 'Statut invalide.')
        return redirect('gestion_commandes')

    commande.statut = nouveau_statut
    commande.save(update_fields=['statut'])  # Only write the changed field
    messages.success(request, f'Statut de la commande #{commande.id} mis à jour.')
    return redirect('gestion_commandes')


# ── Staff: product management ─────────────────────────────────────────────────

@login_required
@role_required('VENDEUR', 'ADMIN')
def ajouter_produit(request):
    """Add a new product. A stock record (quantity 0) is created automatically."""
    from .forms import ProduitForm
    form = ProduitForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        produit = form.save()
        Stock.objects.get_or_create(produit=produit, defaults={'quantite': 0})
        messages.success(request, 'Produit ajouté avec succès.')
        return redirect('produits')
    return render(request, 'magazin/produit_form.html', {'form': form, 'titre': 'Ajouter un produit'})


@login_required
@role_required('VENDEUR', 'ADMIN')
def modifier_produit(request, produit_id):
    """Edit an existing product."""
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


@login_required
@role_required('VENDEUR', 'ADMIN')
def supprimer_produit(request, produit_id):
    """Delete a product after a POST confirmation step."""
    produit = get_object_or_404(Produit, id=produit_id)
    if request.method == 'POST':
        produit.delete()
        messages.success(request, 'Produit supprimé.')
        return redirect('produits')
    return render(request, 'magazin/produit_confirm_delete.html', {'produit': produit})


# ── Staff: stock management ───────────────────────────────────────────────────

@login_required
@role_required('VENDEUR', 'ADMIN')
def gerer_stock(request):
    """
    Overview of all product stock levels.
    Also computes the total stock value (sum of qty × price across all products).
    """
    from .forms import StockForm
    produits = Produit.objects.select_related('stock').all()
    total_stock_value = (
        Stock.objects.select_related('produit').aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('quantite') * F('produit__prix'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )['total']
        or 0  # Fall back to 0 if there are no stock records
    )
    return render(request, 'magazin/stock.html', {
        'produits': produits,
        'total_stock_value': total_stock_value,
    })


@login_required
@role_required('VENDEUR', 'ADMIN')
def modifier_stock(request, produit_id):
    """Update the stock quantity for a single product."""
    from .forms import StockForm
    produit = get_object_or_404(Produit, id=produit_id)
    stock, _ = Stock.objects.get_or_create(produit=produit)
    form = StockForm(request.POST or None, instance=stock)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Stock de "{produit.nom}" mis à jour.')
        return redirect('stock')
    return render(request, 'magazin/stock_form.html', {'form': form, 'produit': produit})


# ── Staff: supplier management ────────────────────────────────────────────────

@login_required
@role_required('VENDEUR', 'ADMIN')
def ajouter_fournisseur(request):
    from .forms import FournisseurForm
    form = FournisseurForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Fournisseur ajouté avec succès.')
        return redirect('fournisseurs')
    return render(request, 'magazin/fournisseur_form.html', {'form': form, 'titre': 'Ajouter un fournisseur'})


@login_required
@role_required('VENDEUR', 'ADMIN')
def modifier_fournisseur(request, fournisseur_id):
    from .forms import FournisseurForm
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    form = FournisseurForm(request.POST or None, instance=fournisseur)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Fournisseur modifié.')
        return redirect('fournisseurs')
    return render(request, 'magazin/fournisseur_form.html', {
        'form': form,
        'titre': 'Modifier le fournisseur',
        'fournisseur': fournisseur,
    })


@login_required
@role_required('VENDEUR', 'ADMIN')
def supprimer_fournisseur(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    if request.method == 'POST':
        fournisseur.delete()
        messages.success(request, 'Fournisseur supprimé.')
        return redirect('fournisseurs')
    return render(request, 'magazin/fournisseur_confirm_delete.html', {'fournisseur': fournisseur})


@login_required
@role_required('VENDEUR', 'ADMIN')
def liste_fournisseurs(request):
    fournisseurs = Fournisseur.objects.all()
    return render(request, 'magazin/fournisseurs.html', {'fournisseurs': fournisseurs})