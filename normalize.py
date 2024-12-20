import pandas as pd

def normalize_data(file_path: str) -> pd.DataFrame:
    """
    Функция нормализует данные: разделяет столбец coords на x и y и удаляет ненужный индекс.
    
    Args:
        file_path (str): Путь к CSV-файлу.

    Returns:
        pd.DataFrame: Нормализованные данные с отдельными x и y.
    """
    # Читаем данные, убираем индексный столбец (Unnamed)
    df = pd.read_csv(file_path, index_col=0)
    
    # Разделяем столбец coords на два: x и y
    df[['x', 'y']] = df['coordinates'].str.split(expand=True)
    
    # Преобразуем x и y в числовой формат
    df['x'] = pd.to_numeric(df['x'], errors='coerce')
    df['y'] = pd.to_numeric(df['y'], errors='coerce')
    
    # Удаляем старый столбец coords
    df = df.drop(columns=['coords'])
    
    # Возвращаем результат
    return df