# Orchestrator for Large-Scale Subprogram Management

هذا المشروع يوفّر برنامجًا رئيسيًا لإدارة وتشغيل عددٍ كبير من البرامج الفرعية (حتى 1078 برنامجًا أو أكثر) مع تخزين التعريفات والنتائج في قاعدة بيانات SQLite. يهدف النظام إلى تسهيل ربط قنوات الإدخال والإخراج، تسجيل الأهمية وطبيعة العمل لكل برنامج فرعي، وتنفيذ الأكواد المخصّصة بشكل آمن وبسيط.

## المزايا الرئيسية
- **تخزين مركزي** لتعريفات البرامج الفرعية (المعرف، الاسم، الأهمية، قنوات الإدخال/الإخراج، مسار الكود).
- **تشغيل ديناميكي** للكود عبر ملفات بايثون أو كودٍ مكتوب مباشرةً في سطر الأوامر مع تسجيل النتائج.
- **دعم التسجيل بالجملة** عبر ملفات JSONL لاستيعاب مئات أو آلاف البرامج الفرعية دفعة واحدة.
- **سجل تنفيذ** يدوّن حالات النجاح والفشل مع المخرجات في قاعدة البيانات.

## المتطلبات
- Python 3.10 أو أحدث.
- لا توجد تبعيات خارجية؛ يعتمد على مكتبات بايثون القياسية فقط.

## البدء السريع
1. **تهيئة قاعدة البيانات**
   ```bash
   python -m app.cli init-db --db data/registry.db
   ```

2. **تسجيل برنامج فرعي** (مع ربط قنوات الإدخال والإخراج ومسار الكود الاختياري)
   ```bash
   python -m app.cli register payroll-001 "Payroll batch" \
     --description "معالجة رواتب الربع الأول" \
     --importance 10 \
     --input-channel kafka:payroll.in \
     --output-channel kafka:payroll.out \
     --code-path subprograms/payroll.py
   ```

3. **تنفيذ برنامج مسجّل** وتمرير بيانات إدخال كـ JSON
   ```bash
   python -m app.cli run payroll-001 '{"batch": 12, "quarter": "Q1"}'
   ```

4. **تشغيل كود مخصّص (Inline) بدون ملف**
   ```bash
   python -m app.cli run-inline adhoc-123 '{"value": 5}' """
   def run(payload):
       return {"double": payload["value"] * 2}
   """
   ```

5. **تسجيل مجموعة كبيرة من البرامج** من ملف JSONL (سطر لكل برنامج)
   ```bash
   python -m app.cli bulk-register data/programs.jsonl
   ```

6. **عرض جميع البرامج المسجّلة مرتّبة بالأهمية ثم الاسم**
   ```bash
   python -m app.cli list
   ```

7. **عرض سجلّ التنفيذ لأحدث التشغيلات** (يمكن التصفية حسب برنامج محدد)
   ```bash
   python -m app.cli runs --limit 30 --program-id payroll-001
   ```

## كيف تشغّل وتعاين الكود بسرعة؟
يمكنك تجربة النظام محليًا بخطوات محدودة بدون أي تبعيات خارجية:

1. **تهيئة قاعدة البيانات**
   ```bash
   python -m app.cli init-db --db data/registry.db
   ```

2. **تسجيل برنامج تجريبي جاهز** (موجود في `app/samples/echo.py`)
   ```bash
   python -m app.cli register demo-echo "Echo demo" \
     --description "إرجاع النص المستلم مع عدد مرات التكرار" \
     --importance 5 \
     --input-channel demo:in \
     --output-channel demo:out \
     --code-path app/samples/echo.py
   ```

3. **تشغيل البرنامج التجريبي وتمرير حمولة إدخال**
   ```bash
   python -m app.cli run demo-echo '{"text": "hello", "count": 2}'
   ```
   سيطبع الإخراج الناتج من الدالة `run` ويُسجّل أيضًا في جدول `runs`.

4. **معاينة سجل التشغيل للبرنامج نفسه**
   ```bash
   python -m app.cli runs --program-id demo-echo --limit 5
   ```

5. **تشغيل كودٍ مخصّص سريع بدون تسجيل**
   ```bash
   python -m app.cli run-inline adhoc-echo '{"text": "inline"}' """
   def run(payload):
       return {"echo": payload.get("text", ""), "note": "from inline"}
   """
   ```
   يفيد هذا الأمر إذا أردت اختبار منطق جديد دون إنشاء ملف بايثون منفصل. يقوم
   الأمر بإنشاء إدخال تلقائيًا للبرنامج (إن لم يكن موجودًا) حتى تُسجَّل
   نتيجة التشغيل في جدول `runs` بلا أخطاء قيود مرجعية.

6. **تشغيل ومعاينة النظام في خطوة واحدة (أمر تجريبي جاهز)**
   ```bash
   python -m app.cli demo --text "hello preview" --count 3
   ```
   هذا الأمر يقوم بتهيئة قاعدة البيانات (إن لم تكن جاهزة)، وتسجيل البرنامج
   التجريبي `demo-echo`، ثم تنفيذه فورًا لإظهار الإخراج. بعد ذلك يمكنك عرض
   السجل بالأمر:
   ```bash
   python -m app.cli runs --program-id demo-echo
   ```

### تشغيل مباشر بأقل أوامر ممكنة
- **أبسط تجربة فورية**: نفّذ فقط الأمر التالي وسيظهر الإخراج على الشاشة:
  ```bash
  python -m app.cli demo --text "مرحبا" --count 1
  ```
  سيطبع نتيجة الدالة `run` من العينة المدمجة، ثم يعرض لك أمرًا جاهزًا لاستعراض السجل.

- **تبديل الحمولة بسرعة**: غيّر النص أو عدد التكرار بدون أي إعداد إضافي:
  ```bash
  python -m app.cli demo --text "رسالة اختبار" --count 5
  ```

- **معاينة الكود نفسه**: ملف العينة موجود في `app/samples/echo.py` ويمكنك تعديل الدالة `run`
  ثم إعادة تشغيل أمر `demo` لمشاهدة الأثر فورًا.
- **عرض الكود بالكامل على الشاشة مع ترقيم الأسطر**: اطبع الملف الموحّد أو أي ملف كود
  آخر مباشرةً:
  ```bash
  python -m app.cli preview-code --file app/monolith.py --start 1 --end 120
  # أو باستخدام الملف الموحّد نفسه دون تحديد المسار (سيُختار تلقائيًا):
  python -m app.monolith preview-code --start 1 --end 80
  ```
  سيظهر الكود في الشاشة بترقيم أسطر واضح لنسخه أو مراجعته سريعًا.

### نسخة ملف واحد جاهزة للنسخ
إن كنت تريد كل شيء في ملف واحد لنسخه أو تشغيله مباشرةً، استخدم `app/monolith.py`:

- **تهيئة وتشغيل مباشر**:
  ```bash
  python -m app.monolith demo --text "نسخة موحدة" --count 2
  ```
  سيقوم الملف الموحّد بتهيئة قاعدة البيانات، تسجيل عينة `demo-echo` داخليًا (Inline)، ثم تشغيلها وتسجيل النتيجة.

- **تنفيذ نفس أوامر السطر السابقة** متاحة بصيغة ملفٍ واحد:
  ```bash
  python -m app.monolith init-db --db data/registry.db
  python -m app.monolith register sample-1 "Sample name" --importance 3
  python -m app.monolith run-inline adhoc "{\"value\": 2}" """
  def run(payload):
      return {"double": payload["value"] * 2}
  """
  ```
  جميع الأوامر (`register`، `bulk-register`، `list`، `runs`، `run`، `run-inline`، `demo`) متاحة كما هي ولكن داخل ملف واحد لمن يفضّل نسخة يمكن لصقها وتشغيلها فورًا.

## تنسيق ملف JSONL للتسجيل بالجملة
لكل سطر JSON يمثل برنامجًا فرعيًا:
```json
{"program_id": "analytics-042", "name": "Analytics job", "importance": 7, "input_channel": "queue:analytics.in", "output_channel": "queue:analytics.out", "code_path": "subprograms/analytics.py"}
```
يمكنك إضافة حقول `description` أو إغفال `code_path` إذا كان التنفيذ سيكون عبر كودٍ مخصّص أثناء التشغيل.

## ملاحظات حول الأمن وتشغيل الكود
- يتوقع النظام وجود دالة باسم `run(payload: dict)` داخل كل ملف كود أو داخل الكود المخصّص.
- تشغيل الكود يتم عبر `exec`/`importlib`، لذا يُنصح بمراجعة الأكواد والتحكم في صلاحيات البيئة قبل التشغيل في بيئات حساسة.
- يتم تسجيل حالة التنفيذ (نجاح/فشل) والمخرجات كسلسلة JSON في جدول `runs` داخل قاعدة البيانات.

## هيكل المجلدات
- `app/models.py`: تعريف هيكل البرنامج الفرعي.
- `app/datastore.py`: إدارة قاعدة البيانات وتسجيل النتائج.
- `app/registry.py`: واجهة التسجيل والاستعلام عن البرامج.
- `app/executor.py`: تحميل وتشغيل الأكواد وتسجيل النتائج.
- `app/cli.py`: واجهة سطر الأوامر لتشغيل المهام السابقة.

## أفكار للتوسع
- ربط قنوات الإدخال/الإخراج الفعلية (Kafka، RabbitMQ، REST) بدلًا من الحقول النصية فقط.
- إضافة طبقة صلاحيات حسب أهمية البرنامج وطبيعة بياناته.
- إنشاء لوحة معلومات Dashboard لعرض حالة 1078 برنامجًا فرعيًا والنتائج المخزَّنة في قاعدة البيانات.
