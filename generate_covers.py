import os
import django
from PIL import Image, ImageDraw, ImageFont

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scr.settings')
django.setup()

from app.models import Book

def create_book_cover(filename, title, author, bg_color, accent_color):
    width, height = 400, 600
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Frame border
    draw.rectangle([16, 16, width - 16, height - 16], outline=accent_color, width=3)
    draw.rectangle([22, 22, width - 22, height - 22], outline=accent_color, width=1)

    # Header decorative element
    draw.line([80, 70, width - 80, 70], fill=accent_color, width=2)
    draw.rectangle([width//2 - 6, 67, width//2 + 6, 73], fill=accent_color)

    # Book spine shadow simulation on the left
    for i in range(12):
        draw.line([i, 0, i, height], fill=(0, 0, 0, int(80 - i * 6)))

    # Try default font
    try:
        font_large = ImageFont.truetype("arial.ttf", 26)
        font_medium = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw Title wrapped
    words = title.split(' ')
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        if len(" ".join(current_line)) > 18:
            lines.append(" ".join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    y_start = 180
    for line in lines:
        draw.text((width // 2, y_start), line, fill=(255, 255, 255), font=font_large, anchor="mm")
        y_start += 36

    # Decorative separator
    draw.line([120, y_start + 20, width - 120, y_start + 20], fill=accent_color, width=2)

    # Author
    draw.text((width // 2, y_start + 60), author, fill=accent_color, font=font_medium, anchor="mm")

    # Bottom badge
    draw.text((width // 2, height - 60), "KITOB DO'KONI", fill=(200, 200, 200), font=font_small, anchor="mm")

    out_path = os.path.join('media', 'covers', filename)
    img.save(out_path, quality=95)
    return f"covers/{filename}"

def update_all_covers():
    covers_data = {
        "9789943001111": ("otkan_kunlar.jpg", "O'tkan kunlar", "Abdulla Qodiriy", (26, 77, 46), (245, 214, 114)), # Emerald & Gold
        "9789943002222": ("mehrobdan_chayon.jpg", "Mehrobdan chayon", "Abdulla Qodiriy", (114, 27, 43), (250, 208, 100)), # Maroon & Gold
        "9789943003333": ("dunyoning_ishlari.jpg", "Dunyoning ishlari", "O'tkir Hoshimov", (30, 58, 138), (147, 197, 253)), # Deep Blue & Sky
        "9780132350884": ("clean_code.jpg", "Clean Code", "Robert C. Martin", (15, 23, 42), (56, 189, 248)), # Slate & Cyan
        "9789943554444": ("atom_odatlar.jpg", "Atom Odatlar", "James Clear", (194, 65, 12), (254, 215, 170)), # Vibrant Orange & Sand
        "9780134757599": ("refactoring.jpg", "Refactoring", "Martin Fowler", (19, 78, 74), (52, 211, 153)), # Teal & Mint
    }

    for barcode, (fname, title, author, bg, accent) in covers_data.items():
        book = Book.objects.filter(barcode=barcode).first()
        if book:
            rel_path = create_book_cover(fname, title, author, bg, accent)
            book.cover_image = rel_path
            book.save(update_fields=['cover_image'])
            print(f"Cover yaratildi: {book.title} -> {rel_path}")

if __name__ == '__main__':
    update_all_covers()
