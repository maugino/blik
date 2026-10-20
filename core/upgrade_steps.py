"""
Registry of one-time upgrade steps.

Each entry is a (name, callable) tuple. The callable receives a stdout
write-stream for logging. Steps are run in order; only steps not yet
recorded as success=True in the UpgradeStep table will execute.

Old steps should stay in this list forever. If the underlying code is
removed later, replace the callable body with a no-op.
"""
from questionnaires.management.commands.apply_dreyfus_mappings import Command as DreyfusCommand


def _apply_dreyfus_mappings(stdout):
    cmd = DreyfusCommand(stdout=stdout)
    cmd.handle(dry_run=False)


def _reapply_dreyfus_mappings(stdout):
    """Re-run dreyfus mappings to catch any records missed by 0001.

    The fixtures were updated in the same commit as this step, so fresh
    installs get the right data.  For existing deployments the idempotent
    apply_dreyfus_mappings command ensures every DB record is up to date.
    """
    _apply_dreyfus_mappings(stdout)


def _move_setup_admins_into_the_admin_group(stdout):
    """Put admins that hold their permissions directly into the admin group.

    Until this release the setup page granted three permissions straight to
    the first user instead of calling assign_organization_admin(). Those
    accounts are in no group, so every permission added to the group later
    passes them by, and they never got can_delete_organization at all. The
    data import did the same with can_manage_organization alone.

    Only accounts holding can_manage_organization directly are touched. One
    already in the member group was demoted, and assign_organization_member
    used to leave the grant behind: it stays a member and loses the grant.
    Per-user grants the role does not cover (can_view_all_reports, say)
    survive either way.
    """
    from django.contrib.auth.models import User

    from accounts.permissions import (
        ADMIN_ROLE_CODENAMES,
        ORG_ADMIN_GROUP,
        ORG_MEMBER_GROUP,
        _drop_direct_grants,
        assign_organization_admin,
        ensure_permission_groups,
    )

    if ensure_permission_groups() == (None, None):
        # Raise so the runner records a failure and retries next time.
        raise RuntimeError('Apps not ready')

    candidates = User.objects.filter(
        user_permissions__codename='can_manage_organization',
        user_permissions__content_type__app_label='accounts',
    ).exclude(groups__name=ORG_ADMIN_GROUP).distinct()

    moved = demoted = 0
    for user in candidates:
        if user.groups.filter(name=ORG_MEMBER_GROUP).exists():
            _drop_direct_grants(user, ADMIN_ROLE_CODENAMES)
            demoted += 1
            stdout.write(f'  {user.username} stays {ORG_MEMBER_GROUP}')
        else:
            assign_organization_admin(user)
            moved += 1
            stdout.write(f'  {user.username} -> {ORG_ADMIN_GROUP}')

    stdout.write(f'Moved {moved} account(s) into {ORG_ADMIN_GROUP}, '
                 f'removed stale admin grants from {demoted} member(s).')


STEPS = [
    ('0001_apply_dreyfus_mappings', _apply_dreyfus_mappings),
    ('0002_reapply_dreyfus_mappings', _reapply_dreyfus_mappings),
    ('0003_move_setup_admins_into_the_admin_group',
     _move_setup_admins_into_the_admin_group),
]
