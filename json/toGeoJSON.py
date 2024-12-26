import cv2
import numpy as np
import json

def image_to_geojson(image_path, geojson_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, binary = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    features = []
    for contour in contours:
        polygon = [[int(point[0][0]), int(point[0][1])] for point in contour]
        

        if polygon[0] != polygon[-1]:
            polygon.append(polygon[0])

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon]  
            },
            "properties": {
                "name": "Detected Area"  
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=4)


image_to_geojson("river.png", "river.geojson")
