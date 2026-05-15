# BEZOPAS_CHAT_3.0
Simple discord-style chat with E2EE encryption =)


# 🔐 BezopasniChat

**BezopasniChat** – безопасный мессенджер реального времени с **end‑to‑end шифрованием**.  
Совмещает интерфейс в стиле **Discord** и надёжность **Telegram**, но с полной конфиденциальностью: сервер никогда не видит ваши сообщения.

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

---

## ✨ Особенности

- 🔒 **End‑to‑end шифрование**  
  Все сообщения шифруются алгоритмом AES‑GCM на устройстве отправителя и расшифровываются только у получателя. Ключи передаются с помощью RSA‑OAEP.

- 💬 **Реальное время**  
  Мгновенная отправка и получение сообщений благодаря WebSocket (Socket.IO).

- 🌐 **Публичные каналы**  
  Встроенные текстовые каналы: 📝 Общий, 🎮 Игры, 🎵 Музыка, 😂 Мемы.

- 🔑 **Приватные чаты и группы**  
  Создавайте защищённые чаты с конкретными пользователями по их ID или создавайте группы с несколькими участниками.

- 👥 **Приглашение по ID**  
  Добавляйте пользователей в приватные чаты и группы через их уникальный цифровой идентификатор.

- 📌 **Современный интерфейс**  
  Тёмная тема, панель серверов, список онлайн‑пользователей, аватарки, звуки уведомлений.

- 🧹 **Управление сообщениями**  
  Удаление и редактирование своих сообщений, очистка истории чатов (для администраторов — в публичных каналах).

- 🛡️ **Администрирование**  
  Встроенная консоль администратора с возможностью бана/разбана, мута, кика и отправки системных сообщений.

---

## 🧰 Технологии

| Компонент       | Технология                        |
|-----------------|-----------------------------------|
| **Бэкенд**      | Python 3, Flask, Flask‑SocketIO  |
| **Криптография**| PyCryptoDome, Web Crypto API     |
| **Фронтенд**    | HTML5, CSS3, JavaScript (Vanilla)|
| **WebSocket**   | Socket.IO (threading mode)       |
| **База данных** | В памяти (словари Python)        |

---

## 🚀 Установка и запуск

1. **Склонируйте репозиторий**
   ```bash
   git clone https://github.com/Shavermushka/BEZOPAS_CHAT_3.0.git
   cd BEZOPAS_CHAT_3.0
   cd BEZOPAS_CHAT_END
   ```

2. **Создайте виртуальное окружение и активируйте его**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/Mac
   .venv\Scripts\activate      # Windows
   ```

3. **Установите зависимости**
   ```bash
   pip install -r requirements.txt
   ```

4. **Запустите сервер**
   ```bash
   python run.py
   ```

5. **Откройте браузер** и перейдите по адресу [http://127.0.0.1:5000](http://127.0.0.1:5000).

---

## 📸 Скриншоты

![](https://github.com/Shavermushka/BEZOPAS_CHAT_3.0/blob/main/Scrin1.png)

---

![](https://github.com/Shavermushka/BEZOPAS_CHAT_3.0/blob/main/Scrin2.png)

---

## 👥 Авторы

| Фамилия, Имя                      | GitHub                                     | Роль |
|-----------------------------------|-------------------------------------------------------|------|
| **Шинкаренко Егор Вадимович**     | [Shavermushka](https://github.com/Shavermushka)      | Backend, тестирование, криптография, архитектура |
| **Сыпачев Дмитрий Константинович** | [dmitriysypachev6-coder](https://github.com/dmitriysypachev6-coder)                                                    | Backend, тестирование |
| **Иванченко Кирилл Александрович** | [kerikkkk](https://github.com/kerikkkk)                                                     | Frontend, UI/UX дизайн, криптография |

---

## 📜 Лицензия и атрибуция

Этот проект распространяется под лицензией **Creative Commons Attribution‑NonCommercial 4.0 International (CC BY‑NC 4.0)**.  
Полный текст лицензии доступен в файле [LICENSE](LICENSE).

Пример атрибуции, которую необходимо разместить при использовании кода:


> «Часть кода основана на проекте BezopasniChat, созданном [Shavermushka](https://github.com/Shavermushka)., [dmitriysypachev6-coder](https://github.com/dmitriysypachev6-coder)., [kerikkkk](https://github.com/kerikkkk).»


Это гарантирует, что ваш вклад останется бесплатным и открытым навсегда.

📂 Структура проекта 
```
BEZOPAS_CHAT_3.0/
│
├──BEZOPAS_CHAT_END/
  ├── run.py
  ├── config.py
  ├── requirements.txt
  ├── LICENSE
  ├── bezopasnichat/
  │   ├── __init__.py
  │   ├── crypto_utils.py
  │   └── events.py
  ├── static/
  │   ├── style.css
  │   └── client.js
  └── templates/
      └── index.html
```

## 🤝 Вклад

Pull request’ы приветствуются! Однако помните, что любые изменения также остаются под лицензией CC BY‑NC 4.0, и вы должны соблюдать её условия.

## 🌟 Благодарности
- [Flask](https://flask.palletsprojects.com/)

- [Socket.IO](https://socket.io/)

- [PyCryptoDome](https://www.pycryptodome.org/)

Огромное спасибо сообществу open‑source за вдохновение.

© 2026 Шинкаренко Е.В., Сыпачев Д.К., Иванченко К.А. Все права, не предоставленные явно лицензией, сохранены.
