# Simorgh 🦅

یک پروکسی SOCKS5 سبک و قابل اطمینان بر پایه Python با قابلیت TLS Fragmentation.

```
Client → Simorgh → Server
```

---

## ⚙️ ویژگی‌ها

- **SOCKS5 Proxy** — کاملاً مطابق RFC 1928
- **احراز هویت** — پشتیبانی از username/password (RFC 1929)
- **TLS Fragmentation** — تشخیص ClientHello و ارسال تکه‌تکه با تأخیر تنظیم‌پذیر
- **محدودیت اتصال** — جلوگیری از resource exhaustion
- **Timeout** — بستن خودکار اتصال‌های stale
- **Logging** — گزارش‌گیری کامل با پشتیبانی از فایل و چرخش خودکار
- **تست‌های یونیت** — پوشش کامل ماژول‌های اصلی
- **پیکربندی ساده** — یک فایل YAML با مستندات کامل

---

## 📋 پیش‌نیازها

- Python **3.10** یا بالاتر

```bash
python3 --version
```

---

## 📥 نصب

```bash
git clone https://github.com/yousofpayamber/Simorgh.git
cd Simorgh
pip install -r requirements.txt
```

---

## 🚀 اجرا (کامپیوتر)

```bash
python3 main.py
```

با مسیر config دلخواه:

```bash
python3 main.py --config /path/to/config.yaml
```

با override سطح لاگ:

```bash
python3 main.py --log-level DEBUG
```

---

## ⚙️ پیکربندی

فایل `config/config.yaml`:

```yaml
listen_host: "127.0.0.1"
listen_port: 1080
max_connections: 200
connection_timeout: 30

auth:
  enabled: false
  username: ""
  password: ""

fragment:
  enabled: true
  min_size: 10
  max_size: 40
  delay_min: 0.01
  delay_max: 0.05
  randomize_order: false

logging:
  level: "INFO"
```

---

## 🔐 فعال‌سازی احراز هویت

```yaml
auth:
  enabled: true
  username: "myuser"
  password: "mypassword"
```

---

## 🧪 اجرای تست‌ها

```bash
python3 -m pytest tests/ -v
```

---

## ساختار پروژه

```
Simorgh/
├── main.py
├── requirements.txt
├── config/
│   └── config.yaml
├── core/
│   ├── proxy.py
│   ├── socks5.py
│   ├── fragment.py
│   ├── config_validator.py
│   └── logger.py
├── scripts/
│   └── run.sh
└── tests/
    └── test_simorgh.py
```

---

## 📱 اتصال با اندروید

> برای آموزش کامل اجرا و اتصال با گوشی اندروید و ترموکس:
>
> **[👈 آموزش اتصال با اندروید](ANDROID.md)**

---

> ⚠️ این پروژه برای تست و پژوهش شبکه طراحی شده است.
