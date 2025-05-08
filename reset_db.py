"""
Скрипт для сброса базы данных и подготовки к новым миграциям.
Используйте только в разработке!
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'floodportal.settings')
django.setup()

from django.db import connection

def reset_flooddata_tables():
    """Сбрасывает все таблицы приложения flooddata и удаляет записи о миграциях"""
    cursor = connection.cursor()
    
    print("Удаление таблиц flooddata...")
    
    # Удаляем все таблицы flooddata
    tables = [
        'flooddata_floodzone',
        'flooddata_floodevent',
        'flooddata_measurementpoint',
        'flooddata_waterlevelmeasurement',
        'flooddata_demfile',
        'flooddata_satelliteimage',
        'flooddata_floodanalysis'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"Таблица {table} удалена")
        except Exception as e:
            print(f"Ошибка при удалении {table}: {e}")
    
    print("\nУдаление записей о миграциях...")
    # Удаляем записи миграций для flooddata
    cursor.execute("DELETE FROM django_migrations WHERE app = 'flooddata'")
    connection.commit()
    
    print("\nБаза данных сброшена.")
    print("Теперь выполните следующие команды:")
    print("python manage.py makemigrations flooddata")
    print("python manage.py migrate")

if __name__ == "__main__":
    confirm = input("Вы собираетесь сбросить базу данных. Это приведет к потере всех данных. Продолжить? (yes/no): ")
    if confirm.lower() == 'yes':
        reset_flooddata_tables()
    else:
        print("Операция отменена.")