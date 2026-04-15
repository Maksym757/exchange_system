from types import MethodType


ALLOWED_ADMIN_GROUPS = {
    "admin",
    "manager",
    "employee",
    "worker",
    "\u043f\u0440\u0430\u0446\u0456\u0432\u043d\u0438\u043a",
    "\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440",
    "\u0430\u0434\u043c\u0456\u043d",
    "group_management",
    "administrator",
    "pracivnyk",
    "menedzher",
    "admin_ua",
}

ALLOWED_ADMIN_USERNAMES = {
    "admin",
    "manager",
    "employee",
    "worker",
    "\u043f\u0440\u0430\u0446\u0456\u0432\u043d\u0438\u043a",
    "\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440",
    "\u0430\u0434\u043c\u0456\u043d",
    "pracivnyk",
    "menedzher",
    "administrator",
    "admin_ua",
}


def _patched_has_permission(self, request):
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return False

    if user.is_superuser or user.is_staff:
        return True

    if (user.username or "").strip().lower() in ALLOWED_ADMIN_USERNAMES:
        return True

    user_group_names = {
        (group_name or "").strip().lower()
        for group_name in user.groups.values_list("name", flat=True)
    }
    return bool(user_group_names & ALLOWED_ADMIN_GROUPS)


def patch_default_admin_site(admin_site):
    # Keep default admin site/registry, only broaden login permission by group.
    admin_site.has_permission = MethodType(_patched_has_permission, admin_site)
    admin_site.site_header = (
        "\u0410\u0434\u043c\u0456\u043d\u0456\u0441\u0442\u0440\u0443\u0432\u0430\u043d\u043d\u044f "
        "\u0432\u0430\u043b\u044e\u0442\u043d\u043e\u0457 \u0441\u0438\u0441\u0442\u0435\u043c\u0438"
    )
    admin_site.site_title = "\u0410\u0434\u043c\u0456\u043d-\u043f\u0430\u043d\u0435\u043b\u044c"
    admin_site.index_title = (
        "\u041a\u0435\u0440\u0443\u0432\u0430\u043d\u043d\u044f \u0434\u0430\u043d\u0438\u043c\u0438"
    )
