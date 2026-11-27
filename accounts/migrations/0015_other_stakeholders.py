from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_review_setup"),
    ]

    operations = [
        migrations.AddField(
            model_name="reviewsetup",
            name="include_other",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="setupreviewer",
            name="category",
            field=models.CharField(
                choices=[
                    ("manager", "Manager"),
                    ("peer", "Peer"),
                    ("direct_report", "Direct report"),
                    ("other", "Other"),
                ],
                max_length=20,
            ),
        ),
    ]
