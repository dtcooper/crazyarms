from django import forms
from django.core.exceptions import PermissionDenied
from django.contrib import admin, messages
from django.contrib.admin.helpers import AdminForm
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path

from common.admin import AssetAdminBase

from .forms import AudioAssetCreateForm, AudioAssetUploadForm
from .models import AudioAsset


class AudioAssetAdmin(AssetAdminBase):
    create_form = AudioAssetCreateForm

    def get_urls(self):
        return [path('upload/', self.admin_site.admin_view(self.upload_view),
                name='autodj_audioasset_upload')] + super().get_urls()

    def upload_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method == 'POST':
            form = AudioAssetUploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist('audios')
                audio_assets = []

                for file in files:
                    asset = AudioAsset(file=file)
                    audio_assets.append(asset)

                    try:
                        asset.clean()
                    except forms.ValidationError as validation_error:
                        for field, error_list in validation_error:
                            for error in error_list:
                                form.add_error('audios' if field == 'audio' else '__all__', error)

            # If no errors where added
            if form.is_valid():
                for audio_asset in audio_assets:
                    audio_asset.uploader = request.user
                    audio_asset.save()

                self.message_user(request, f'Uploaded {len(audio_assets)} audio assets.', messages.SUCCESS)

                return redirect('admin:autodj_audioasset_changelist')
        else:
            form = AudioAssetUploadForm()

        opts = self.model._meta
        return TemplateResponse(request, 'admin/autodj/audioasset/upload.html', {
            'adminform': AdminForm(form, [(None, {'fields': form.base_fields})],
                                   self.get_prepopulated_fields(request)),
            'app_label': opts.app_label,
            'errors': form.errors.values(),
            'form': form,
            'opts': opts,
            'save_on_top': self.save_on_top,
            'title': 'Bulk Upload Audio Assets',
            **self.admin_site.each_context(request),
        })


admin.site.register(AudioAsset, AudioAssetAdmin)
