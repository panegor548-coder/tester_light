import tkinter as tk
import customtkinter as ctk
import serial
import serial.tools.list_ports
import json
import threading
import time
import os

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

PRESETS_FILE = "presets.json"

DEFAULT_PRESETS = {
    "По умолчанию": {
        "del_diff": 0, "dur_diff": 10,
        "del_beam": 10, "dur_beam": 10,
        "del_back": 20, "dur_back": 10,
        "del_s1": 2, "dur_s1": 15,
        "del_s2": 5, "dur_s2": 15
    }
}

class StandApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FPV Stand Controller")
        self.geometry("1000x920")

        self.ser = None

        # --- Состояние сценария ---
        self.is_running = False
        self.is_paused = False
        self.elapsed_total = 0.0

        # --- База пресетов ---
        self.presets = self.load_presets_from_file()

        self.setup_ui()
        self.refresh_com_ports()

    # ==========================================
    # РАБОТА С ПРЕСЕТАМИ (JSON)
    # ==========================================
    def load_presets_from_file(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка чтения пресетов: {e}")
        return DEFAULT_PRESETS.copy()

    def save_presets_to_file(self):
        try:
            with open(PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения пресетов: {e}")

    # ==========================================
    # ИНТЕРФЕЙС (UI)
    # ==========================================
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ------------------------------------------
        # ЛЕВАЯ ПАНЕЛЬ: Связь и Ручное Управление
        # ------------------------------------------
        left_frame = ctk.CTkFrame(self)
        left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(left_frame, text="🔌 Подключение COM-порта", font=("Arial", 16, "bold")).pack(pady=5)

        com_box = ctk.CTkFrame(left_frame)
        com_box.pack(fill="x", padx=10, pady=5)

        self.port_combo = ctk.CTkOptionMenu(com_box, values=["Поиск..."])
        self.port_combo.pack(side="left", padx=5, expand=True, fill="x")

        btn_refresh = ctk.CTkButton(com_box, text="🔄", width=35, command=self.refresh_com_ports)
        btn_refresh.pack(side="left", padx=2)

        self.btn_connect = ctk.CTkButton(com_box, text="Подключить", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=5)

        ctk.CTkLabel(left_frame, text="🎛️ Ручное Управление (Свет / Сервы)", font=("Arial", 16, "bold")).pack(pady=(15, 5))

        # Ползунки DMX Света
        self.slider_diffuse = self.create_manual_slider(left_frame, "Рассеянный свет (Diff)", 0, 255)
        self.slider_beam = self.create_manual_slider(left_frame, "Направленный луч (Beam)", 0, 255)
        self.slider_back = self.create_manual_slider(left_frame, "Контровой свет (Back)", 0, 255)

        # Ползунки Сервоприводов
        self.slider_s1 = self.create_manual_slider(left_frame, "Сервопривод 1 (°)", 0, 180)
        self.slider_s2 = self.create_manual_slider(left_frame, "Сервопривод 2 (°)", 0, 180)

        # ------------------------------------------
        # ПРАВАЯ ПАНЕЛЬ: Автоматический Сценарий
        # ------------------------------------------
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(right_frame, text="⏱️ Настройка Авто-Сценария", font=("Arial", 16, "bold")).pack(pady=5)

        # Блок управления пресетами
        preset_box = ctk.CTkFrame(right_frame)
        preset_box.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(preset_box, text="Пресет:").pack(side="left", padx=5)

        self.preset_combo = ctk.CTkOptionMenu(preset_box, values=list(self.presets.keys()), command=self.on_preset_select)
        self.preset_combo.pack(side="left", padx=5, expand=True, fill="x")

        btn_save_preset = ctk.CTkButton(preset_box, text="💾 Сохранить", width=80, command=self.save_current_preset)
        btn_save_preset.pack(side="left", padx=2)

        btn_new_preset = ctk.CTkButton(preset_box, text="➕ Новый", width=60, command=self.create_new_preset)
        btn_new_preset.pack(side="left", padx=2)

        # Ползунки временных интервалов для каждого канала
        self.slider_del_diff, self.slider_dur_diff, self.lbl_del_diff, self.lbl_dur_diff = self.create_channel_time_sliders(right_frame, "💡 Рассеянный свет")
        self.slider_del_beam, self.slider_dur_beam, self.lbl_del_beam, self.lbl_dur_beam = self.create_channel_time_sliders(right_frame, "🔦 Направленный луч")
        self.slider_del_back, self.slider_dur_back, self.lbl_del_back, self.lbl_dur_back = self.create_channel_time_sliders(right_frame, "☀️ Контровой свет")
        self.slider_del_s1, self.slider_dur_s1, self.lbl_del_s1, self.lbl_dur_s1 = self.create_channel_time_sliders(right_frame, "⚙️ Сервопривод 1")
        self.slider_del_s2, self.slider_dur_s2, self.lbl_del_s2, self.lbl_dur_s2 = self.create_channel_time_sliders(right_frame, "⚙️ Сервопривод 2")

        # Загружаем настройки выбранного пресета по умолчанию
        self.apply_preset_values(self.preset_combo.get())

        # Статус сценария
        self.lbl_status = ctk.CTkLabel(right_frame, text="Статус: Готов к запуску", font=("Arial", 14), text_color="gray")
        self.lbl_status.pack(pady=10)

        # Кнопки управления сценарием
        btn_box = ctk.CTkFrame(right_frame)
        btn_box.pack(fill="x", padx=10, pady=5)

        self.btn_start = ctk.CTkButton(btn_box, text="▶ Старт", fg_color="green", hover_color="darkgreen", command=self.start_scenario)
        self.btn_start.pack(side="left", padx=5, expand=True, fill="x")

        self.btn_pause = ctk.CTkButton(btn_box, text="⏸ Пауза", fg_color="orange", hover_color="darkorange", command=self.toggle_pause, state="disabled")
        self.btn_pause.pack(side="left", padx=5, expand=True, fill="x")

        self.btn_stop = ctk.CTkButton(btn_box, text="⏹ Стоп", fg_color="red", hover_color="darkred", command=self.stop_scenario, state="disabled")
        self.btn_stop.pack(side="left", padx=5, expand=True, fill="x")

    # --- Вспомогательные элементы UI ---
    def create_manual_slider(self, parent, label_text, min_v, max_v):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=10, pady=5)
        
        lbl = ctk.CTkLabel(frame, text=f"{label_text}: 0")
        lbl.pack(anchor="w", padx=5)

        slider = ctk.CTkSlider(frame, from_=min_v, to=max_v, number_of_steps=max_v-min_v)
        slider.set(0)
        slider.configure(command=lambda v: [lbl.configure(text=f"{label_text}: {int(v)}"), self.send_manual_state()])
        slider.pack(fill="x", padx=5, pady=2)
        return slider

    def create_channel_time_sliders(self, parent, title):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(frame, text=title, font=("Arial", 13, "bold")).pack(anchor="w", padx=5, pady=(2, 0))

        # Ползунок Задержки
        lbl_del = ctk.CTkLabel(frame, text="Задержка старта: 0 сек")
        lbl_del.pack(anchor="w", padx=10)
        s_del = ctk.CTkSlider(frame, from_=0, to=300, number_of_steps=300)
        s_del.configure(command=lambda v: lbl_del.configure(text=f"Задержка старта: {int(v)} сек"))
        s_del.pack(fill="x", padx=10, pady=1)

        # Ползунок Длительности
        lbl_dur = ctk.CTkLabel(frame, text="Время работы: 10 сек")
        lbl_dur.pack(anchor="w", padx=10)
        s_dur = ctk.CTkSlider(frame, from_=0, to=300, number_of_steps=300)
        s_dur.configure(command=lambda v: lbl_dur.configure(text=f"Время работы: {int(v)} сек"))
        s_dur.pack(fill="x", padx=10, pady=1)

        return s_del, s_dur, lbl_del, lbl_dur

    # --- Логика Управления Пресетами ---
    def apply_preset_values(self, preset_name):
        if preset_name not in self.presets:
            return
        data = self.presets[preset_name]

        self.slider_del_diff.set(data.get("del_diff", 0))
        self.lbl_del_diff.configure(text=f"Задержка старта: {int(data.get('del_diff', 0))} сек")
        self.slider_dur_diff.set(data.get("dur_diff", 10))
        self.lbl_dur_diff.configure(text=f"Время работы: {int(data.get('dur_diff', 10))} сек")

        self.slider_del_beam.set(data.get("del_beam", 0))
        self.lbl_del_beam.configure(text=f"Задержка старта: {int(data.get('del_beam', 0))} сек")
        self.slider_dur_beam.set(data.get("dur_beam", 10))
        self.lbl_dur_beam.configure(text=f"Время работы: {int(data.get('dur_beam', 10))} сек")

        self.slider_del_back.set(data.get("del_back", 0))
        self.lbl_del_back.configure(text=f"Задержка старта: {int(data.get('del_back', 0))} сек")
        self.slider_dur_back.set(data.get("dur_back", 10))
        self.lbl_dur_back.configure(text=f"Время работы: {int(data.get('dur_back', 10))} сек")

        self.slider_del_s1.set(data.get("del_s1", 0))
        self.lbl_del_s1.configure(text=f"Задержка старта: {int(data.get('del_s1', 0))} сек")
        self.slider_dur_s1.set(data.get("dur_s1", 10))
        self.lbl_dur_s1.configure(text=f"Время работы: {int(data.get('dur_s1', 10))} сек")

        self.slider_del_s2.set(data.get("del_s2", 0))
        self.lbl_del_s2.configure(text=f"Задержка старта: {int(data.get('del_s2', 0))} сек")
        self.slider_dur_s2.set(data.get("dur_s2", 10))
        self.lbl_dur_s2.configure(text=f"Время работы: {int(data.get('dur_s2', 10))} сек")

    def on_preset_select(self, preset_name):
        self.apply_preset_values(preset_name)

    def save_current_preset(self):
        preset_name = self.preset_combo.get()
        self.presets[preset_name] = {
            "del_diff": int(self.slider_del_diff.get()), "dur_diff": int(self.slider_dur_diff.get()),
            "del_beam": int(self.slider_del_beam.get()), "dur_beam": int(self.slider_dur_beam.get()),
            "del_back": int(self.slider_del_back.get()), "dur_back": int(self.slider_dur_back.get()),
            "del_s1": int(self.slider_del_s1.get()), "dur_s1": int(self.slider_dur_s1.get()),
            "del_s2": int(self.slider_del_s2.get()), "dur_s2": int(self.slider_dur_s2.get()),
        }
        self.save_presets_to_file()
        self.lbl_status.configure(text=f"Пресет '{preset_name}' сохранён!", text_color="green")

    def create_new_preset(self):
        dialog = ctk.CTkInputDialog(text="Введите название нового пресета:", title="Новый пресет")
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            new_name = new_name.strip()
            # Копируем текущие настройки с экрана в новый пресет
            self.presets[new_name] = {
                "del_diff": int(self.slider_del_diff.get()), "dur_diff": int(self.slider_dur_diff.get()),
                "del_beam": int(self.slider_del_beam.get()), "dur_beam": int(self.slider_dur_beam.get()),
                "del_back": int(self.slider_del_back.get()), "dur_back": int(self.slider_dur_back.get()),
                "del_s1": int(self.slider_del_s1.get()), "dur_s1": int(self.slider_dur_s1.get()),
                "del_s2": int(self.slider_del_s2.get()), "dur_s2": int(self.slider_dur_s2.get()),
            }
            self.save_presets_to_file()
            self.preset_combo.configure(values=list(self.presets.keys()))
            self.preset_combo.set(new_name)
            self.lbl_status.configure(text=f"Создан новый пресет '{new_name}'!", text_color="green")

    # --- Связь по COM-порту ---
    def refresh_com_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_combo.configure(values=ports)
            self.port_combo.set(ports[0])
        else:
            self.port_combo.configure(values=["Нет портов"])
            self.port_combo.set("Нет портов")

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.btn_connect.configure(text="Подключить", fg_color=["#3B8ED0", "#1F6AA5"])
            self.lbl_status.configure(text="Порт отключен", text_color="gray")
        else:
            port = self.port_combo.get()
            try:
                self.ser = serial.Serial(port, 115200, timeout=0.1)
                time.sleep(2)
                self.btn_connect.configure(text="Отключить", fg_color="green")
                self.lbl_status.configure(text=f"Подключено к {port}", text_color="green")
            except Exception as e:
                self.lbl_status.configure(text=f"Ошибка: {e}", text_color="red")

    def send_to_esp(self, diffuse=0, beam=0, backlight=0, servo1=0, servo2=0):
        if self.ser and self.ser.is_open:
            payload = {
                "diffuse": int(diffuse),
                "beam": int(beam),
                "backlight": int(backlight),
                "servo1": int(servo1),
                "servo2": int(servo2)
            }
            raw = json.dumps(payload) + "\n"
            self.ser.write(raw.encode('utf-8'))

    def send_manual_state(self):
        if not self.is_running:
            self.send_to_esp(
                diffuse=self.slider_diffuse.get(),
                beam=self.slider_beam.get(),
                backlight=self.slider_back.get(),
                servo1=self.slider_s1.get(),
                servo2=self.slider_s2.get()
            )

    # --- Управление автоматическим сценарием ---
    def start_scenario(self):
        if not self.ser or not self.ser.is_open:
            self.lbl_status.configure(text="Ошибка: Сначала подключите COM-порт!", text_color="red")
            return

        self.is_running = True
        self.is_paused = False
        self.elapsed_total = 0.0

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="⏸ Пауза", fg_color="orange")
        self.btn_stop.configure(state="normal")

        threading.Thread(target=self.run_scenario_thread, daemon=True).start()

    def toggle_pause(self):
        if not self.is_running:
            return

        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.configure(text="▶ Продолжить", fg_color="green")
            self.lbl_status.configure(text="Статус: ПАУЗА (Ожидание)", text_color="orange")
        else:
            self.btn_pause.configure(text="⏸ Пауза", fg_color="orange")

    def stop_scenario(self):
        self.is_running = False
        self.is_paused = False
        self.elapsed_total = 0.0

        # Сброс железа в Ноль
        self.send_to_esp(0, 0, 0, 0, 0)

        self.btn_start.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="⏸ Пауза", fg_color="orange")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="Статус: Принудительно остановлено", text_color="red")

    # --- Главный поток временной шкалы ---
    def run_scenario_thread(self):
        del_diff, dur_diff = int(self.slider_del_diff.get()), int(self.slider_dur_diff.get())
        del_beam, dur_beam = int(self.slider_del_beam.get()), int(self.slider_dur_beam.get())
        del_back, dur_back = int(self.slider_del_back.get()), int(self.slider_dur_back.get())
        del_s1, dur_s1 = int(self.slider_del_s1.get()), int(self.slider_dur_s1.get())
        del_s2, dur_s2 = int(self.slider_del_s2.get()), int(self.slider_dur_s2.get())

        max_duration = max(
            del_diff + dur_diff,
            del_beam + dur_beam,
            del_back + dur_back,
            del_s1 + dur_s1,
            del_s2 + dur_s2
        )

        while self.elapsed_total <= max_duration:
            if not self.is_running:
                return

            if self.is_paused:
                time.sleep(0.1)
                continue

            diff_val = 255 if (del_diff <= self.elapsed_total < del_diff + dur_diff) else 0
            beam_val = 255 if (del_beam <= self.elapsed_total < del_beam + dur_beam) else 0
            back_val = 255 if (del_back <= self.elapsed_total < del_back + dur_back) else 0
            s1_val = 90 if (del_s1 <= self.elapsed_total < del_s1 + dur_s1) else 0
            s2_val = 90 if (del_s2 <= self.elapsed_total < del_s2 + dur_s2) else 0

            self.send_to_esp(diff_val, beam_val, back_val, s1_val, s2_val)

            rem = int(max_duration - self.elapsed_total)
            self.lbl_status.configure(
                text=f"Тест идет: {int(self.elapsed_total)}с / {max_duration}с (Осталось {rem}с)",
                text_color="yellow"
            )

            time.sleep(0.1)
            self.elapsed_total += 0.1

        if self.is_running:
            self.send_to_esp(0, 0, 0, 0, 0)
            self.lbl_status.configure(text="Статус: Сценарий успешно завершён!", text_color="green")
            self.stop_scenario()

if __name__ == "__main__":
    app = StandApp()
    app.mainloop()
