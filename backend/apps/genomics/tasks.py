"""
apps/genomics/tasks.py
The Celery task that runs the full genomic pipeline in the background,
followed by a separate task that generates the LLM clinical report.
"""

import logging
from backend.core.utils.atomic_utils import atomic_with_cleanup
from celery import shared_task
from django.utils import timezone
from celery.exceptions import SoftTimeLimitExceeded
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, acks_late=True, track_started=True,soft_time_limit=600,   
    time_limit=660,)
def run_genomic_pipeline_task(self, input_data_id: int) -> dict:
    from apps.genomics.models import InputData, OutputData
    from services.pipeline_manager import GenomicPipelineManager, PipelineCancelledError

    logger.info("[Task %s] Pipeline started for InputData id=%s", self.request.id, input_data_id)

    try:
        input_data = InputData.objects.select_related("cell_type", "patient").get(pk=input_data_id)
    except InputData.DoesNotExist:
        logger.error("[Task] InputData id=%s not found — aborting", input_data_id)
        return {"error": "InputData not found"}

    try:
        manager = GenomicPipelineManager(input_data_id=input_data_id)
        results: dict = manager.run()
    except SoftTimeLimitExceeded:
        # ← هاد الجزء الجديد المهم: تجاوز الـ 5 دقايق
        logger.error("[Task] Pipeline TIMEOUT (>5min) for InputData id=%s — marking as failed", input_data_id)
        input_data.status = "failed"
        input_data.save(update_fields=["status"])
        return {"status": "failed", "reason": "timeout_exceeded"}
    except PipelineCancelledError:
        # ← إلغاء صريح من المستخدم (status="cancelling") — مكتشف داخل
        # GenomicPipelineManager._check_cancelled بين خطوات الـ pipeline.
        # ما في داعي لـ retry هون أبداً، ولا لإعادة فحص الـ status لأنه
        # إحنا يلي رفعنا الاستثناء وعارفين السبب أصلاً.
        logger.info("[Task] Pipeline cancelled by user. Cleaning up InputData ID=%s", input_data_id)
        if input_data.dna_sequence_file and input_data.dna_sequence_file.storage.exists(input_data.dna_sequence_file.name):
            input_data.dna_sequence_file.delete(save=False)
        input_data.delete()
        return {"status": "deleted", "message": "Cancelled and completely removed by user"}
    except Exception as exc:
        input_data.refresh_from_db()
        if input_data.status == "cancelling":
            # حالة احتياطية: إلغاء اكتُشف بطريقة تانية (مثلاً استثناء غير
            # متوقع صار بالتزامن مع طلب stop) — نفس منطق التنظيف السابق.
            logger.info("[Task] Pipeline stopped by user. Cleaning up InputData ID=%s", input_data_id)
            if input_data.dna_sequence_file and input_data.dna_sequence_file.storage.exists(input_data.dna_sequence_file.name):
                input_data.dna_sequence_file.delete(save=False)
            input_data.delete()
            return {"status": "deleted", "message": "Cancelled and completely removed by user"}

        logger.exception("[Task] Pipeline FAILED for InputData id=%s", input_data_id)
        input_data.status = "failed"
        input_data.save(update_fields=["status"])
        raise self.retry(exc=exc)

    output_data = None
    try:
        with atomic_with_cleanup(log_prefix="PipelineTask-SaveOutput"):
            output_data, _ = OutputData.objects.update_or_create(
                input_data=input_data,
                defaults={
                    "hic_patient_file": results["hic_patient_file"],
                    "hic_control_file": results.get("hic_control_file", ""),
                    "coords_patient_file": results["coords_patient_file"],
                    "coords_control_file": results.get("coords_control_file", ""),
                    "affected_proteins": results["affected_proteins"],
                    "generated_at": timezone.now(),
                },
            )
            InputData.objects.filter(pk=input_data_id).update(status="completed")
    except Exception:
        input_data.status = "failed"
        input_data.save(update_fields=["status"])
        raise

    logger.info("[Task] Pipeline completed → OutputData id=%s", output_data.id)
    generate_llm_report_task.delay(output_data.id)

    return {"output_data_id": output_data.id, "status": "completed"}

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="apps.genomics.tasks.generate_llm_report_task",
)

def generate_llm_report_task(self, output_data_id: int) -> dict:
    """
    Generates (or regenerates) the AI clinical report for a completed
    pipeline run. Retries on transient network/API errors.
    """
    from apps.genomics.models import OutputData
    from apps.reports.models import AnalysisReport
    from services.llm_service.bridge import run_llm_report_bridge

    logger.info("[LLM Task] Initiating report generation for OutputData ID=%s", output_data_id)

    try:
        output_data = OutputData.objects.select_related(
            "input_data__patient", "input_data__cell_type"
        ).get(pk=output_data_id)
    except OutputData.DoesNotExist:
        logger.error("[LLM Task] OutputData ID=%s not found in database", output_data_id)
        return {"error": "OutputData not found"}

    report, created = AnalysisReport.objects.get_or_create(
        output_data=output_data,
        defaults={
            "status": "draft",
            "summary_text": "AI clinical engine is analyzing chromatin folds...",
        },
    )

    try:
        markdown_result = run_llm_report_bridge(output_data)
        if "Error:" in markdown_result:
            raise Exception(f"Gemini Bridge returned an error structure: {markdown_result}")
    except Exception as exc:
        if self.request.retries < self.max_retries:
            logger.warning(
                "[LLM Task] Connection/API issue. Retrying in 60s... (%d/%d)",
                self.request.retries + 1,
                self.max_retries,
            )
            raise self.retry(exc=exc)

        logger.error("[LLM Task] All retries exhausted for OutputData ID=%s", output_data_id)
        report.summary_text = f"Clinical report generation failed after retries: {exc}"
        report.status = "failed"  # تحديث الحالة هنا
        report.save(update_fields=["summary_text", "status"])
        raise exc

    report.summary_text = markdown_result
    report.detected_disease = "Structural Chromatin Alteration Detected"
    report.status = "completed"  # التقرير أصبح جاهزاً
    report.save(update_fields=["summary_text", "detected_disease", "status"])

    
    action = "created" if created else "regenerated"
    logger.info("[LLM Task] Report successfully %s with ID=%s", action, report.id)
    return {"report_id": report.id, "action": action}