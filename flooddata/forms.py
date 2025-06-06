from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import SatelliteImage, DEMFile, FloodAnalysis, WaterbodyVector
from django.db import models
import datetime

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Введите действующий email адрес")
    first_name = forms.CharField(max_length=30, required=False, help_text="Имя (необязательно)")
    last_name = forms.CharField(max_length=30, required=False, help_text="Фамилия (необязательно)")

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user 

class DEMFileUploadForm(forms.ModelForm):
    """Форма для загрузки DEM файла (цифровой модели рельефа)"""
    class Meta:
        model = DEMFile
        fields = ['name', 'file', 'description', 'is_base_layer']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Проверка расширения файла
            extension = file.name.split('.')[-1].lower()
            if extension not in ['tif', 'tiff', 'geotiff']:
                raise forms.ValidationError("Допустимы только файлы формата GeoTIFF (.tif, .tiff)")
            # Проверка размера файла (ограничение 100 МБ)
            if file.size > 100 * 1024 * 1024:
                raise forms.ValidationError("Размер файла не должен превышать 100 МБ")
        return file

class SatelliteImageUploadForm(forms.ModelForm):
    """Форма для загрузки космического снимка"""
    image_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=datetime.date.today,
        label="Дата снимка"
    )
    
    class Meta:
        model = SatelliteImage
        fields = ['name', 'file', 'description', 'image_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Проверка расширения файла
            extension = file.name.split('.')[-1].lower()
            if extension not in ['tif', 'tiff', 'geotiff', 'jpg', 'jpeg', 'png']:
                raise forms.ValidationError("Допустимы только файлы форматов GeoTIFF и изображения (jpg, png)")
            # Проверка размера файла (ограничение 200 МБ)
            if file.size > 200 * 1024 * 1024:
                raise forms.ValidationError("Размер файла не должен превышать 200 МБ")
        return file

class FloodAnalysisForm(forms.ModelForm):
    WATER_METHOD_CHOICES = [
        ('none', 'Не учитывать'),
        ('vector', 'Векторный слой водоёмов'),
        ('accumulation', 'Flow Accumulation (реки/озёра по аккумуляции)')
    ]
    permanent_water_method = forms.ChoiceField(
        choices=WATER_METHOD_CHOICES,
        required=False,
        label="Постоянные воды: способ определения"
    )
    waterbody_vector = forms.ModelChoiceField(
        queryset=WaterbodyVector.objects.filter(is_active=True),
        required=False,
        label="Векторный слой водоёмов (shp/geojson)"
    )
    accumulation_threshold = forms.IntegerField(
        required=False,
        initial=1000,
        min_value=1,
        label="Порог flow accumulation (река/озеро)"
    )
    class Meta:
        model = FloodAnalysis
        fields = [
            'name', 'dem_file', 'green_band_image', 'swir2_band_image',
            'permanent_water_method', 'waterbody_vector', 'accumulation_threshold'
        ]
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(FloodAnalysisForm, self).__init__(*args, **kwargs)
        
        # Фильтруем доступные пользователю DEM файлы и снимки
        if user:
            if user.is_staff:
                # Для админа - все файлы и активные базовые слои
                self.fields['dem_file'].queryset = DEMFile.objects.filter(is_active=True)
                self.fields['green_band_image'].queryset = SatelliteImage.objects.all()
                self.fields['swir2_band_image'].queryset = SatelliteImage.objects.all()
                self.fields['waterbody_vector'].queryset = WaterbodyVector.objects.filter(is_active=True)
            else:
                # Для обычного пользователя - свои файлы и общие базовые слои
                self.fields['dem_file'].queryset = DEMFile.objects.filter(
                    is_active=True
                ).filter(
                    models.Q(uploaded_by=user) | models.Q(is_base_layer=True)
                )
                self.fields['green_band_image'].queryset = SatelliteImage.objects.filter(uploaded_by=user)
                self.fields['swir2_band_image'].queryset = SatelliteImage.objects.filter(uploaded_by=user)
                self.fields['waterbody_vector'].queryset = WaterbodyVector.objects.filter(is_active=True, uploaded_by=user)

class WaterbodyVectorUploadForm(forms.ModelForm):
    # Изменяем поле file на zip_file для приема архива
    zip_file = forms.FileField(label="ZIP архив с векторным слоем (shp/geojson)")

    class Meta:
        model = WaterbodyVector
        fields = ['name', 'description'] # Удаляем 'file'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_zip_file(self):
        file = self.cleaned_data.get('zip_file')
        if file:
            extension = file.name.split('.')[-1].lower()
            if extension not in ['zip']:
                raise forms.ValidationError("Допустимы только файлы формата ZIP (.zip)")
            if file.size > 100 * 1024 * 1024: # Увеличиваем лимит для архивов
                raise forms.ValidationError("Размер файла не должен превышать 100 МБ")
        return file