from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username")
        labels = {"email": "E-posta", "username": "Kullanıcı adı"}
        error_messages = {
            "email": {"unique": "Bu e-posta ile zaten bir hesap var."},
            "username": {"unique": "Bu kullanıcı adı alınmış."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Parola"
        self.fields["password2"].label = "Parola (tekrar)"
        self.fields["username"].help_text = "3-20 karakter: küçük harf, rakam, _ ve ."
        self.fields["username"].widget.attrs.update(
            {"autocapitalize": "none", "autocomplete": "username", "data-username-hint": ""}
        )
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})
        self.error_messages["password_mismatch"] = "Parolalar eşleşmiyor."
        self.fields["password2"].error_messages["required"] = "Parolayı tekrar yaz."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta ile zaten bir hesap var.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu kullanıcı adı alınmış.")
        return username


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "E-posta veya parola hatalı.",
        "inactive": "Bu hesap aktif değil.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-posta"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autofocus": True, "autocomplete": "email"}
        )
        self.fields["password"].label = "Parola"

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
