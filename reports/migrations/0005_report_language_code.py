from django.db import migrations, models


def populate_report_language(apps, schema_editor):
    Report = apps.get_model('reports', 'Report')
    for report in Report.objects.select_related(
        'cycle__questionnaire'
    ).iterator():
        source_language = report.cycle.questionnaire.source_language or 'en-us'
        report.language_code = source_language.strip().replace('_', '-').lower()
        report.save(update_fields=['language_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('questionnaires', '0017_questionnaire_source_language_and_more'),
        ('reports', '0004_add_uuid_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='language_code',
            field=models.CharField(blank=True, default='', help_text='Questionnaire-content language frozen into this report snapshot', max_length=35),
        ),
        migrations.RunPython(populate_report_language, migrations.RunPython.noop),
    ]
