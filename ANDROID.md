# 📱 آموزش اتصال با اندروید

این راهنما توضیح میده چطور پروژه Simorgh رو روی گوشی اندروید با ترموکس اجرا کنی و بهش وصل بشی.

---

## ۱. نصب ترموکس

ترموکس رو از **F-Droid** دانلود کن (نسخه گوگل پلی قدیمیه و کار نمیکنه):

🔗 https://f-droid.org/en/packages/com.termux

---

## ۲. آپدیت و نصب پیش‌نیازها

ترموکس رو باز کن و این دستورا رو بزن:

```bash
pkg update && pkg upgrade -y
pkg install git python -y
```

---

## ۳. دانلود پروژه

```bash
git clone https://github.com/yousofpayamber/Simorgh.git
cd Simorgh
```

---

## ۴. نصب کتابخانه‌ها

```bash
pip install -r requirements.txt
```

---

## ۵. اجرای پروکسی

```bash
python main.py
```

اگه همه چیز درست باشه این پیام رو میبینی:

```
Simorgh listening on 127.0.0.1:1080
```

---

## ۶. اجرا در پس‌زمینه (اختیاری)

اگه نمی‌خوای ترموکس باز بمونه:

```bash
nohup python main.py > simorgh.log 2>&1 &
```

برای متوقف کردن:

```bash
pkill -f main.py
```

---

## ۷. اتصال گوشی به پروکسی

### روش ۱ — SocksDroid (پیشنهادی ✅)

1. برنامه **SocksDroid** رو از گوگل پلی نصب کن
2. باز کن و تنظیمات زیر رو وارد کن:
   - **Server:** `127.0.0.1`
   - **Port:** `1080`
   - **Protocol:** SOCKS5
   - **Username / Password:** خالی بذار (مگه auth رو فعال کرده باشی)
3. دکمه اتصال رو بزن
4. اگه درخواست VPN permission داد قبول کن

### روش ۲ — V2rayNG

1. **V2rayNG** رو از گوگل پلی نصب کن
2. روی **+** بزن → **Add SOCKS**
3. وارد کن:
   - **Address:** `127.0.0.1`
   - **Port:** `1080`
4. ذخیره کن و connect بزن

---

## ۸. تست اتصال

بعد از اتصال، توی مرورگر گوشیت برو به:

```
https://ip.me
```

اگه آی‌پی تغییر کرده بود، پروکسی داره کار میکنه ✅

---

## ❗ رفع مشکل

**خطای `pip: command not found`:**
```bash
pkg install python -y
```

**خطای `ModuleNotFoundError`:**
```bash
pip install -r requirements.txt
```

**پروکسی وصل نمیشه:**
- مطمئن شو ترموکس باز و پروکسی داره اجرا میشه
- port رو چک کن: `1080` باشه
- اگه auth فعاله، username/password رو توی SocksDroid وارد کن

---

> [🔙 برگشت به README اصلی](README.md)
