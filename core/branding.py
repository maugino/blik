"""Organization branding helpers and upload validation."""

from pathlib import Path
import xml.etree.ElementTree as ET

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


MAX_LOGO_SIZE = 2 * 1024 * 1024
ALLOWED_SUFFIXES = {'.png', '.webp', '.svg'}
FORBIDDEN_SVG_ELEMENTS = {
    'script',
    'foreignobject',
    'iframe',
    'object',
    'embed',
}

FORBIDDEN_URL_PREFIXES = (
    'javascript:',
    'http:',
    'https:',
    '//',
)


def validate_brand_logo(upload):
    """Allow small PNG, WebP or self-contained SVG logo files."""
    if not upload:
        return

    if upload.size <= 0:
        raise ValidationError(_('The logo file is empty.'))

    if upload.size > MAX_LOGO_SIZE:
        raise ValidationError(_('The logo file must be 2 MB or smaller.'))

    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationError(_('Upload a PNG, WebP or SVG logo.'))

    position = upload.tell()
    try:
        upload.seek(0)
        content = upload.read()

        if suffix == '.svg':
            _validate_svg(content)
        else:
            _validate_raster(content, suffix)
    finally:
        upload.seek(position)


def _validate_raster(content, suffix):
    try:
        from PIL import Image

        from io import BytesIO

        image = Image.open(BytesIO(content))
        image.verify()

        expected = {
            '.png': {'PNG'},
            '.webp': {'WEBP'},
        }[suffix]

        if image.format not in expected:
            raise ValidationError(_('The uploaded file does not match its file type.'))
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError(_('The uploaded logo is not a valid image.')) from error


def _validate_svg(content):
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError, TypeError) as error:
        raise ValidationError(_('The uploaded SVG is not valid.')) from error

    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1].lower()
        if tag in FORBIDDEN_SVG_ELEMENTS:
            raise ValidationError(
                _('The SVG contains content that is not allowed.')
            )

        for attribute, value in element.attrib.items():
            attribute = attribute.rsplit('}', 1)[-1].lower()
            value = str(value).strip().lower()

            if attribute.startswith('on'):
                raise ValidationError(
                    _('The SVG contains content that is not allowed.')
                )

            if any(value.startswith(prefix) for prefix in FORBIDDEN_URL_PREFIXES):
                raise ValidationError(
                    _('The SVG must not reference scripts or external resources.')
                )


def organization_logo_urls(organization):
    """Return browser URLs for organization-uploaded branding."""
    if not organization:
        return '', ''

    light = (
        organization.brand_logo_light.url
        if organization.brand_logo_light
        else ''
    )
    dark = (
        organization.brand_logo_dark.url
        if organization.brand_logo_dark
        else light
    )
    return light, dark


def organization_report_logo(organization, deployment_logo=''):
    """Return a file URI suitable for the PDF renderer."""
    if organization and organization.brand_logo_light:
        try:
            return Path(
                organization.brand_logo_light.path
            ).resolve().as_uri()
        except (NotImplementedError, ValueError):
            # Local FileSystemStorage supports .path. Other storage backends
            # may not, so retain the deployment-level PDF fallback.
            pass

    if deployment_logo:
        path = Path(deployment_logo)
        if path.is_file():
            return path.resolve().as_uri()

    return ''
