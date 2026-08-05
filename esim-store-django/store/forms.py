import re

from django import forms


def normalize_phone(phone: str) -> str:
    phone = phone.strip()
    digits = re.sub(r"\D+", "", phone)
    return "+" + digits


class ContactForm(forms.Form):
    email = forms.EmailField(error_messages={"invalid": "Укажите корректный email."})
    phone = forms.CharField(max_length=20)

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if not re.match(r"^\+\d{9,15}$", phone):
            raise forms.ValidationError(
                "Укажите номер телефона в международном формате, например +992900000000."
            )
        return phone


class CodeForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=4)


class ReceiptForm(forms.Form):
    receipt = forms.FileField(error_messages={"required": "Загрузите скриншот или PDF чека."})
