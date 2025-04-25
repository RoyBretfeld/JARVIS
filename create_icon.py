from PIL import Image, ImageDraw
import os

def create_jarvis_icon():
    # Erstelle ein 256x256 Bild mit transparentem Hintergrund
    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Zeichne einen äußeren Ring
    margin = 20
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 outline=(0, 255, 255, 255), width=8)
    
    # Zeichne einen inneren Ring
    inner_margin = 60
    draw.ellipse([inner_margin, inner_margin, size-inner_margin, size-inner_margin], 
                 outline=(0, 255, 255, 200), width=6)
    
    # Zeichne einen zentralen Kreis
    center_margin = 100
    draw.ellipse([center_margin, center_margin, size-center_margin, size-center_margin], 
                 fill=(0, 255, 255, 150))
    
    # Zeichne Linien für einen futuristischen Effekt
    for i in range(8):
        angle = i * 45
        x1 = size/2 + (size/2 - margin) * 0.7 * (angle % 90 == 0)
        y1 = size/2 + (size/2 - margin) * 0.7 * (angle % 90 != 0)
        x2 = size/2 + (size/2 - inner_margin) * 0.7 * (angle % 90 == 0)
        y2 = size/2 + (size/2 - inner_margin) * 0.7 * (angle % 90 != 0)
        draw.line([(x1, y1), (x2, y2)], fill=(0, 255, 255, 200), width=4)
    
    # Speichere das Icon in verschiedenen Größen
    icon_sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
    icon_images = []
    
    for icon_size in icon_sizes:
        resized = image.resize(icon_size, Image.Resampling.LANCZOS)
        icon_images.append(resized)
    
    # Speichere als ICO-Datei
    icon_images[0].save('icon.ico', format='ICO', sizes=icon_sizes)
    print("Icon wurde erfolgreich erstellt!")

if __name__ == "__main__":
    create_jarvis_icon() 