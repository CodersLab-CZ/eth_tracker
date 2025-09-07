"""Models
for the Ethereum address tracker application.
"""
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User

class WatchList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlists')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EthereumAddress(models.Model):
    """Model representing an Ethereum address being tracked."""
    address = models.CharField(max_length=42, unique=True)
    label = models.CharField(max_length=100, blank=True)
    balance = models.DecimalField(max_digits=30, decimal_places=18, default=0)
    last_updated = models.DateTimeField(default=timezone.now)
    is_contract = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Many-to-many relationship with WatchList
    watchlists = models.ManyToManyField(WatchList, through='AddressWatchList', blank=True)

    def __str__(self):
        return self.label if self.label else self.address[:10] + "..."


class AddressWatchList(models.Model):
    """Through model for the many-to-many relationship between Address and WatchList."""
    address = models.ForeignKey(EthereumAddress, on_delete=models.CASCADE)
    watchlist = models.ForeignKey(WatchList, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['address', 'watchlist']

    def __str__(self):
        return f"{self.address} in {self.watchlist.name}"


class Transaction(models.Model):

    hash = models.CharField(max_length=66, unique=True)
    from_address = models.ForeignKey(
        EthereumAddress,
        on_delete=models.CASCADE,
        related_name='outgoing_transactions'
    )
    to_address = models.ForeignKey(
        EthereumAddress,
        on_delete=models.CASCADE,
        related_name='incoming_transactions'
    )
    value = models.DecimalField(max_digits=30, decimal_places=18)
    gas_price = models.BigIntegerField()
    gas_used = models.BigIntegerField()
    block_number = models.BigIntegerField()
    timestamp = models.DateTimeField()
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"Tx: {self.hash[:10]}... - {self.value} ETH"



class Alert(models.Model):

    ALERT_TYPES = [
        ('balance', 'Balance Change'),
        ('transaction', 'New Transaction'),
        ('large_transaction', 'Large Transaction'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    address = models.ForeignKey(EthereumAddress, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    threshold = models.DecimalField(max_digits=30, decimal_places=18, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.alert_type} alert for {self.address} by {self.user.username}"


class Notification(models.Model):
    """Model for in-app notifications."""
    NOTIFICATION_TYPES = [
        ('balance_change', 'Balance Change'),
        ('new_transaction', 'New Transaction'),
        ('large_transaction', 'Large Transaction'),
        ('alert_triggered', 'Alert Triggered'),
        ('system', 'System Notification'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    # Related objects
    address = models.ForeignKey('EthereumAddress', on_delete=models.CASCADE, null=True, blank=True)
    transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, null=True, blank=True)
    alert = models.ForeignKey('Alert', on_delete=models.CASCADE, null=True, blank=True)

    # Status fields
    is_read = models.BooleanField(default=False)
    is_sent_email = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class NotificationPreference(models.Model):
    """User notification preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')

    # Email notifications
    email_balance_changes = models.BooleanField(default=True)
    email_new_transactions = models.BooleanField(default=True)
    email_large_transactions = models.BooleanField(default=True)
    email_alert_triggers = models.BooleanField(default=True)
    email_system_notifications = models.BooleanField(default=True)

    # In-app notifications
    inapp_balance_changes = models.BooleanField(default=True)
    inapp_new_transactions = models.BooleanField(default=True)
    inapp_large_transactions = models.BooleanField(default=True)
    inapp_alert_triggers = models.BooleanField(default=True)
    inapp_system_notifications = models.BooleanField(default=True)

    # Thresholds
    large_transaction_threshold = models.DecimalField(max_digits=30, decimal_places=18, default=10)

    # Frequency settings
    email_digest_frequency = models.CharField(max_length=20, choices=[
        ('instant', 'Instant'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('never', 'Never'),
    ], default='instant')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification preferences for {self.user.username}"


from django.db import models


