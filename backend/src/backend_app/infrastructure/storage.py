import logging
from pathlib import Path
from typing import Optional, Union

import boto3

from ..config.settings import get_settings

logger = logging.getLogger("backend_app.storage")
settings = get_settings()


def _s3_client():
    session = boto3.session.Session(region_name=settings.s3_region)
    return session.client("s3")


def _s3_url(key: str) -> str:
    if settings.s3_public_base_url:
        return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
    client = _s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=3600,
    )


def save_report(
    content: Union[str, bytes],
    filename: str,
    content_type: str = "text/plain; charset=utf-8",
) -> str:
    if settings.reports_storage.lower() == "s3" and settings.s3_bucket:
        key = f"{settings.s3_prefix.strip('/')}/{filename}"
        try:
            client = _s3_client()
            body = content.encode("utf-8") if isinstance(content, str) else content
            client.put_object(
                Bucket=settings.s3_bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
            return _s3_url(key)
        except Exception as exc:
            logger.warning("S3 upload failed, falling back to local: %s", exc)
    report_path = settings.reports_dir / filename
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        report_path.write_text(content, encoding="utf-8")
    else:
        report_path.write_bytes(content)
    return f"/reports/{filename}"
