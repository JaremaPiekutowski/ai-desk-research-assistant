import os
from django import forms

class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class ResearchForm(forms.Form):
    documents = MultipleFileField(
        label='Upload Documents (PDF, DOCX, PPTX, TXT)',
        required=True
    )
    query = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Research Query',
        required=True
    )

    def clean_documents(self):
        files = self.cleaned_data['documents']  # Now this will be a list of files
        allowed_extensions = ['.pdf', '.docx', '.pptx', '.txt']
        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(f"Unsupported file type: {f.name}. Allowed types: {', '.join(allowed_extensions)}")
            # Optional: Add file size validation
            # if f.size > MAX_UPLOAD_SIZE:
            #     raise forms.ValidationError(f"File too large: {f.name}")
        return files
