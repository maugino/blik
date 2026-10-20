from django.db import migrations


def grant_to_admin_group(apps, schema_editor):
    """Give the Organization Admin group the new questionnaire permission.

    Fresh installs get it from ensure_permission_groups(); this covers
    databases where the group already exists with the four older permissions.
    """
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    try:
        content_type = ContentType.objects.get(app_label='accounts', model='userprofile')
    except ContentType.DoesNotExist:
        return

    permission, _ = Permission.objects.get_or_create(
        codename='can_manage_questionnaires',
        content_type=content_type,
        defaults={'name': 'Can create and edit questionnaires'},
    )

    admin_group = Group.objects.filter(name='Organization Admin').first()
    if admin_group:
        admin_group.permissions.add(permission)


def revoke_from_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    permission = Permission.objects.filter(codename='can_manage_questionnaires').first()
    admin_group = Group.objects.filter(name='Organization Admin').first()
    if permission and admin_group:
        admin_group.permissions.remove(permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_add_password_reset_token'),
        ('auth', '__latest__'),
        ('contenttypes', '__latest__'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='userprofile',
            options={
                'ordering': ['user__username'],
                'permissions': [
                    ('can_invite_members', 'Can invite team members'),
                    ('can_manage_organization', 'Can manage organization settings'),
                    ('can_delete_organization', 'Can delete organization'),
                    ('can_view_all_reports', 'Can view all organization reports'),
                    ('can_manage_questionnaires', 'Can create and edit questionnaires'),
                ],
            },
        ),
        migrations.RunPython(grant_to_admin_group, revoke_from_admin_group),
    ]
