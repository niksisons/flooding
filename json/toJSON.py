import cv2
import json

def extract_contours(image_path, output_json_path):
    # Загрузить изображение в оттенках серого
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # Бинаризация
    _, binary = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY)
    
    # Поиск контуров
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Сохраняем контуры как координаты
    contour_list = []
    for contour in contours:
        points = [{"x": int(pt[0][0]), "y": int(pt[0][1])} for pt in contour]
        contour_list.append(points)
    
    # Сохранение в JSON
    with open(output_json_path, "w") as json_file:
        json.dump(contour_list, json_file, indent=4)
    
    print(f"Контуры извлечены и сохранены в файл {output_json_path}")

# Пример использования
extract_contours("water_map.png", "contours.json")
