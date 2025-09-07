import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from django.contrib.auth.models import User
from django.db import models
from ..models import Notification, NotificationPreference, EthereumAddress, Transaction, Alert

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling all types of notifications."""

    @staticmethod
    def create_notification(
            user,
            title: str,
            message: str,
            notification_type: str,
            priority: str = 'medium',
            address: Optional[EthereumAddress] = None,
            transaction: Optional[Transaction] = None,
            alert: Optional[Alert] = None,
            send_email: bool = True
    ) -> Notification:
        """Create a new notification."""

        # Create in-app notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            address=address,
            transaction=transaction,
            alert=alert
        )

        # Send email if enabled
        if send_email:
            NotificationService.send_email_notification(notification)

        logger.info(f"Created notification: {title} for user {user.username}")
        return notification

    @staticmethod
    def send_email_notification(notification: Notification) -> bool:
        """Send email notification to user."""
        try:
            # Get user preferences
            prefs, created = NotificationPreference.objects.get_or_create(
                user=notification.user
            )

            # Check if email notifications are enabled for this type
            email_enabled = getattr(prefs, f'email_{notification.notification_type}', True)

            if not email_enabled or notification.is_sent_email:
                return False

            # Prepare email content
            subject = f"[ETH Tracker] {notification.title}"

            # Use template for email body
            email_body = render_to_string('emails/notification_email.html', {
                'notification': notification,
                'user': notification.user,
                'site_name': 'ETH Tracker',
            })

            # Send email
            send_mail(
                subject=subject,
                message=notification.message,  # Plain text fallback
                html_message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.user.email],
                fail_silently=False,
            )

            # Mark as sent
            notification.is_sent_email = True
            notification.save(update_fields=['is_sent_email'])

            logger.info(f"Email sent for notification {notification.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification {notification.id}: {str(e)}")
            return False

    @staticmethod
    def notify_balance_change(address: EthereumAddress, old_balance: Decimal, new_balance: Decimal):
        """Notify users about balance changes."""
        change = new_balance - old_balance
        change_type = "increased" if change > 0 else "decreased"

        # Get all users watching this address
        users = User.objects.filter(watchlists__ethereumaddress=address).distinct()

        for user in users:
            title = f"Balance {change_type}: {address.label or address.address[:10]}..."
            message = f"Address balance {change_type} by {abs(change):.6f} ETH (from {old_balance:.6f} to {new_balance:.6f} ETH)"

            NotificationService.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type='balance_change',
                priority='medium',
                address=address
            )

    @staticmethod
    def notify_new_transaction(transaction: Transaction):
        """Notify users about new transactions."""
        # Notify users watching the from_address
        from_users = User.objects.filter(
            watchlists__ethereumaddress=transaction.from_address
        ).distinct()

        for user in from_users:
            title = f"Outgoing Transaction: {transaction.from_address.label or transaction.from_address.address[:10]}..."
            message = f"Sent {transaction.value:.6f} ETH to {transaction.to_address.address[:10]}..."

            NotificationService.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type='new_transaction',
                priority='low',
                address=transaction.from_address,
                transaction=transaction
            )

        # Notify users watching the to_address
        to_users = User.objects.filter(
            watchlists__ethereumaddress=transaction.to_address
        ).distinct()

        for user in to_users:
            title = f"Incoming Transaction: {transaction.to_address.label or transaction.to_address.address[:10]}..."
            message = f"Received {transaction.value:.6f} ETH from {transaction.from_address.address[:10]}..."

            NotificationService.create_notification(
                user=user,
                title=title,
                message=message,
                notification_type='new_transaction',
                priority='low',
                address=transaction.to_address,
                transaction=transaction
            )

    @staticmethod
    def get_unread_count(user) -> int:
        """Get count of unread notifications for user."""
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def mark_all_read(user):
        """Mark all notifications as read for user."""
        Notification.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )