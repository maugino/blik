import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from accounts.permissions import assign_organization_admin
from core.branding import organization_logo_urls, organization_report_logo
from core.models import Organization


SVG_LIGHT = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">
<path d="M0 0h100v40H0z"/>
</svg>'''

SVG_DARK = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">
<path d="M10 10h80v20H10z"/>
</svg>'''


class OrganizationBrandingSettingsTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='blik-branding-test-')
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.org = Organization.objects.create(
            name='Acme',
            email='org@acme.example',
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@acme.example',
            password='pw',
        )
        UserProfile.objects.create(
            user=self.admin,
            organization=self.org,
        )
        assign_organization_admin(self.admin)
        self.client.force_login(self.admin)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def svg(self, name, content):
        return SimpleUploadedFile(
            name,
            content,
            content_type='image/svg+xml',
        )

    def post_branding(self, **data):
        return self.client.post(
            reverse('settings'),
            {'section': 'branding', **data},
        )

    def test_uploads_light_logo(self):
        response = self.post_branding(
            brand_logo_light=self.svg('light.svg', SVG_LIGHT),
            same_logo_for_dark='on',
        )

        self.assertRedirects(
            response,
            reverse('settings'),
            fetch_redirect_response=False,
        )

        self.org.refresh_from_db()
        self.assertTrue(self.org.brand_logo_light)
        self.assertFalse(self.org.brand_logo_dark)
        self.assertTrue(
            Path(self.org.brand_logo_light.path).is_file()
        )

    def test_separate_dark_logo_is_saved_and_resolved(self):
        self.post_branding(
            brand_logo_light=self.svg('light.svg', SVG_LIGHT),
            brand_logo_dark=self.svg('dark.svg', SVG_DARK),
        )

        self.org.refresh_from_db()

        self.assertTrue(self.org.brand_logo_light)
        self.assertTrue(self.org.brand_logo_dark)

        light, dark = organization_logo_urls(self.org)

        self.assertEqual(light, self.org.brand_logo_light.url)
        self.assertEqual(dark, self.org.brand_logo_dark.url)

    def test_dark_logo_falls_back_to_light(self):
        self.post_branding(
            brand_logo_light=self.svg('light.svg', SVG_LIGHT),
            same_logo_for_dark='on',
        )

        self.org.refresh_from_db()
        light, dark = organization_logo_urls(self.org)

        self.assertEqual(light, self.org.brand_logo_light.url)
        self.assertEqual(dark, light)

    def test_same_logo_checkbox_clears_and_deletes_dark_logo(self):
        self.post_branding(
            brand_logo_light=self.svg('light.svg', SVG_LIGHT),
            brand_logo_dark=self.svg('dark.svg', SVG_DARK),
        )
        self.org.refresh_from_db()

        old_dark = Path(self.org.brand_logo_dark.path)
        self.assertTrue(old_dark.is_file())

        self.post_branding(same_logo_for_dark='on')

        self.org.refresh_from_db()
        self.assertFalse(self.org.brand_logo_dark)
        self.assertFalse(old_dark.exists())

    def test_replacing_light_logo_deletes_old_file(self):
        self.post_branding(
            brand_logo_light=self.svg('first.svg', SVG_LIGHT),
            same_logo_for_dark='on',
        )
        self.org.refresh_from_db()

        old_light = Path(self.org.brand_logo_light.path)
        self.assertTrue(old_light.is_file())

        self.post_branding(
            brand_logo_light=self.svg('second.svg', SVG_DARK),
            same_logo_for_dark='on',
        )

        self.org.refresh_from_db()

        self.assertNotEqual(
            str(old_light),
            self.org.brand_logo_light.path,
        )
        self.assertFalse(old_light.exists())
        self.assertTrue(
            Path(self.org.brand_logo_light.path).is_file()
        )

    def test_remove_uploaded_logos_deletes_both_files(self):
        self.post_branding(
            brand_logo_light=self.svg('light.svg', SVG_LIGHT),
            brand_logo_dark=self.svg('dark.svg', SVG_DARK),
        )
        self.org.refresh_from_db()

        light = Path(self.org.brand_logo_light.path)
        dark = Path(self.org.brand_logo_dark.path)

        self.post_branding(remove_brand_logos='1')

        self.org.refresh_from_db()

        self.assertFalse(self.org.brand_logo_light)
        self.assertFalse(self.org.brand_logo_dark)
        self.assertFalse(light.exists())
        self.assertFalse(dark.exists())

    def test_pdf_prefers_organization_light_logo(self):
        self.post_branding(
            brand_logo_light=self.svg('light.svg', SVG_LIGHT),
            same_logo_for_dark='on',
        )
        self.org.refresh_from_db()

        deployment = Path(self.media_root) / 'deployment.svg'
        deployment.write_bytes(SVG_DARK)

        resolved = organization_report_logo(
            self.org,
            str(deployment),
        )

        self.assertEqual(
            resolved,
            Path(self.org.brand_logo_light.path).resolve().as_uri(),
        )

    def test_pdf_falls_back_to_deployment_logo(self):
        deployment = Path(self.media_root) / 'deployment.svg'
        deployment.write_bytes(SVG_DARK)

        resolved = organization_report_logo(
            self.org,
            str(deployment),
        )

        self.assertEqual(
            resolved,
            deployment.resolve().as_uri(),
        )
