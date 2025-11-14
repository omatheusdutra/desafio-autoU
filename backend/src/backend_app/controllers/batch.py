from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse

from ..services.processing import handle_zip_payload
from ..config.settings import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/batch_upload", response_class=HTMLResponse)
async def batch_upload(request: Request, emails_zip: UploadFile = File(...)):
    templates = request.app.state.templates
    data = await emails_zip.read()
    rows, csv_name, summary = await handle_zip_payload(data)

    preview_limit = max(1, settings.batch_preview_limit)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "batch_done": True,
            "report_url": f"/reports/{csv_name}",
            "rows": rows[:preview_limit],
            "summary": summary,
            "zip_success_message": "ZIP processado e relatório disponível!",
        },
    )
