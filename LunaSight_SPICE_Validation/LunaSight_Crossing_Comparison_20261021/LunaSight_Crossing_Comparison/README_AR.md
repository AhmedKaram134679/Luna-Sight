# LunaSight — إعادة فحص حدث حافة الأرض

## الملفات
- `validate_earth_limb.py`: نسخة SPICE المعدلة بنافذة `2026-11-02 14:12:30` إلى `14:16:00 UTC`، عينات كل ثانية، إحاطة جذر ثم تنصيف حتى 0.01 ثانية.
- `fetch_horizons_reference.py`: يطلب جدول Horizons للفترة نفسها وموقع الراصد القمري نفسه، ويحفظ الاستجابة الخام والجدول وCSV.

## التشغيل على Windows
من داخل مجلد المشروع الذي يحتوي على البيئة `.venv`:

```powershell
.\.venv\Scripts\python.exe .\validate_earth_limb.py
.\.venv\Scripts\python.exe .\fetch_horizons_reference.py
```

إذا كان `fetch_horizons_reference.py` في مجلد مختلف، شغّله بمساره الكامل. يعتمد سكربت Horizons على مكتبات Python القياسية فقط.

## ما الذي نقارنه؟
- SPICE: `upper_limb_elevation_deg`، وهو ناتج نموذج الحافة الإهليلجية في السكربت.
- Horizons: ارتفاع مركز الأرض، السمت، القطر الزاوي، المدى وزمن الضوء.

**تحذير علمي:** جدول Horizons لا يخرج مباشرةً ارتفاع الحافة العليا المحسوبة بنفس خوارزمية الإهليلج. لذلك يجب أولًا مطابقة مركز الأرض والقطر/الشكل وتصحيحات الموضع الظاهري، ثم اشتقاق تعريف حافة متسق. لا تُعلن النتيجة VALIDATED لمجرد تقارب الوقت أو نجاح طلب API.

توثيق Horizons API الرسمي:
https://ssd-api.jpl.nasa.gov/doc/horizons.html
