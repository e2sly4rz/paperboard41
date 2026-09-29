from PIL import Image, ImageDraw, ImageFont
import os

# ============================================================
# КОНСТАНТЫ — пути к иконкам и настройки (меняй под себя)
# ============================================================

ICON1_PATH = "icons/players.png"       # иконка 1 — количество игроков
ICON2_PATH = "icons/duration.png"      # иконка 2 — длительность

# Папка, где лежат иконки сложности
DIFFICULTY_ICONS_DIR = "icons"
DIFFICULTY_ICONS = [
    "light.png",
    "medium_light.png",
    "medium.png",
    "medium_heavy.png",
    "heavy.png"
]

ICON_SIZE       = 150                  # итоговый размер иконки (из 256×256 уменьшится до этого)
TARGET_W, TARGET_H = 1000, 1000
BOTTOM_MARGIN   = 30                   # отступ блока иконок от нижнего края холста
ICON_GAP        = 30                   # расстояние между иконками
BG_COLOR        = (255, 255, 255)

def get_font(size=22):
    candidates = [
        "/usr/share/fonts/TTF/CaskaydiaMonoNerdFont-Regular.ttf",   # Linux
        "/Library/Fonts/Arial.ttf",                         # macOS
        "C:\\Windows\\Fonts\\arial.ttf",                    # Windows
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()

def fit_image(img, max_w, max_h):
    """Масштабирует изображение, сохраняя пропорции, чтобы оно вписалось в max_w x max_h."""
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)

def load_image(path, name):
    if not os.path.exists(path):
        print(f"Файл не найден: {name} — {path}")
        exit(1)
    return Image.open(path).convert("RGBA")

def ask(prompt):
    return input(prompt).strip()

def main():
    # --- Основное изображение ---
    main_path = ask("Путь к основному изображению (коробка игры): ")
    main_img = load_image(main_path, "основное изображение")
    main_img = fit_image(main_img, TARGET_W, TARGET_H)

    # Создаём холст
    canvas = Image.new("RGBA", (TARGET_W, TARGET_H), BG_COLOR + (255,))

    # Центрируем основное изображение
    mx = (TARGET_W - main_img.width) // 2
    my = (TARGET_H - main_img.height) // 2
    canvas.paste(main_img, (mx, my), main_img)

    # --- Иконки 1 и 2 (фиксированные) ---
    icon_paths = [ICON1_PATH, ICON2_PATH]
    icons = []
    for p in icon_paths:
        ic = load_image(p, f"иконка {p}")
        ic = fit_image(ic, ICON_SIZE, ICON_SIZE)
        icons.append(ic)

    # --- Иконка 3 (сложность): выбор из списка ---
    print("\nВыберите иконку сложности (введите номер):")
    for i, name in enumerate(DIFFICULTY_ICONS, start=1):
        print(f"{i}) {name}")

    while True:
        choice = ask("Ваш выбор (1–5): ")
        if choice.isdigit() and 1 <= int(choice) <= 5:
            idx = int(choice) - 1
            break
        else:
            print("Пожалуйста, введите число от 1 до 5.")

    diff_icon_name = DIFFICULTY_ICONS[idx]
    diff_icon_path = os.path.join(DIFFICULTY_ICONS_DIR, diff_icon_name)
    diff_icon = load_image(diff_icon_path, f"иконка сложности {diff_icon_name}")
    diff_icon = fit_image(diff_icon, ICON_SIZE, ICON_SIZE)
    icons.append(diff_icon)

    # Вычисляем позиции 3 иконок равномерно по нижнему краю
    block_w = 3 * ICON_SIZE + 2 * ICON_GAP
    start_x = (TARGET_W - block_w) // 2
    icon_y = TARGET_H - ICON_SIZE - BOTTOM_MARGIN

    positions = []
    for i in range(3):
        x = start_x + i * (ICON_SIZE + ICON_GAP)
        positions.append((x, icon_y))

    for ic, (x, y) in zip(icons, positions):
        canvas.paste(ic, (x, y), ic)

    # --- Интерактивный ввод подписей для иконок 1 и 2 ---
    print("\nТеперь введи подписи для первых двух иконок:")
    label1 = ask("1) Количество игроков: ")
    label2 = ask("2) Длительность партии: ")

    # Подпись для 3-й иконки фиксирована
    label3 = "Сложность"
    labels = [label1, label2, label3]

    # --- Рисуем подписи НА нижней части иконок (не под ними) ---
    draw = ImageDraw.Draw(canvas)
    font = get_font(size=25)  # чуть меньше, чтобы лучше влезало на иконку
    text_color = (255, 255, 255, 255)  # белый цвет текста

    # Процент высоты иконки, где будет текст (например, 85–95% по вертикали)
    TEXT_Y_RELATIVE = 0.73

    for i, label in enumerate(labels):
        x, y = positions[i]
        # Позиция текста: по центру иконки, в нижней её части
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Центр по X относительно иконки
        text_x = x + (ICON_SIZE - text_w) // 2
        # Y внутри иконки: TEXT_Y_RELATIVE * высота иконки + Y самой иконки
        text_y = y + int(TEXT_Y_RELATIVE * ICON_SIZE)

        draw.text((text_x, text_y), label, fill=text_color, font=font)

    # --- Запрос имени итогового файла ---
    filename = ask("\nИмя итогового файла (например, card.png): ")
    if not filename.lower().endswith(".png"):
        filename += ".png"
    output_path = os.path.join(os.getcwd(), filename)

    # --- Сохранение ---
    canvas.convert("RGB").save(output_path, format="PNG")
    print(f"Готово: {output_path}")

if __name__ == "__main__":
    main()
