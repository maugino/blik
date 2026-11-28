from django.db import migrations, models

import core.branding


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_organization_org_chart_offer_dismissed'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='brand_logo_light',
            field=models.FileField(
                blank=True,
                upload_to='organization-logos/',
                validators=[core.branding.validate_brand_logo],
                verbose_name='logo for light backgrounds',
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='brand_logo_dark',
            field=models.FileField(
                blank=True,
                upload_to='organization-logos/',
                validators=[core.branding.validate_brand_logo],
                verbose_name='logo for dark backgrounds',
            ),
        ),
    ]
