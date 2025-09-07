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
from django.core.paginator import Paginator
from .models import Notification, NotificationPreference
from .services.notification_service import NotificationService
from django.views.decorators.http import require_http_methods




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
    """Update address balance from Etherscan API with notifications."""
    old_balance = address.balance

    ETHERSCAN_API_KEY = 'HB3STU4AAVGM74E1MBKJ9M77Z6VYRMW19J'
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={address.address}&tag=latest&apikey={ETHERSCAN_API_KEY}"

    response = requests.get(url)
    data = response.json()

    if data['status'] == '1':
        wei_balance = Decimal(data['result'])
        eth_balance = wei_balance / Decimal('1000000000000000000')  # convert wei to ETH

        # Update address
        address.balance = eth_balance
        address.last_updated = timezone.now()
        address.save()

        # ADD THESE LINES - Notify users of significant balance changes
        if abs(eth_balance - old_balance) > Decimal('0.001'):  # Only notify for changes > 0.001 ETH
            NotificationService.notify_balance_change(address, old_balance, eth_balance)

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

        # CREATE TRANSACTION - Changed from create() to get_or_create() for safety
        tx_obj, created = Transaction.objects.get_or_create(
            hash=tx["hash"],
            defaults={
                'from_address': from_addr,
                'to_address': to_addr,
                'value': Decimal(tx["value"]) / Decimal(10 ** 18),
                'gas_price': int(tx["gasPrice"]),
                'gas_used': int(tx["gasUsed"]),
                'block_number': int(tx["blockNumber"]),
                'timestamp': timestamp,
                'status': (tx["isError"] == "0"),
            }
        )

        # ADD THESE LINES - Send notifications for new transactions
        if created:
            NotificationService.notify_new_transaction(tx_obj)


@login_required
def notifications(request):
    """View all notifications for the user."""
    notifications_list = Notification.objects.filter(user=request.user)

    # Pagination
    paginator = Paginator(notifications_list, 20)
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)

    # Mark notifications as read when viewed
    unread_notifications = notifications_list.filter(is_read=False)
    for notification in unread_notifications:
        notification.mark_as_read()

    context = {
        'notifications': notifications_page,
        'unread_count': 0,  # Now 0 since we marked them as read
    }
    return render(request, 'notifications/list.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read."""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user
    )
    notification.mark_as_read()

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the user."""
    NotificationService.mark_all_read(request.user)
    return JsonResponse({'success': True})


@login_required
def notification_preferences(request):
    """View and update notification preferences."""
    prefs, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':
        # Update preferences
        prefs.email_balance_changes = request.POST.get('email_balance_changes') == 'on'
        prefs.email_new_transactions = request.POST.get('email_new_transactions') == 'on'
        prefs.email_large_transactions = request.POST.get('email_large_transactions') == 'on'
        prefs.email_alert_triggers = request.POST.get('email_alert_triggers') == 'on'
        prefs.email_system_notifications = request.POST.get('email_system_notifications') == 'on'

        prefs.inapp_balance_changes = request.POST.get('inapp_balance_changes') == 'on'
        prefs.inapp_new_transactions = request.POST.get('inapp_new_transactions') == 'on'
        prefs.inapp_large_transactions = request.POST.get('inapp_large_transactions') == 'on'
        prefs.inapp_alert_triggers = request.POST.get('inapp_alert_triggers') == 'on'
        prefs.inapp_system_notifications = request.POST.get('inapp_system_notifications') == 'on'

        large_threshold = request.POST.get('large_transaction_threshold')
        if large_threshold:
            try:
                prefs.large_transaction_threshold = Decimal(large_threshold)
            except:
                pass

        prefs.email_digest_frequency = request.POST.get('email_digest_frequency', 'instant')
        prefs.save()

        messages.success(request, 'Notification preferences updated successfully!')
        return redirect('notification_preferences')

    return render(request, 'notifications/preferences.html', {'preferences': prefs})


@login_required
def get_notification_count(request):
    """AJAX endpoint to get unread notification count."""
    count = NotificationService.get_unread_count(request.user)
    return JsonResponse({'count': count})


from django.shortcuts import render


