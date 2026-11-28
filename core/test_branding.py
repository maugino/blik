from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from core.branding import validate_brand_logo


class BrandLogoValidationTests(SimpleTestCase):
    def raster(self, format_name, extension):
        buffer = BytesIO()
        Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(
            buffer,
            format=format_name,
        )
        return SimpleUploadedFile(
            f"logo.{extension}",
            buffer.getvalue(),
        )

    def svg(self, body):
        return SimpleUploadedFile(
            "logo.svg",
            body.encode("utf-8"),
            content_type="image/svg+xml",
        )

    def test_accepts_png(self):
        validate_brand_logo(self.raster("PNG", "png"))

    def test_accepts_webp(self):
        validate_brand_logo(self.raster("WEBP", "webp"))

    def test_accepts_simple_svg(self):
        validate_brand_logo(
            self.svg(
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 100 40">'
                '<path d="M0 0h100v40H0z"/>'
                '</svg>'
            )
        )

    def test_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile(
            "logo.jpg",
            b"not-a-logo",
            content_type="image/jpeg",
        )
        with self.assertRaises(ValidationError):
            validate_brand_logo(upload)

    def test_rejects_file_over_two_mb(self):
        upload = SimpleUploadedFile(
            "logo.png",
            b"x" * (2 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_brand_logo(upload)

    def test_rejects_malformed_svg(self):
        with self.assertRaises(ValidationError):
            validate_brand_logo(self.svg("<svg><broken></svg>"))

    def test_rejects_svg_script(self):
        with self.assertRaises(ValidationError):
            validate_brand_logo(
                self.svg(
                    '<svg xmlns="http://www.w3.org/2000/svg">'
                    '<script>alert(1)</script>'
                    '</svg>'
                )
            )

    def test_rejects_svg_event_handler(self):
        with self.assertRaises(ValidationError):
            validate_brand_logo(
                self.svg(
                    '<svg xmlns="http://www.w3.org/2000/svg" '
                    'onclick="alert(1)"></svg>'
                )
            )

    def test_rejects_svg_external_url(self):
        with self.assertRaises(ValidationError):
            validate_brand_logo(
                self.svg(
                    '<svg xmlns="http://www.w3.org/2000/svg">'
                    '<image href="https://example.com/logo.png"/>'
                    '</svg>'
                )
            )
