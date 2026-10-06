from django.conf import settings
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.test.client import RequestFactory
from django.urls import reverse
from django.middleware.locale import LocaleMiddleware


@override_settings(
    MIDDLEWARE=[
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.locale.LocaleMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
    ],
)
class InterfaceLocalizationTests(TestCase):
    def test_supported_interface_languages_are_limited_to_phase_one(self):
        self.assertEqual(
            settings.LANGUAGES,
            [
                ('en-us', 'English'),
                ('fr', 'Français'),
                ('de', 'Deutsch'),
                ('it', 'Italiano'),
            ],
        )

    def test_language_switch_sets_cookie_and_keeps_safe_current_page(self):
        response = Client().post(
            reverse('set_language'),
            {'language': 'fr', 'next': '/dashboard/?tab=cycles'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/dashboard/?tab=cycles')
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value,
            'fr',
        )

    def test_language_switch_rejects_unsupported_language(self):
        response = Client().post(
            reverse('set_language'),
            {'language': 'es', 'next': '/dashboard/'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_language_switch_rejects_external_redirect(self):
        response = Client().post(
            reverse('set_language'),
            {'language': 'de', 'next': 'https://example.invalid/'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    def test_language_switch_requires_csrf(self):
        response = Client(enforce_csrf_checks=True).post(
            reverse('set_language'),
            {'language': 'it', 'next': '/dashboard/'},
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(
        LANGUAGE_CODE='en-us',
        LANGUAGES=[
            ('en-us', 'English'),
            ('fr', 'Français'),
            ('de', 'Deutsch'),
            ('it', 'Italiano'),
        ],
    )
    def test_locale_middleware_uses_english_default_and_accepts_explicit_cookie(self):
        middleware = LocaleMiddleware(lambda request: HttpResponse())
        factory = RequestFactory()

        default_request = factory.get('/')
        middleware.process_request(default_request)
        self.assertEqual(default_request.LANGUAGE_CODE, 'en-us')

        browser_request = factory.get('/', HTTP_ACCEPT_LANGUAGE='fr,de;q=0.8')
        middleware.process_request(browser_request)
        self.assertEqual(browser_request.LANGUAGE_CODE, 'fr')

        selected_request = factory.get(
            '/',
            HTTP_ACCEPT_LANGUAGE='de',
            HTTP_COOKIE=f'{settings.LANGUAGE_COOKIE_NAME}=it',
        )
        middleware.process_request(selected_request)
        self.assertEqual(selected_request.LANGUAGE_CODE, 'it')
