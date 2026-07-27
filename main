import tkinter as tk
import customtkinter as ctk
import serial
import serial.tools.list_ports
import json
import threading
import time

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class StandApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FPV Stand Controller")
        self.geometry("900x700")

        self.ser = None

        # --- Состояние сценария ---
        self.is_running = False
        self.is_paused = False
        self.current_step = 0
        self.elapsed_in_step = 0.0

        self.setup_ui()
        self.refresh_com_ports()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ==========================================
        # ЛЕВАЯ ПАНЕЛЬ: Связь и Ручное Управление
        # ==========================================
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

        ctk.CTkLabel(left_frame, text="🎛️ Ручное Управление Свет / Сервы", font=("Arial", 16, "bold")).pack(pady=(15, 5))

        # Ползунки DMX Света
        self.slider_diffuse = self.create_slider(left_frame, "Рассеянный свет (Diff)", 0, 255)
        self.slider_beam = self.create_slider(left_frame, "Направленный луч (Beam)", 0, 255)
        self.slider_back = self.create_slider(left_frame, "Контровой свет (Back)", 0, 255)

        # Ползунки Сервоприводов
        self.slider_s1 = self.create_slider(left_frame, "Сервопривод 1 (°)", 0, 180)
        self.slider_s2 = self.create_slider(left_frame, "Сервопривод 2 (°)", 0, 180)

        # ==========================================
        # ПРАВАЯ ПАНЕЛЬ: Автоматический Сценарий
        # ==========================================
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(right_frame, text="⏱️ Настройка Авто-Сценария", font=("Arial", 16, "bold")).pack(pady=5)

        # Шаг 1
        self.time_diffuse = self.create_time_input(right_frame, "Время Рассеянного света (сек):", default=10)
        # Шаг 2
        self.time_beam = self.create_time_input(right_frame, "Время Направленного луча (сек):", default=10)
        # Шаг 3
        self.time_back = self.create_time_input(right_frame, "Время Контрового света (сек):", default=10)

        # Задержка сервоприводов
        self.time_servo_delay = self.create_time_input(right_frame, "Задержка старта Сервоприводов (сек):", default=2, min_val=0, max_val=180)

        # Статус сценария
        self.lbl_status = ctk.CTkLabel(right_frame, text="Статус: Готов к запуску", font=("Arial", 14), text_color="gray")
        self.lbl_status.pack(pady=15)

        # Кнопки управления сценарием
        btn_box = ctk.CTkFrame(right_frame)
        btn_box.pack(fill="x", padx=10, pady=10)

        self.btn_start = ctk.CTkButton(btn_box, text="▶ Старт", fg_color="green", hover_color="darkgreen", command=self.start_scenario)
        self.btn_start.pack(side="left", padx=5, expand=True, fill="x")

        self.btn_pause = ctk.CTkButton(btn_box, text="⏸ Пауза", fg_color="orange", hover_color="darkorange", command=self.toggle_pause, state="disabled")
        self.btn_pause.pack(side="left", padx=5, expand=True, fill="x")

        self.btn_stop = ctk.CTkButton(btn_box, text="⏹ Стоп", fg_color="red", hover_color="darkred", command=self.stop_scenario, state="disabled")
        self.btn_stop.pack(side="left", padx=5, expand=True, fill="x")

    # --- Вспомогательные конструкторы UI ---
    def create_slider(self, parent, label_text, min_v, max_v):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=10, pady=5)
        
        lbl = ctk.CTkLabel(frame, text=f"{label_text}: 0")
        lbl.pack(anchor="w", padx=5)

        slider = ctk.CTkSlider(frame, from_=min_v, to=max_v, number_of_steps=max_v-min_v)
        slider.set(0)
        slider.configure(command=lambda v: [lbl.configure(text=f"{label_text}: {int(v)}"), self.send_manual_state()])
        slider.pack(fill="x", padx=5, pady=2)
        return slider

    def create_time_input(self, parent, label_text, default=10, min_val=10, max_val=180):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=10, pady=5)

        lbl = ctk.CTkLabel(frame, text=label_text)
        lbl.pack(side="left", padx=5)

        entry = ctk.CTkEntry(frame, width=60)
        entry.insert(0, str(default))
        entry.pack(side="right", padx=5)
        return entry

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
                time.sleep(2)  # Пауза на авторестарт ESP32
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
        self.current_step = 1
        self.elapsed_in_step = 0.0

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
        self.current_step = 0
        self.elapsed_in_step = 0.0

        # Сброс железа в Ноль
        self.send_to_esp(0, 0, 0, 0, 0)

        self.btn_start.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="⏸ Пауза", fg_color="orange")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="Статус: Принудительно остановлено", text_color="red")

    # --- Главный поток цикла сценария ---
    def run_scenario_thread(self):
        try:
            t_diff = max(10, min(180, int(self.time_diffuse.get())))
            t_beam = max(10, min(180, int(self.time_beam.get())))
            t_back = max(10, min(180, int(self.time_back.get())))
            t_servo_delay = max(0, min(180, int(self.time_servo_delay.get())))
        except ValueError:
            self.lbl_status.configure(text="Ошибка: Некорректное время!", text_color="red")
            self.stop_scenario()
            return

        steps = [
            {"name": "Рассеянный свет", "diff": 255, "beam": 0, "back": 0, "duration": t_diff},
            {"name": "Направленный луч", "diff": 0, "beam": 255, "back": 0, "duration": t_beam},
            {"name": "Контровой свет", "diff": 0, "beam": 0, "back": 255, "duration": t_back},
        ]

        for step_idx in range(self.current_step - 1, len(steps)):
            if not self.is_running:
                break

            self.current_step = step_idx + 1
            step = steps[step_idx]

            while self.elapsed_in_step < step["duration"]:
                if not self.is_running:
                    return

                if self.is_paused:
                    time.sleep(0.1)
                    continue

                # Расчет работы Сервоприводов с задержкой
                s1_val = 90 if self.elapsed_in_step >= t_servo_delay else 0
                s2_val = 90 if self.elapsed_in_step >= t_servo_delay else 0

                # Отправка на ESP32
                self.send_to_esp(step["diff"], step["beam"], step["back"], s1_val, s2_val)

                # Обновление текста статуса
                rem_time = int(step["duration"] - self.elapsed_in_step)
                self.lbl_status.configure(
                    text=f"Шаг {self.current_step}/3: {step['name']} | Осталось: {rem_time}с",
                    text_color="yellow"
                )

                time.sleep(0.1)
                self.elapsed_in_step += 0.1

            # Сброс таймера шага при переходе к следующему
            self.elapsed_in_step = 0.0

        if self.is_running:
            self.send_to_esp(0, 0, 0, 0, 0)
            self.lbl_status.configure(text="Статус: Сценарий успешно завершён!", text_color="green")
            self.stop_scenario()

if __name__ == "__main__":
    app = StandApp()
    app.mainloop()
