from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='submission',
            constraint=models.UniqueConstraint(
                fields=('candidate', 'assessment'),
                name='unique_submission_per_candidate_assessment',
            ),
        ),
    ]
