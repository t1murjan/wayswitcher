#!/usr/bin/env python3
"""
Wayland Keyboard Interceptor & Clipboard Tool
Требования:
1. Установленные пакеты: python3-evdev, wl-clipboard (wl-copy, wl-paste)
2. Права на /dev/uinput (пользователь в группе uinput или правило udev)
3. Запуск в среде Wayland
"""

import os
import sys
import time
import signal
import subprocess
from evdev import InputDevice, categorize, ecodes, UInput, list_devices
from evdev.uinput import Capabilities

# Глобальный флаг для корректного завершения
running = True

def signal_handler(sig, frame):
    global running
    print("\nПолучен сигнал остановки. Завершение работы...")
    running = False

def check_wayland():
    """Проверяет, запущена ли сессия Wayland."""
    if not os.environ.get("WAYLAND_DISPLAY"):
        # Допускаем запуск в XWayland, но предупреждаем
        if not os.environ.get("DISPLAY"):
            print("Ошибка: Не найдено ни WAYLAND_DISPLAY, ни DISPLAY. Убедитесь, что графическая сессия активна.")
            return False
        print("Предупреждение: Запуск в среде X11 или XWayland. Функционал wl-clipboard может работать некорректно.")
    else:
        print(f"Обнаружена сессия Wayland: {os.environ['WAYLAND_DISPLAY']}")
    return True

def get_keyboard_device():
    """Находит подходящее устройство клавиатуры."""
    devices = [InputDevice(path) for path in list_devices()]
    
    # Фильтруем только клавиатуры
    keyboards = [dev for dev in devices if 'key' in dev.capabilities() and dev.name]
    
    if not keyboards:
        print("Ошибка: Не найдено устройств ввода с поддержкой клавиш.")
        return None
    
    # Приоритет: ищем устройство с названием, содержащим "Keyboard" или "AT Translated"
    for dev in keyboards:
        if "Keyboard" in dev.name or "AT Translated" in dev.name:
            return dev
    
    # Если не нашли по имени, берем первое попавшееся (с предупреждением)
    print(f"Предупреждение: Используется первое найденное устройство: {keyboards[0].name} ({keyboards[0].path})")
    return keyboards[0]

def setup_uinput():
    """Настраивает виртуальное устройство ввода."""
    try:
        # Определяем возможности виртуального устройства
        caps = {
            ecodes.EV_KEY: [ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C], # Пример, лучше скопировать все ключи
            ecodes.EV_SYN: []
        }
        
        # Для полноценной работы лучше скопировать все ключи с физического устройства,
        # но для демонстрации создадим базовое. 
        # В реальном проекте здесь нужно мапить все keycodes.
        # Используем упрощенный вариант создания UInput без явного списка всех ключей,
        # если библиотека позволяет, или передаем полный список.
        
        # Более надежный способ: взять способности у физического устройства
        # Но UInput требует явного перечисления. 
        # Для краткости примера создадим устройство, поддерживающее все стандартные клавиши.
        all_keys = [i for i in range(256)] # Грубый перебор кодов клавиш
        
        virt_caps = {
            ecodes.EV_KEY: all_keys,
            ecodes.EV_SYN: []
        }
        
        ui = UInput(virt_caps, name='WaylandInterceptor', vendor=0x1, product=0x1)
        print("Виртуальное устройство uinput успешно создано.")
        return ui
    except PermissionError:
        print("Ошибка: Нет прав на запись в /dev/uinput.")
        print("Решение: Добавьте пользователя в группу 'uinput' или создайте правило udev.")
        print("Команда для добавления в группу: sudo usermod -aG uinput $USER")
        return None
    except Exception as e:
        print(f"Ошибка при создании uinput: {e}")
        return None

def process_event(event, ui_device):
    """Обрабатывает событие клавиатуры."""
    # Пример логики: перехват Ctrl+Alt+T для открытия терминала через wl-clipboard или просто эмуляция
    # В данном примере мы просто передаем все нажатия дальше (проксирование),
    # но вы можете добавить свою логику перехвата.
    
    if event.type == ecodes.EV_KEY:
        # Эмулируем нажатие на виртуальном устройстве
        ui_device.syn()
        ui_device.write(event.type, event.code, event.value)
        ui_device.syn()
        
        # Пример специальной обработки (раскомментировать для теста):
        # if event.code == ecodes.KEY_SPACE and event.value == 1:
        #     print("Пробел перехвачен! Выполняем действие...")
        #     try:
        #         # Пример копирования текста в буфер Wayland
        #         subprocess.run(["wl-copy", "Текст перехвачен!"], check=True)
        #         print("Текст скопирован в буфер обмена.")
        #     except FileNotFoundError:
        #         print("Ошибка: wl-copy не найден. Установите пакет wl-clipboard.")
        #     except Exception as e:
        #         print(f"Ошибка при работе с буфером: {e}")
        #     return # Не передаем пробел дальше, если хотим его заблокировать

    # Передаем событие дальше (если не заблокировали выше)
    # В данной реализации мы пишем в uinput, что эмулирует нажатие.
    # Чтобы заблокировать оригинальное нажатие, нужно использовать grab_exclusive().

def main():
    global running
    
    # Установка обработчика сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("--- Запуск Wayland Keyboard Interceptor ---")
    
    # 1. Проверка окружения
    if not check_wayland():
        sys.exit(1)

    # 2. Поиск клавиатуры
    phys_dev = get_keyboard_device()
    if not phys_dev:
        sys.exit(1)
    
    print(f"Используется физическое устройство: {phys_dev.name} ({phys_dev.path})")

    # 3. Настройка uinput
    virt_dev = setup_uinput()
    if not virt_dev:
        sys.exit(1)

    # 4. Эксклюзивный захват (ВАЖНО для Wayland, чтобы дублирования не было)
    try:
        phys_dev.grab()
        print(f"Устройство {phys_dev.path} захвачено в эксклюзивном режиме.")
    except PermissionError:
        print("Ошибка: Не удалось захватить устройство. Возможно, нужен root или пользователь в группе input.")
        virt_dev.close()
        sys.exit(1)

    print("Ожидание событий... (Нажмите Ctrl+C для выхода)")

    try:
        while running:
            # Читаем события с неблокирующим таймаутом, чтобы можно было проверить флаг running
            try:
                event = phys_dev.read_one()
                if event:
                    process_event(event, virt_dev)
            except BlockingIOError:
                time.sleep(0.01) # Небольшая пауза чтобы не грузить CPU
            
            # Небольшая задержка для предотвращения высокой нагрузки CPU в цикле
            time.sleep(0.001)
            
    except Exception as e:
        print(f"Критическая ошибка в цикле: {e}")
    finally:
        # Освобождение ресурсов
        print("Освобождение ресурсов...")
        try:
            phys_dev.ungrab()
        except:
            pass
        virt_dev.close()
        print("Работа завершена.")

if __name__ == "__main__":
    # Проверка зависимостей перед запуском
    try:
        import evdev
    except ImportError:
        print("Ошибка: Модуль 'evdev' не установлен. Выполните: pip install evdev")
        sys.exit(1)

    # Проверка wl-clipboard (опционально, но желательно)
    if subprocess.run(["which", "wl-copy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print("Предупреждение: Утилита 'wl-copy' не найдена. Функции буфера обмена не будут работать.")
        print("Установите пакет 'wl-clipboard' через ваш менеджер пакетов.")

    main()
