from django.db import migrations


def apply_migration(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.bulk_create([
        Group(name=u'group1'),
        Group(name=u'group2'),
        Group(name=u'group3'),
    ])


def revert_migration(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(
        name__in=[
            u'group1',
            u'group2',
            u'group3',
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('carb', '0001_initial')]
    operations = [migrations.RunPython(apply_migration, revert_migration)]
