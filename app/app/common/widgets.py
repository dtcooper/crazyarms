from django import forms


class AlwaysClearableFileInput(forms.ClearableFileInput):
    template_name = "common/forms/widgets/always_clearable_file_input.html"
