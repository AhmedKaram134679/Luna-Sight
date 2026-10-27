# LunaSight — مقارنة SPICE/Horizons الموحدة (مرحلة التشخيص)

هذه الحزمة تضيف أداة تشخيص قابلة للتشغيل على Windows. لا تدّعي أن التوقيت أصبح معتمدًا؛ هدفها قياس الفرق بين النماذج في اللحظات نفسها، وفصل:
1. مركز الأرض: هندسي، LT، وLT+S.
2. الحافة العلوية للأرض: إهليلج الأرض مع زمن ضوء مستقل لكل نقطة من نقاط الحافة، ثم تطبيق تصحيح الانحراف النجمي على اتجاه كل نقطة.
3. الفروق الزاوية في مركز الأرض والحافة.

## مهم قبل التشغيل
- احتفظ بالسكربت الأصلي والنتائج السابقة؛ هذه الأداة تشخيص إضافي ولا تستبدل ملفات المصدر.
- تستخدم بيانات Horizons المحفوظة في هذا الملف كمرجع مركز/قطر زاوي. القيم المدخلة هي من الجدول الذي زوّد به المستخدم، وليست إعادة استعلام حي.
- تقدير الحافة من `center elevation + angular radius` ليس مساويًا بالضرورة لحافة إهليلجية محسوبة هندسيًا.
- SPICE `LT+S` لمركز الأرض يستخدم موضع/سرعة الراصد القمري المحسوبة عدديًا. لا يمكن وصف التطابق بأنه كامل قبل التأكد من خيارات Horizons الدقيقة ونموذج الشكل والـ PCK والـ frame.
- لا توجد هنا نتيجة تشغيل جديدة؛ يجب تشغيل الأداة محليًا مع kernels المطلوبة. لا تستخدم أي توقيت ناتج كقيمة مرجعية نهائية قبل مراجعة CSV.

## المتطلبات
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install spiceypy numpy scipy
```

## التشغيل
ضع `compare_horizons_spice.py` في مجلد عمل منفصل، ثم:
```powershell
.\.venv\Scripts\python.exe .\compare_horizons_spice.py
```
سيحمّل kernels المطلوبة إلى `kernels/` عند الحاجة، ويكتب:
- `results/matched_comparison.csv`
- `results/matched_comparison_summary.txt`

## قراءة النتائج
- `center_delta_arcsec_*`: الفرق بين ارتفاع مركز SPICE وارتفاع مركز Horizons.
- `horizons_upper_limb_estimate_deg`: تقدير الحافة من مركز Horizons والقطر الزاوي.
- `spice_limb_*`: ارتفاع أعلى نقطة على محيط الأرض المحسوب بواسطة SPICE.
- `limb_delta_arcsec_vs_horizons_estimate_*`: الفرق بين الحافة الهندسية المصححة في SPICE والتقدير البسيط من Horizons.
- `lt_plus_s` يضيف stellar aberration؛ `lt` لا يضيفه.
