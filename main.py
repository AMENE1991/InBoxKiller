import tkinter as tk
from tkinter import messagebox
import os.path
import queue
import threading
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Области доступа
SCOPES = ['https://mail.google.com/']

# Создаем очередь для передачи данных между потоками
data_queue = queue.Queue()

def get_gmail_service():
    """Аутентификация и получение сервиса Gmail."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret_337833950710-1vilc8j9m0fb382d8ak2gllubgs0itfv.apps.googleusercontent.com.json',
                SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def list_unread_messages(service, user_id='me'):
    """Получает список непрочитанных сообщений из почтового ящика."""
    try:
        response = service.users().messages().list(userId=user_id, labelIds=['UNREAD']).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId=user_id, labelIds=['UNREAD'], pageToken=page_token).execute()
            messages.extend(response['messages'])
        return messages
    except HttpError as error:
        print(f'Произошла ошибка: {error}')
        return None

def delete_message(service, user_id, msg_id):
    """Удаляет сообщение с указанным ID."""
    try:
        result = service.users().messages().delete(userId=user_id, id=msg_id).execute()
        print(f"Сообщение с ID: {msg_id} успешно удалено. Результат: {result}")
    except Exception as error:
        print(f'Произошла ошибка при удалении сообщения: {error}')

def fetch_emails_async():
    def worker():
        try:
            service = get_gmail_service()
            messages = list_unread_messages(service)
            senders = set()
            if messages:
                for message in messages:
                    msg = service.users().messages().get(userId='me', id=message['id']).execute()
                    headers = msg['payload']['headers']
                    subject = next(header['value'] for header in headers if header['name'] == 'Subject')
                    sender = next(header['value'] for header in headers if header['name'] == 'From')
                    senders.add(sender)
                    data_queue.put((subject, sender))
                data_queue.put(("senders", list(senders)))
        except Exception as e:
            data_queue.put(("error", str(e)))

    threading.Thread(target=worker).start()
    root.after(100, process_queue)

def delete_emails_by_sender_async():
    sender_email = sender_var.get()
    if not sender_email:
        messagebox.showwarning("Предупреждение", "Пожалуйста, выберите отправителя из списка.")
        return

    def worker():
        try:
            service = get_gmail_service()
            messages = list_unread_messages(service)
            if messages:
                for message in messages:
                    msg = service.users().messages().get(userId='me', id=message['id']).execute()
                    headers = msg['payload']['headers']
                    sender = next(header['value'] for header in headers if header['name'] == 'From')
                    if sender_email in sender:
                        delete_message(service, 'me', message['id'])
                data_queue.put(f"Все письма от отправителя {sender_email} успешно удалены.")
        except Exception as e:
            data_queue.put(("error", str(e)))

    threading.Thread(target=worker).start()
    root.after(100, process_queue)

def process_queue():
    try:
        while True:
            item = data_queue.get_nowait()
            if isinstance(item, tuple) and item[0] == "error":
                root.after(0, messagebox.showerror, "Ошибка", item[1])
            elif isinstance(item, tuple) and item[0] == "senders":
                sender_var.set('')
                sender_menu['menu'].delete(0, 'end')
                for sender in item[1]:
                    sender_menu['menu'].add_command(label=sender, command=tk._setit(sender_var, sender))
                if item[1]:
                    sender_var.set(item[1][0])
            elif isinstance(item, tuple):
                subject, sender = item
                email_list.insert(tk.END, f"От: {sender} - Тема: {subject}")
            else:
                root.after(0, messagebox.showinfo, "Информация", item)
    except queue.Empty:
        root.after(100, process_queue)

# Создание основного окна приложения
root = tk.Tk()
root.title("InboxKiller App")

# Кнопка для получения писем
fetch_button = tk.Button(root, text="Получить непрочитанные письма", command=fetch_emails_async)
fetch_button.pack(pady=10)

# Кнопка для удаления писем от выбранного отправителя
delete_by_sender_button = tk.Button(root, text="Удалить письма от выбранного отправителя", command=delete_emails_by_sender_async)
delete_by_sender_button.pack(pady=10)

# Список для отображения писем
email_list = tk.Listbox(root, width=100, height=20)
email_list.pack(pady=10)

# Переменная для хранения выбранного отправителя
sender_var = tk.StringVar(root)

# Выпадающий список для выбора отправителя
sender_menu = tk.OptionMenu(root, sender_var, [])
sender_menu.pack(pady=10)

# Запуск основного цикла приложения
root.mainloop()
