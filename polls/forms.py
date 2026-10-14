from django import forms

from .models import LEVELS
from .services import MAX_OPTIONS, MIN_OPTIONS, normalize_option_text


class PollForm(forms.Form):
    question = forms.CharField(label="Sorun ne?", max_length=160, strip=True)
    details = forms.CharField(label="Kısa açıklama (opsiyonel)", max_length=300, required=False, strip=True)
    indecision_level = forms.TypedChoiceField(
        label="Ne kadar kararsızsın?",
        choices=[(k, v[0]) for k, v in LEVELS.items()],
        coerce=int,
        initial=2,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(MAX_OPTIONS):
            self.fields[f"option_{i}"] = forms.CharField(
                label=f"Seçenek {i + 1}", max_length=80, required=False, strip=True
            )

    def clean_question(self):
        question = " ".join(self.cleaned_data["question"].split())
        if len(question) < 5:
            raise forms.ValidationError("Soru en az 5 karakter olmalı.")
        return question

    def clean(self):
        cleaned = super().clean()
        texts = []
        for i in range(MAX_OPTIONS):
            text = normalize_option_text(cleaned.get(f"option_{i}") or "")
            if text:
                texts.append(text)
        if len(texts) < MIN_OPTIONS:
            raise forms.ValidationError("En az 2 seçenek girmelisin.")
        if len({t.casefold() for t in texts}) != len(texts):
            raise forms.ValidationError("Aynı seçeneği iki kez yazmışsın.")
        cleaned["option_texts"] = texts
        return cleaned

    @property
    def option_fields(self):
        return [self[f"option_{i}"] for i in range(MAX_OPTIONS)]
