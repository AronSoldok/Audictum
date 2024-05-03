import os
import time
import logging
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, filedialog
from tkinter import ttk
import psutil
import threading
from queue import Queue
from logging.handlers import RotatingFileHandler
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Путь к файлу журнала событий
LOG_FILE = 'system_audit.log'  # Файл будет создан в текущей директории

# Определение констант для ротации журнала событий
MAX_LOG_SIZE = 1024 * 1024  # 1 MB
BACKUP_COUNT = 3

# Функция для отслеживания событий запуска процессов
def monitor_processes(queue):
    while True:
        processes = psutil.process_iter(['pid', 'name', 'username'])
        process_list = "\n".join([f"PID: {p.info['pid']}, Название: {p.info['name']}, Пользователь: {p.info['username']}" for p in processes])
        queue.put(f"Процессы:\n{process_list}")
        logger.info(f"Процессы:\n{process_list}")
        time.sleep(60)

# Функция для отслеживания событий изменения файлов
def monitor_file_changes(queue, path):
    while True:
        try:
            files = os.listdir(path)
            files_info = "\n".join([f"Название: {file}, Размер: {os.path.getsize(os.path.join(path, file))} байт" for file in files])
            queue.put(f"Изменения файлов в {path}:\n{files_info}")
            logger.info(f"Изменения файлов в {path}:\n{files_info}")
        except Exception as e:
            queue.put(f"Ошибка при получении списка файлов: {e}")
            logger.error(f"Ошибка при получении списка файлов: {e}")
        time.sleep(300)  # Периодичность мониторинга

# Функция для обновления журнала событий в GUI
def update_log_text(queue, log_text):
    while True:
        if not queue.empty():
            log_text.insert(tk.END, queue.get() + "\n")
            log_text.see(tk.END)
        time.sleep(1)

# Функция для отправки файла логов по почте
def send_email_notification(sender_email, password, receiver_email, subject, message, attachment_path=None):
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    msg.attach(MIMEText(message, "plain"))

    if attachment_path:
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
        part["Content-Disposition"] = f"attachment; filename={os.path.basename(attachment_path)}"
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.mail.ru", 465) as server:
            server.login(sender_email, password)
            server.send_message(msg)
    except Exception as e:
        print(f"Не удалось отправить электронное письмо: {e}")

# Класс окна настройки почты
class EmailWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Настройка почты")

        self.sender_email_label = ttk.Label(self, text="Email отправителя:")
        self.sender_email_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.sender_email_entry = ttk.Entry(self)
        self.sender_email_entry.grid(row=0, column=1, padx=5, pady=5)

        self.sender_password_label = ttk.Label(self, text="Пароль отправителя:")
        self.sender_password_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.sender_password_entry = ttk.Entry(self, show="*")
        self.sender_password_entry.grid(row=1, column=1, padx=5, pady=5)

        self.recipient_email_label = ttk.Label(self, text="Email получателя:")
        self.recipient_email_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.recipient_email_entry = ttk.Entry(self)
        self.recipient_email_entry.grid(row=2, column=1, padx=5, pady=5)

        self.send_button = ttk.Button(self, text="Отправить", command=self.send_email)
        self.send_button.grid(row=3, columnspan=2, padx=5, pady=5)

    def send_email(self):
        sender_email = self.sender_email_entry.get()
        sender_password = self.sender_password_entry.get()
        recipient_email = self.recipient_email_entry.get()

        if sender_email and sender_password and recipient_email:
            try:
                send_email_notification(sender_email, sender_password, recipient_email, "Аудит системы - Журнал событий", "Вложенный файл с журналом событий.", LOG_FILE)
                messagebox.showinfo("Успех", "Электронное письмо успешно отправлено!")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
        else:
            messagebox.showerror("Ошибка", "Пожалуйста, заполните все поля.")

# Функция для выбора каталога для мониторинга
def choose_directory():
    directory = filedialog.askdirectory()
    return directory

# Настройка логгера
logger = logging.getLogger()
handler = RotatingFileHandler(LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Основная функция программы
def main():
    # Создание или очистка файла журнала
    open(LOG_FILE, 'w').close()

    # Создание очереди для обмена данными между потоками
    queue = Queue()

    # Запуск потоков мониторинга
    process_thread = threading.Thread(target=monitor_processes, args=(queue,))
    file_thread = threading.Thread(target=monitor_file_changes, args=(queue, '/путь/к/монитору'))
    process_thread.start()
    file_thread.start()

    # Создание графического интерфейса
    create_gui(queue)

# Создание графического интерфейса
def create_gui(queue):
    root = tk.Tk()
    root.title("Инструмент аудита системы")
    root.configure(bg='#171717')  # Установка цвета фона

    # Создание текстового поля для вывода журнала событий
    log_text = scrolledtext.ScrolledText(root, width=100, height=30, bg='#121212', fg='#FFFFFF', font=('Arial', 10))
    log_text.pack(padx=10, pady=10)

    # Функция для обновления текстового поля с журналом событий
    def update_log_text():
        while True:
            if not queue.empty():
                log_text.insert(tk.END, queue.get() + "\n")
                log_text.see(tk.END)
            time.sleep(1)
    # Запуск функции обновления текстового поля
    update_log_thread = threading.Thread(target=update_log_text)
    update_log_thread.start()

    # Кнопка для выбора каталога мониторинга
    choose_button = ttk.Button(root, text="Выбрать каталог мониторинга", command=choose_directory)
    choose_button.pack(pady=10)

    # Кнопка для отправки лог-файла по почте
    email_button = ttk.Button(root, text="Настройка почты", command=lambda: EmailWindow(root))
    email_button.pack(pady=5)

    # Запуск приложения
    root.mainloop()

if __name__ == "__main__":
    main()  # Запуск основной программы в фоновом режиме
