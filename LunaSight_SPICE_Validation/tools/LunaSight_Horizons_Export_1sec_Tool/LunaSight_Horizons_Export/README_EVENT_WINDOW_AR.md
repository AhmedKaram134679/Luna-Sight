# LunaSight — استخراج نافذة الحدث بدقة ثانية واحدة

## الهدف
استخراج استجابة JPL Horizons الخام وبيانات CSV للفترة **2026-11-01 07:40:00 إلى 07:41:00 UTC** بفاصل ثانية واحدة، للموقع القمري نفسه المستخدم في التصدير السابق.

## المتطلبات
- Python مثبت ويعمل عبر الأمر `py`.
- اتصال بالإنترنت.
- تثبيت `truststore` مرة واحدة، لأنه يستخدم مخزن شهادات Windows مع إبقاء التحقق من TLS مفعّلًا:
  ```powershell
  py -m pip install truststore
  ```

## التشغيل
ضع الملف في المجلد المطلوب ثم شغّله من PowerShell:

```powershell
py .\fetch_lunasight_event_window.py
```

يحفظ السكربت ملفي الاستجابة الخام `lunasight_event_raw_*.txt` والصفوف `lunasight_event_rows_*.csv` في المجلد نفسه.

## الإعدادات العلمية

**تصحيح مهم:** لا تستخدم `STEP_SIZE='1 s'`؛ فقد رفض Horizons وحدة `s` برسالة `Unknown units specification`. يستخدم الإصدار المصحح قيمة رقمية بلا وحدة (`STEP_SIZE='60'`) لطلب 60 فاصلًا ضمن نافذة مدتها 60 ثانية. هذا السلوك مستند إلى توثيق JPL Horizons، لكن يجب التأكد من عدد الصفوف وترويسة الاستجابة بعد التشغيل.
- Target: Earth (399)
- Center: user-defined geodetic site on Moon (301)
- East longitude: 200°
- Latitude: −88.45°
- Altitude: 0 km
- Time scale: UT/UTC output
- Quantities: apparent azimuth/elevation, range/range-rate, target angular diameter
- Apparent mode: AIRLESS
- Step: `STEP_SIZE=60` بلا وحدة؛ وفق توثيق Horizons، الخطوة الرقمية بلا وحدة هي الطريقة المدعومة لطلب فاصل أقل من دقيقة. على نافذة مدتها 60 ثانية، يُتوقع الحصول على 61 عينة شاملة الطرفين.

راجع ترويسة الاستجابة الخام لتأكيد الإعدادات الفعلية. لا تعني كثافة العينات أن الدقة الفيزيائية المطلقة تساوي ثانية واحدة، ولا يجوز افتراض تطابق النموذج مع إطار قمري آخر دون التوفيق بين الإطارات والتصحيحات.
