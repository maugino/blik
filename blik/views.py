"""
Core views for Blik application
"""
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.i18n import set_language as django_set_language


def health_check(request):
    """Health check endpoint for monitoring"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'blik',
        'version': '0.1.0'
    })


def home(request):
    """Home page - redirect authenticated users to dashboard, others to login"""
    if request.user.is_authenticated:
        return redirect('admin_dashboard')
    return redirect('login')


def set_interface_language(request):
    """Restrict Django's standard language switcher to exposed UI languages."""
    if request.POST.get('language') not in {
        code for code, _name in settings.LANGUAGES
    }:
        post_data = request.POST.copy()
        post_data['language'] = ''
        request.POST = post_data
    return django_set_language(request)


def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'landing/404.html', status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, 'landing/500.html', status=500)
