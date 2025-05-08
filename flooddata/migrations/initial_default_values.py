from django.db import migrations, models
import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FloodZone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('geometry', django.contrib.gis.db.models.fields.PolygonField(srid=4326, verbose_name='Геометрия')),
                ('risk_level', models.PositiveSmallIntegerField(choices=[(1, 'Низкий'), (2, 'Средний'), (3, 'Высокий')], default=1, verbose_name='Уровень риска')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_zones', to=settings.AUTH_USER_MODEL, verbose_name='Создано')),
            ],
            options={
                'verbose_name': 'Зона затопления',
                'verbose_name_plural': 'Зоны затопления',
            },
        ),
        migrations.CreateModel(
            name='FloodEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Название события')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('geometry', django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326, verbose_name='Область затопления')),
                ('event_start', models.DateTimeField(verbose_name='Начало события')),
                ('event_end', models.DateTimeField(blank=True, null=True, verbose_name='Окончание события')),
                ('water_level', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Уровень воды (м)')),
                ('source', models.CharField(blank=True, max_length=255, verbose_name='Источник данных')),
                ('is_forecast', models.BooleanField(default=False, verbose_name='Прогноз')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_events', to=settings.AUTH_USER_MODEL, verbose_name='Создано')),
            ],
            options={
                'verbose_name': 'Событие затопления',
                'verbose_name_plural': 'События затопления',
            },
        ),
        migrations.CreateModel(
            name='MeasurementPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('code', models.CharField(blank=True, max_length=50, verbose_name='Код/Идентификатор')),
                ('location', django.contrib.gis.db.models.fields.PointField(srid=4326, verbose_name='Местоположение')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
            ],
            options={
                'verbose_name': 'Точка измерения',
                'verbose_name_plural': 'Точки измерения',
            },
        ),
        migrations.CreateModel(
            name='DEMFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Цифровая модель рельефа', max_length=255, verbose_name='Название')),
                ('file', models.FileField(upload_to='dem_files/user_%(uploaded_by)s/', verbose_name='DEM файл')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('upload_date', models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('is_base_layer', models.BooleanField(default=False, verbose_name='Базовый слой')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dem_files', to=settings.AUTH_USER_MODEL, verbose_name='Загружено')),
            ],
            options={
                'verbose_name': 'DEM файл',
                'verbose_name_plural': 'DEM файлы',
                'ordering': ['-upload_date'],
            },
        ),
        migrations.CreateModel(
            name='SatelliteImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Космический снимок', max_length=255, verbose_name='Название')),
                ('file', models.FileField(upload_to='satellite_images/user_%(uploaded_by)s/', verbose_name='Космический снимок')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('upload_date', models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')),
                ('image_date', models.DateField(verbose_name='Дата снимка')),
                ('status', models.CharField(choices=[('new', 'Новый'), ('processing', 'В обработке'), ('completed', 'Обработан'), ('error', 'Ошибка')], default='new', max_length=50, verbose_name='Статус')),
                ('area', django.contrib.gis.db.models.fields.PolygonField(blank=True, null=True, srid=4326, verbose_name='Область снимка')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='satellite_images', to=settings.AUTH_USER_MODEL, verbose_name='Загружено')),
            ],
            options={
                'verbose_name': 'Космический снимок',
                'verbose_name_plural': 'Космические снимки',
                'ordering': ['-upload_date'],
            },
        ),
        migrations.CreateModel(
            name='WaterLevelMeasurement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(verbose_name='Время измерения')),
                ('value', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='Значение (м)')),
                ('is_forecast', models.BooleanField(default=False, verbose_name='Прогноз')),
                ('point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='measurements', to='flooddata.measurementpoint', verbose_name='Точка измерения')),
            ],
            options={
                'verbose_name': 'Измерение уровня воды',
                'verbose_name_plural': 'Измерения уровня воды',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='FloodAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Анализ затопления', max_length=255, verbose_name='Название анализа')),
                ('flood_mask', models.FileField(blank=True, null=True, upload_to='analysis_results/user_%(created_by)s/', verbose_name='Маска затопления')),
                ('flood_vector', django.contrib.gis.db.models.fields.MultiPolygonField(blank=True, null=True, srid=4326, verbose_name='Векторный слой затопления')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('status', models.CharField(choices=[('pending', 'В очереди'), ('processing', 'В обработке'), ('completed', 'Завершено'), ('error', 'Ошибка')], default='pending', max_length=50, verbose_name='Статус')),
                ('error_message', models.TextField(blank=True, verbose_name='Сообщение об ошибке')),
                ('flooded_area_sqkm', models.FloatField(blank=True, null=True, verbose_name='Площадь затопления (кв.км)')),
                ('compared_with_base', models.BooleanField(default=False, verbose_name='Сравнено с базовым слоем')),
                ('dem_file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analyses', to='flooddata.demfile', verbose_name='DEM файл')),
                ('satellite_image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analyses', to='flooddata.satelliteimage', verbose_name='Космический снимок')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analyses', to=settings.AUTH_USER_MODEL, verbose_name='Создано')),
            ],
            options={
                'verbose_name': 'Анализ затопления',
                'verbose_name_plural': 'Анализы затоплений',
                'ordering': ['-created_at'],
            },
        ),
    ]