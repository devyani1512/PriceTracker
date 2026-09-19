# Durable scheduled-job queue for the cron tick + job runner.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="priority",
            field=models.IntegerField(db_index=True, default=100),
        ),
        migrations.AddField(
            model_name="task",
            name="product_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="slot_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="attempts",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="task",
            name="locked_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(
                fields=["category", "product_id", "slot_at"],
                name="ix_tasks_category_product_slot",
            ),
        ),
    ]
