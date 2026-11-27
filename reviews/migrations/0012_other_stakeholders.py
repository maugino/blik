from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0011_outbox"),
    ]

    operations = [
        migrations.AddField(
            model_name="reviewcycle",
            name="include_other",
            field=models.BooleanField(
                default=False,
                verbose_name="Other",
            ),
        ),
        migrations.AddField(
            model_name="reviewcycle",
            name="invitation_token_other",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
                unique=True,
                verbose_name="other stakeholder invitation token",
            ),
        ),
        migrations.AlterField(
            model_name="reviewertoken",
            name="category",
            field=models.CharField(
                choices=[
                    ("self", "Self Assessment"),
                    ("peer", "Peer Review"),
                    ("manager", "Manager Review"),
                    ("direct_report", "Direct Report Review"),
                    ("other", "Other"),
                ],
                max_length=20,
                verbose_name="feedback category",
            ),
        ),
    ]
