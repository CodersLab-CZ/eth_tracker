## tracker/views.py

"""
Views for the Ethereum address tracker application.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Sum
from django.utils import timezone
from .models import EthereumAddress, Transaction, WatchList, Alert
from .forms import AddAddressForm, CreateWatchListForm, CreateAlertForm
import requests
from django.db import models
from .forms import AddAddressForm, CreateWatchListForm
from .forms import CustomUserCreationForm


def register(request):
    """User registration view."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Create a default watchlist for the new user
            WatchList.objects.create(
                name="My Addresses",
                description="Default watchlist for tracked addresses",
                user=user
            )

            # Log the user in after successful registration
            login(request, user)
            messages.success(request, f'Welcome {user.username}! Your account has been created successfully.')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


def home(request):
    """Home page view showing recent transactions and top addresses."""
    recent_transactions = Transaction.objects.select_related(
        'from_address', 'to_address'
    ).order_by('-timestamp')[:10]

    top_addresses = EthereumAddress.objects.annotate(
        tx_count=Count('outgoing_transactions') + Count('incoming_transactions')
    ).order_by('-balance')[:5]

    context = {
        'recent_transactions': recent_transactions,
        'top_addresses': top_addresses,
    }
    return render(request, 'home.html', context)


def address_detail(request, address):
    """Detail view for a specific Ethereum address."""
    eth_address = get_object_or_404(EthereumAddress, address=address)

    # Get transactions for this address
    outgoing_txs = eth_address.outgoing_transactions.order_by('-timestamp')[:20]
    incoming_txs = eth_address.incoming_transactions.order_by('-timestamp')[:20]

    # Combine and sort transactions
    all_transactions = list(outgoing_txs) + list(incoming_txs)
    all_transactions.sort(key=lambda x: x.timestamp, reverse=True)

    context = {
        'address': eth_address,
        'transactions': all_transactions[:20],
        'outgoing_count': outgoing_txs.count(),
        'incoming_count': incoming_txs.count(),
    }
    return render(request, 'address_detail.html', context)


@login_required
def dashboard(request):
    """User dashboard showing their watchlists and tracked addresses."""
    user_watchlists = request.user.watchlists.prefetch_related('ethereumaddress_set')
    user_alerts = request.user.alerts.select_related('address').filter(is_active=True)

    # Get summary statistics
    total_addresses = EthereumAddress.objects.filter(
        watchlists__user=request.user
    ).distinct().count()

    total_balance = EthereumAddress.objects.filter(
        watchlists__user=request.user
    ).distinct().aggregate(Sum('balance'))['balance__sum'] or 0

    context = {
        'watchlists': user_watchlists,
        'alerts': user_alerts,
        'total_addresses': total_addresses,
        'total_balance': total_balance,
    }
    return render(request, 'dashboard.html', context)


@login_required
def add_address(request):
    """View for adding a new Ethereum address to track."""
    if request.method == 'POST':
        form = AddAddressForm(request.POST)
        if form.is_valid():
            address = form.save()

            # Create or get user's default watchlist
            default_watchlist, created = WatchList.objects.get_or_create(
                name="Default",
                user=request.user,
                defaults={'description': 'Default watchlist'}
            )

            # Add address to default watchlist
            default_watchlist.ethereumaddress_set.add(address)

            # Update address balance from blockchain (mock implementation)
            update_address_balance(address)

            messages.success(request, f'Address {address.address} added successfully!')
            return redirect('dashboard')
    else:
        form = AddAddressForm()

    return render(request, 'add_address.html', {'form': form})


@login_required
def create_watchlist(request):
    """View for creating a new watchlist."""
    if request.method == 'POST':
        form = CreateWatchListForm(request.POST)
        if form.is_valid():
            watchlist = form.save(commit=False)
            watchlist.user = request.user
            watchlist.save()
            messages.success(request, f'Watchlist "{watchlist.name}" created successfully!')
            return redirect('dashboard')
    else:
        form = CreateWatchListForm()

    return render(request, 'create_watchlist.html', {'form': form})


def api_address_balance(request, address):
    """API endpoint to get current balance of an address."""
    try:
        eth_address = get_object_or_404(EthereumAddress, address=address)
        # Mock balance update - in production, use Web3 or Etherscan API
        update_address_balance(eth_address)

        return JsonResponse({
            'address': eth_address.address,
            'balance': str(eth_address.balance),
            'last_updated': eth_address.last_updated.isoformat()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


import requests
from decimal import Decimal


def update_address_balance(address):
    ETHERSCAN_API_KEY = 'HB3STU4AAVGM74E1MBKJ9M77Z6VYRMW19J'
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={address.address}&tag=latest&apikey={ETHERSCAN_API_KEY}"

    response = requests.get(url)
    data = response.json()

    if data['status'] == '1':
        wei_balance = Decimal(data['result'])
        eth_balance = wei_balance / Decimal('1000000000000000000')  # convert wei to ETH
        address.balance = eth_balance
        address.last_updated = timezone.now()
        address.save()
    else:
        raise ValueError("Failed to fetch balance from Etherscan")

from django.conf import settings
from decimal import Decimal
import requests
from datetime import datetime
from django.utils import timezone


def address_detail(request, address):
    eth_address = get_object_or_404(EthereumAddress, address=address)

    # 👉 Fetch from Etherscan if no txs exist yet
    has_any = Transaction.objects.filter(
        models.Q(from_address=eth_address) | models.Q(to_address=eth_address)
    ).exists()

    if not has_any:
        fetch_transactions_from_etherscan(eth_address)

    outgoing_txs = eth_address.outgoing_transactions.order_by('-timestamp')[:20]
    incoming_txs = eth_address.incoming_transactions.order_by('-timestamp')[:20]

    all_transactions = list(outgoing_txs) + list(incoming_txs)
    all_transactions.sort(key=lambda x: x.timestamp, reverse=True)

    context = {
        'address': eth_address,
        'transactions': all_transactions[:20],
        'outgoing_count': outgoing_txs.count(),
        'incoming_count': incoming_txs.count(),
    }
    return render(request, 'address_detail.html', context)

"""Add or update fetch_transactions_from_etherscan"""



def fetch_transactions_from_etherscan(eth_address):
    api_key = settings.ETHERSCAN_API_KEY
    address = eth_address.address.lower()

    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&sort=desc&apikey={api_key}"
    response = requests.get(url)
    data = response.json()

    if data["status"] != "1":
        print("No transactions found or API error")
        return

    for tx in data["result"]:
        # Skip if already exists
        if Transaction.objects.filter(hash=tx["hash"]).exists():
            continue

        # Get or create from_address and to_address
        from_addr, _ = EthereumAddress.objects.get_or_create(address=tx["from"].lower())
        to_addr, _ = EthereumAddress.objects.get_or_create(address=tx["to"].lower())

        # Parse timestamp
        timestamp = timezone.make_aware(datetime.fromtimestamp(int(tx["timeStamp"])))

        Transaction.objects.create(
            hash=tx["hash"],
            from_address=from_addr,
            to_address=to_addr,
            value=Decimal(tx["value"]) / Decimal(10**18),
            gas_price=int(tx["gasPrice"]),
            gas_used=int(tx["gasUsed"]),
            block_number=int(tx["blockNumber"]),
            timestamp=timestamp,
            status=(tx["isError"] == "0"),
        )



from django.shortcuts import render


