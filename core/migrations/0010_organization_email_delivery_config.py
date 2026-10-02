from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0009_upgradestep'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='email_delivery_method',
            field=models.CharField(
                choices=[('smtp', 'SMTP'), ('http_webhook', 'HTTP Webhook')],
                default='smtp',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='email_webhook_url_encrypted',
            field=models.BinaryField(blank=True, null=True),
        ),
    ]
