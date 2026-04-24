#!/usr/bin/env python3
import evdev
import time
import subprocess
import threading
import sys

# --- НАСТРОЙКИ ---
DOUBLE_TAP_TIMEOUT = 0.4  # Максимальное время между нажатиями Shift (в секундах)
SHIFT_KEYS = [evdev.ecodes.KEY_LEFTSHIFT, evdev.ecodes.KEY_RIGHTSHIFT]

# Словари для конвертации
EN = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`"
RU = "йцукенгшщзхъфывапролджэячсмитьбю.ё"
EN_UPPER = "QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>/~"
RU_UPPER = "ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё"

MAP_EN_TO_RU = dict(zip(EN + EN_UPPER, RU + RU_UPPER))
MAP_RU_TO_EN = dict(zip(RU + RU_UPPER, EN + EN_UPPER))

def convert_text(text):
    """Определяет язык и конвертирует текст"""
    ru_count = sum(1 for char in text if char in MAP_RU_TO_EN)
    en_count = sum(1 for char in text if char in MAP_EN_TO_RU)

    if not text.strip():
        return text

    if ru_count > en_count:
        # Переводим в английский
        return ''.join(MAP_RU_TO_EN.get(c, c) for c in text)
    else:
        # Переводим в русский
        return ''.join(MAP_EN_TO_RU.get(c, c) for c in text)

def get_clipboard():
    try:
        return subprocess.check_output(['wl-paste'], text=True)
    except Exception:
        return ""

def set_clipboard(text):
    try:
        subprocess.run(['wl-copy'], input=text, text=True, check=True)
    except Exception as e:
        print(f"Ошибка буфера обмена: {e}")

def simulate_key(ui, key_code, state):
    """state: 1 - press, 0 - release"""
    ui.write(evdev.ecodes.EV_KEY, key_code, state)
    ui.syn()

def tap_key(ui, key_code):
    simulate_key(ui, key_code, 1)
    time.sleep(0.01)
    simulate_key(ui, key_code, 0)

def execute_replacement(ui):
    """Логика замены текста"""
    print("Триггер сработал! Заменяем текст...")

    # 1. Сохраняем текущий буфер обмена
    old_clipboard = get_clipboard()

    # Очищаем буфер, чтобы понять, скопировалось ли что-то новое
    set_clipboard("")
    time.sleep(0.05)

    # 2. Пытаемся скопировать ВЫДЕЛЕННЫЙ текст (Ctrl+C)
    simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 1)
    tap_key(ui, evdev.ecodes.KEY_C)
    simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 0)
    time.sleep(0.1) # Ждем, пока Wayland обновит буфер

    current_clipboard = get_clipboard()

    # 3. Если ничего не скопировалось (текст не был выделен)
    if not current_clipboard:
        # Пытаемся выделить последнее слово (Ctrl+Shift+Left)
        simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 1)
        simulate_key(ui, evdev.ecodes.KEY_LEFTSHIFT, 1)
        tap_key(ui, evdev.ecodes.KEY_LEFT)
        simulate_key(ui, evdev.ecodes.KEY_LEFTSHIFT, 0)
        simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 0)
        time.sleep(0.05)

        # Снова копируем (Ctrl+C)
        simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 1)
        tap_key(ui, evdev.ecodes.KEY_C)
        simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 0)
        time.sleep(0.1)

        current_clipboard = get_clipboard()

    # 4. Если текст получен - конвертируем и вставляем
    if current_clipboard:
        new_text = convert_text(current_clipboard)
        set_clipboard(new_text)
        time.sleep(0.05)

        # Вставляем (Ctrl+V)
        simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 1)
        tap_key(ui, evdev.ecodes.KEY_V)
        simulate_key(ui, evdev.ecodes.KEY_LEFTCTRL, 0)
        time.sleep(0.1)

        # Возвращаем старый буфер обмена
        set_clipboard(old_clipboard)
    else:
        print("Не удалось получить текст для замены.")
        set_clipboard(old_clipboard)

def main():
    # Ищем клавиатуру среди устройств ввода
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    keyboard = None
    for device in devices:
        # Эвристика: ищем устройство, у которого есть клавиша ESC и Shift
        capabilities = device.capabilities().get(evdev.ecodes.EV_KEY, [])
        if evdev.ecodes.KEY_ESC in capabilities and evdev.ecodes.KEY_LEFTSHIFT in capabilities:
            keyboard = device
            print(f"Найдена клавиатура: {keyboard.name} ({keyboard.path})")
    if not keyboard:
        print("Клавиатура не найдена! Запустите скрипт через sudo.")
        sys.exit(1)

    # Создаем виртуальную клавиатуру для отправки нажатий (Ctrl+C, Ctrl+V)
    ui = evdev.UInput()

    last_shift_time = 0

    print(f"Скрипт запущен. Ожидание двойного нажатия Shift (таймаут {DOUBLE_TAP_TIMEOUT}с)...")

    # Слушаем события ввода
    for event in keyboard.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            # Если клавиша нажата (value = 1)
            if event.value == 1:
                if event.code in SHIFT_KEYS:
                    current_time = time.time()
                    if current_time - last_shift_time < DOUBLE_TAP_TIMEOUT:
                        # Двойное нажатие зафиксировано!
                        # Запускаем в отдельном потоке, чтобы не блокировать чтение эвентов
                        threading.Thread(target=execute_replacement, args=(ui,)).start()
                        last_shift_time = 0 # Сбрасываем таймер
                    else:
                        last_shift_time = current_time
                else:
                    # Если нажата любая другая клавиша, сбрасываем счетчик двойного клика
                    last_shift_time = 0

if __name__ == "__main__":
    main()

    if not keyboard:
        print("Клавиатура не найдена! Запустите скрипт через sudo.")
        sys.exit(1)

    # Создаем виртуальную клавиатуру для отправки нажатий (Ctrl+C, Ctrl+V)
    ui = evdev.UInput()

    last_shift_time = 0

    print(f"Скрипт запущен. Ожидание двойного нажатия Shift (таймаут {DOUBLE_TAP_TIMEOUT}с)...")

    # Слушаем события ввода
    for event in keyboard.read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            # Если клавиша нажата (value = 1)
            if event.value == 1:
                if event.code in SHIFT_KEYS:
                    current_time = time.time()
                    if current_time - last_shift_time < DOUBLE_TAP_TIMEOUT:
                        # Двойное нажатие зафиксировано!
                        # Запускаем в отдельном потоке, чтобы не блокировать чтение эвентов
                        threading.Thread(target=execute_replacement, args=(ui,)).start()
                        last_shift_time = 0 # Сбрасываем таймер
                    else:
                        last_shift_time = current_time
                else:
                    # Если нажата любая другая клавиша, сбрасываем счетчик двойного клика
                    last_shift_time = 0

if __name__ == "__main__":
    main()
