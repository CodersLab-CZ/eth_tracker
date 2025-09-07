
"""
Forms for the Ethereum address tracker application.
"""
from django import forms
from .models import EthereumAddress, WatchList, Alert
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re

class CustomUserCreationForm(UserCreationForm):
    """Extended user registration form with additional fields."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name (optional)'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name (optional)'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        """Initialize form with Bootstrap styling."""
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })

    def clean_email(self):
        """Validate that email is unique."""
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        """Save user with email and optional name fields."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
        return user


class AddAddressForm(forms.ModelForm):
    """Form for adding a new Ethereum address to track."""

    class Meta:
        model = EthereumAddress
        fields = ['address', 'label']
        widgets = {
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '0x...',
                'required': True
            }),
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional label for this address'
            })
        }

    def clean_address(self):
        """Validate Ethereum address format."""
        address = self.cleaned_data['address']
        if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
            raise forms.ValidationError('Invalid Ethereum address format')
        return address.lower()


class CreateWatchListForm(forms.ModelForm):
    """Form for creating a new watchlist."""

    class Meta:
        model = WatchList
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            })
        }


class CreateAlertForm(forms.ModelForm):
    """Form for creating address alerts."""

    class Meta:
        model = Alert
        fields = ['address', 'alert_type', 'threshold']
        widgets = {
            'address': forms.Select(attrs={'class': 'form-control'}),
            'alert_type': forms.Select(attrs={'class': 'form-control'}),
            'threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            })
        }

    def __init__(self, user, *args, **kwargs):
        """Initialize form with user's addresses."""
        super().__init__(*args, **kwargs)
        self.fields['address'].queryset = EthereumAddress.objects.filter(
            watchlists__user=user
        ).distinct()


