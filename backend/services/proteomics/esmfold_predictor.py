"""
services/proteomics/esmfold_predictor.py

مسؤولية هذا الملف: التنبؤ ببنية بروتين ثلاثية الأبعاد (3D) انطلاقاً من
تسلسل الأحماض الأمينية *الفعلي للمريض*.

نقطة مهمة جداً بالتصميم (سبب وجود هذا الملف أصلاً):
ملف PDB التجريبي القادم من RCSB (عبر structure_fetcher.py) يمثّل دائماً
البروتين *السليم المرجعي* (Wild-Type) الموجود بقواعد البيانات العالمية -
هذا الملف لا يعكس إطلاقاً تأثير طفرات المريض الفعلية على الشكل الفراغي
للبروتين (لأن المريض المصاب لا يوجد له ملف PDB تجريبي أصلاً - محدّده هو
نفسه). لذلك:

    - RCSB/PDB   -> يُستخدم فقط كـ "مرجع سليم" للمقارنة الحتمية
                    (mutation_comparator.py).
    - ESMFold     -> يُستخدم دائماً لتوليد بنية *بناءً على تسلسل المريض
                    نفسه بطفراته*، وهو ما يُعرض فعلياً للمستخدم/الطبيب
                    ليشوف الأثر الحقيقي المحتمل للطفرة على الشكل الفراغي.

النموذج المستخدم: ESMFold عبر واجهة ESM Metagenomic Atlas العامة (Meta AI)
- مجانية ولا تحتاج مفتاح API.

هذه العملية تنبؤية بطبيعتها (Predictive) وغير حتمية - النتيجة قد تختلف
قليلاً بين طلب وآخر، والثقة فيها (pLDDT) دائماً يجب عرضها للمستخدم بوضوح
كـ "بنية متنبأ بها" وليست بنية مؤكدة معملياً.

مبدأ الحماية الأهم بهذا الملف: **لا يجوز أبداً** أن يتسبب فشل هذه الخدمة
(شبكة، تحميل بطيء، تسلسل طويل جداً، استجابة غير متوقعة...) بانهيار الـ
pipeline كامل. كل مسار فشل يجب أن يُسجَّل (log) ويُرجع نتيجة فارغة آمنة
(None, None, warnings) بدل رفع Exception للخارج.
"""

import logging
import time
from typing import List, Optional, Tuple, TypedDict

import requests

logger = logging.getLogger(__name__)

ESMFOLD_API_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"

# طول أقصى آمن نسبياً - تسلسلات أطول من هيك بتصير بطيئة جداً أو بترجع خطأ
# من سيرفرات Meta العامة (Practical Limit مش Limit رسمي موثق 100%).
MAX_SAFE_SEQUENCE_LENGTH = 400

# حد أدنى منطقي - تسلسل أقصر من هيك مالوش معنى نتنبأ ببنيته
MIN_SEQUENCE_LENGTH = 5

REQUEST_TIMEOUT_SECONDS = 120  # ESMFold بطيء نسبياً مقارنة بباقي الـ APIs هون

# إعادة محاولة تلقائية عند فشل مؤقت بالشبكة (لا تشمل أخطاء المحتوى نفسه)
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 5

# رموز غير قياسية لا يقبلها ESMFold إطلاقاً - يجب تنظيفها أو رفض الطلب
_VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYX")


class PredictionResult(TypedDict):
    pdb_content: Optional[str]
    confidence_score: Optional[float]
    warnings: List[str]
    success: bool


def _validate_sequence(sequence: str, warnings: List[str]) -> Optional[str]:
    """
    يتحقق من صلاحية التسلسل قبل إرساله لأي API خارجي، ويرجع نسخة منظّفة
    منه أو None لو التسلسل غير صالح إطلاقاً للتنبؤ.

    هذا التحقق المسبق مهم جداً: أفضل نمنع طلب غير صالح محلياً بدل ما نرسله
    ونستهلك وقت/كوتا الـ API الخارجي المجاني على شي رح يفشل أكيد.
    """
    if not sequence:
        warnings.append("[ESMFold] لا يوجد تسلسل أحماض أمينية للتنبؤ ببنيته.")
        return None

    cleaned = sequence.strip().upper().replace("*", "")

    if len(cleaned) < MIN_SEQUENCE_LENGTH:
        warnings.append(
            f"[ESMFold] التسلسل قصير جداً ({len(cleaned)} حمض أميني) - "
            "تم تجاهل طلب التنبؤ بالبنية."
        )
        return None

    invalid_chars = {ch for ch in cleaned if ch not in _VALID_AMINO_ACIDS}
    if invalid_chars:
        warnings.append(
            f"[ESMFold] تم العثور على رموز غير قياسية بالتسلسل وتمت إزالتها: "
            f"{', '.join(sorted(invalid_chars))}"
        )
        cleaned = "".join(ch for ch in cleaned if ch in _VALID_AMINO_ACIDS)

    if len(cleaned) < MIN_SEQUENCE_LENGTH:
        warnings.append(
            "[ESMFold] بعد إزالة الرموز غير القياسية، لم يتبقَّ تسلسل كافٍ "
            "للتنبؤ ببنيته."
        )
        return None

    if len(cleaned) > MAX_SAFE_SEQUENCE_LENGTH:
        warnings.append(
            f"[ESMFold] التسلسل طويل جداً ({len(cleaned)} حمض أميني، الحد "
            f"العملي الآمن هو {MAX_SAFE_SEQUENCE_LENGTH}) - سيتم المحاولة "
            "رغم ذلك لكن الطلب قد يفشل أو يستغرق وقتاً طويلاً جداً."
        )

    return cleaned


def _extract_mean_plddt(pdb_text: str, warnings: List[str]) -> Optional[float]:
    """
    ESMFold يخزّن درجة الثقة (pLDDT) بعمود B-factor بكل سطر ATOM بملف الـ
    PDB الناتج. نحسب متوسطها كتقدير عام لجودة البنية المتنبأ بها بالكامل.

    محمي بالكامل ضد أي سطر مشوّه - أي خطأ بسطر واحد لا يوقف حساب الباقي.
    """
    scores = []
    try:
        for line in pdb_text.splitlines():
            if not line.startswith("ATOM"):
                continue
            try:
                b_factor = float(line[60:66].strip())
                scores.append(b_factor)
            except (ValueError, IndexError):
                continue  # سطر واحد تالف - نتجاهله ونكمل الباقي
    except Exception:
        # حماية قصوى - حتى لو صار خطأ غير متوقع بمعالجة النص نفسه
        logger.exception("[ESMFold] خطأ غير متوقع أثناء استخراج pLDDT.")
        warnings.append(
            "[ESMFold] تعذر استخراج درجة الثقة (pLDDT) من ملف البنية الناتج."
        )
        return None

    if not scores:
        warnings.append(
            "[ESMFold] لم يتم العثور على أي قيم pLDDT صالحة بملف البنية."
        )
        return None

    return round(sum(scores) / len(scores), 2)


def _looks_like_valid_pdb(text: str) -> bool:
    """فحص سريع وخفيف: هل النص المُرجَع يشبه فعلاً ملف PDB؟"""
    if not text or not text.strip():
        return False
    head = text.strip()[:500]
    return any(marker in head for marker in ("ATOM", "HEADER", "PARENT", "MODEL"))


def _call_esmfold_api(cleaned_sequence: str, warnings: List[str]) -> Optional[str]:
    """
    ينفّذ الطلب الفعلي لـ ESMFold API مع إعادة محاولة تلقائية محدودة عند
    فشل مؤقت بالشبكة فقط (Timeout / Connection error) - وليس عند أخطاء
    منطقية بالمحتوى (تلك تُرجع فوراً بدون إعادة محاولة).
    """
    last_error_summary = None

    for attempt in range(1, MAX_RETRIES + 2):  # المحاولة الأولى + إعادات
        try:
            response = requests.post(
                ESMFOLD_API_URL,
                data=cleaned_sequence,
                headers={"Content-Type": "text/plain"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.Timeout:
            last_error_summary = "انتهت مهلة الاتصال (timeout)"
        except requests.ConnectionError:
            last_error_summary = "تعذر الاتصال بخادم ESMFold (connection error)"
        except requests.RequestException as exc:
            # أي خطأ شبكة آخر غير متوقع - نسجله ونعتبره فشل نهائي بدون إعادة محاولة
            logger.exception("[ESMFold] استثناء غير متوقع أثناء الطلب.")
            warnings.append(f"[ESMFold] فشل الاتصال بالخدمة: {exc}")
            return None
        else:
            # وصل رد من السيرفر - نتحقق من صحته (لا داعي لإعادة محاولة شبكية)
            if response.status_code == 200 and _looks_like_valid_pdb(response.text):
                return response.text

            if response.status_code == 200:
                # رد 200 لكن المحتوى مش PDB فعلي (رسالة خطأ نصية مثلاً)
                warnings.append(
                    "[ESMFold] استجابة الخادم لا تبدو ملف PDB صالح "
                    f"(أول 200 حرف): {response.text[:200]!r}"
                )
                logger.error(
                    "[ESMFold] استجابة غير صالحة رغم status 200: %s",
                    response.text[:300],
                )
                return None  # مشكلة بالمحتوى نفسه - إعادة المحاولة لن تفيد غالباً

            if response.status_code in (429, 503):
                # حمل زائد على السيرفر - هذا فعلاً يستاهل إعادة محاولة
                last_error_summary = f"status={response.status_code} (خادم مزدحم/غير متاح مؤقتاً)"
            else:
                warnings.append(
                    f"[ESMFold] فشل الطلب - status_code={response.status_code}, "
                    f"body={response.text[:200]!r}"
                )
                logger.error(
                    "[ESMFold] فشل الطلب - status_code=%s, body=%s",
                    response.status_code,
                    response.text[:300],
                )
                return None  # خطأ عميل/سيرفر واضح - لا فائدة من إعادة المحاولة

        # لو وصلنا هون معناها في سبب يستاهل إعادة محاولة (timeout/connection/ازدحام)
        if attempt <= MAX_RETRIES:
            logger.warning(
                "[ESMFold] محاولة %d فشلت (%s) - إعادة المحاولة بعد %d ثانية...",
                attempt,
                last_error_summary,
                RETRY_BACKOFF_SECONDS,
            )
            time.sleep(RETRY_BACKOFF_SECONDS)

    warnings.append(
        f"[ESMFold] فشلت جميع المحاولات ({MAX_RETRIES + 1}) - آخر سبب: "
        f"{last_error_summary}."
    )
    return None


def predict_structure(amino_acid_sequence: str) -> PredictionResult:
    """
    نقطة الدخول الرئيسية: يأخذ تسلسل أحماض أمينية (عادةً تسلسل *المريض*
    الفعلي بطفراته) ويرجع بنية 3D متنبأ بها + درجة الثقة.

    محاطة بالكامل بـ try/except خارجي إضافي كخط دفاع أخير - حتى لو صار
    أي خطأ برمجي غير متوقع بالمنطق أعلاه، هذا التابع لن يرفع Exception
    للخارج أبداً، ولن يوقف باقي الـ pipeline.

    Args:
        amino_acid_sequence: تسلسل الأحماض الأمينية (من translator.py).

    Returns:
        PredictionResult:
            - pdb_content: نص ملف PDB الكامل، أو None عند أي فشل.
            - confidence_score: متوسط pLDDT (0-100)، أو None لو تعذر.
            - warnings: كل رسائل التحذير/الفشل بالعربي (تُعرض للمستخدم).
            - success: True فقط لو حصلنا على بنية صالحة فعلياً.
    """
    warnings: List[str] = []

    try:
        cleaned_sequence = _validate_sequence(amino_acid_sequence, warnings)
        if not cleaned_sequence:
            return {
                "pdb_content": None,
                "confidence_score": None,
                "warnings": warnings,
                "success": False,
            }

        pdb_content = _call_esmfold_api(cleaned_sequence, warnings)
        if not pdb_content:
            return {
                "pdb_content": None,
                "confidence_score": None,
                "warnings": warnings,
                "success": False,
            }

        confidence_score = _extract_mean_plddt(pdb_content, warnings)

        return {
            "pdb_content": pdb_content,
            "confidence_score": confidence_score,
            "warnings": warnings,
            "success": True,
        }

    except Exception:
        # خط الدفاع الأخير - لا يجوز أبداً أن يوصل استثناء غير متوقع
        # من هذا الملف إلى tasks.py ويكسر الـ Celery task كامل.
        logger.exception(
            "[ESMFold] خطأ غير متوقع تماماً داخل predict_structure - "
            "تم اعتراضه لحماية باقي الـ pipeline."
        )
        warnings.append(
            "[ESMFold] حدث خطأ داخلي غير متوقع أثناء التنبؤ بالبنية."
        )
        return {
            "pdb_content": None,
            "confidence_score": None,
            "warnings": warnings,
            "success": False,
        }