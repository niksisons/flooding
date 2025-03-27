import pandas as pd

def normalize_data(file_path: str) -> pd.DataFrame:

    df = pd.read_csv(file_path, index_col=0)
    

    df[['x', 'y']] = df['coordinates'].str.split(expand=True)
    

    df['x'] = pd.to_numeric(df['x'], errors='coerce')
    df['y'] = pd.to_numeric(df['y'], errors='coerce')
    
    df = df.drop(columns=['coords'])
    

    return df