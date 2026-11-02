# Madara Key Verification API + Telegram Bot

مشروع Python للتحقق من مفاتيح التطبيق وإدارة المفاتيح من Telegram.

## المتطلبات
- Python 3.10 أو أحدث
- Bot Token من BotFather
- Telegram ID ديال الأدمن (مضبوط افتراضياً على `8404634986`)

## التشغيل محلياً
1. فك الضغط على ZIP.
2. ثبت المكتبات:
   ```bash
   pip install -r requirements.txt
   ```
3. نسخ `.env.example` إلى `.env` وعمر `BOT_TOKEN`.
4. شغل التطبيق:
   ```bash
   python main.py
   ```

يتم تحميل ملف `.env` تلقائياً. ويمكن كذلك ضبط المتغيرات يدوياً. على Windows PowerShell:
```powershell
$env:BOT_TOKEN="YOUR_BOT_TOKEN"
$env:ADMIN_ID="8404634986"
python main.py
```
على Linux/macOS:
```bash
export BOT_TOKEN="YOUR_BOT_TOKEN"
export ADMIN_ID="8404634986"
python main.py
```

## أوامر Telegram
- `/Key AKIRA-BOT-JSJSIS 7 30` — إنشاء KEY يسمح بـ7 أجهزة لمدة 30 يوماً.
- `/DelKey AKIRA-BOT-JSJSIS` — حذف KEY وجميع تسجيلات أجهزته.
- `/Keys` — عرض آخر 50 مفتاحاً.
- `/Check AKIRA-BOT-JSJSIS` — عرض الحالة وعدد الأجهزة.
- `/Disable AKIRA-BOT-JSJSIS` — توقيف KEY.
- `/Enable AKIRA-BOT-JSJSIS` — إعادة تفعيل KEY.

كل الأوامر الإدارية محمية برقم Telegram ID المحدد في `ADMIN_ID`.

## API متوافق مع MadaraCheck
`POST /api/verify`

Header:
`Content-Type: application/json`

Body:
```json
{
  "key": "AKIRA-BOT-JSJSIS",
  "device": "ANDROID_ID"
}
```

نجاح:
```json
{"ok": true, "msg": "Key verified successfully"}
```

فشل:
```json
{"ok": false, "msg": "Invalid key"}
```

## ملاحظات مهمة
- قاعدة SQLite محلية. للاستضافة على Render، استعمل Persistent Disk واربط `DB_PATH` بمسار داخل القرص؛ وإلا قد تضيع قاعدة البيانات عند إعادة النشر.
- لا ترفع `.env` أو Bot Token إلى GitHub ولا تشاركه مع أي شخص.
- شغّل نسخة واحدة من البوت فقط باستعمال polling.
- `ANDROID_ID` وسيلة ربط بسيطة وليس إثباتاً قوياً لهوية الجهاز؛ يمكن أن يتغير أو يُزوّر في بعض البيئات.
- لا تضع أسرار البوت داخل APK.
