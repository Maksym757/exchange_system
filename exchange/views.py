import json
import secrets
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import Group, User
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework.viewsets import ModelViewSet

from .models import Order
from .serializers import OrderSerializer


ROLE_LEVELS = {
    "user": 0,
    "worker": 1,
    "manager": 2,
    "admin": 3,
}

ROLE_CHOICES = [
    ("user", "User"),
    ("worker", "Worker"),
    ("manager", "Manager"),
    ("admin", "Admin"),
]

ROLE_LABELS = dict(ROLE_CHOICES)

ROLE_DESTINATIONS = {
    "user": "/",
    "worker": "/worker/",
    "manager": "/manager/",
    "admin": "/admin/",
}

ROLE_ALIASES = {
    "worker": {
        "worker",
        "employee",
        "pracivnyk",
        "працівник",
    },
    "manager": {
        "manager",
        "menedzher",
        "менеджер",
    },
    "admin": {
        "admin",
        "administrator",
        "admin_ua",
        "адмін",
    },
}

SUPPORTED_CURRENCIES = ["USD", "EUR", "PLN", "GBP", "UAH"]
HOME_RATE_QUOTE_CURRENCY = "UAH"
HOME_REFERENCE_RATES = {
    "USD": 41.35,
    "EUR": 44.90,
    "PLN": 10.55,
    "GBP": 52.10,
}

ORDER_STATUS_LABELS = {
    "new": "New",
    "confirmed": "Confirmed",
    "in_progress": "In Progress",
    "done": "Completed",
    "canceled": "Canceled",
    "error": "Error",
}

MANAGER_QUEUE_STATUSES = {"new", "confirmed", "in_progress"}
HOME_STATUS_LABELS_EN = {
    "new": "New",
    "confirmed": "Confirmed",
    "in_progress": "In Progress",
    "done": "Completed",
    "canceled": "Canceled",
    "error": "Error",
}

HOME_CITY = "Львів"
HOME_PHONE = "+38 (096) 876-16-48"
HOME_PHONE_LINK = "tel:+380968761648"
HOME_SCHEDULE = "Щодня з 08:00 до 20:00"
HOME_ADDRESS = "Центральна локація міста зі зручним доїздом та швидким обслуговуванням у пункті обміну."
HOME_SERVICE_TAGS = [
    {
        "label": "Пункт обміну готівки",
        "url": "#contact",
        "accent": "cash",
    },
    {
        "label": "Курси валют на сьогодні",
        "url": "#rates",
        "accent": "rates",
    },
    {
        "label": "Калькулятор обміну",
        "url": "#calculator",
        "accent": "cross",
    },
    {
        "label": "Створити заявку на обмін",
        "url": "/orders/",
        "accent": "orders",
    },
]
HOME_BENEFITS = [
    {
        "title": "Курси одразу на головній",
        "text": "Основні валютні пари видно відразу без переходу в окремий модуль.",
    },
    {
        "title": "Швидкий калькулятор",
        "text": "Калькулятор миттєво рахує доступні напрямки між USD, EUR, PLN, GBP та UAH.",
    },
    {
        "title": "Внутрішня службова зона",
        "text": "Працівники, менеджери й адміністратори мають окремі точки входу у свої робочі розділи.",
    },
    {
        "title": "Продуманий робочий сценарій",
        "text": "Головна сторінка підсвічує контроль заявок, видимість історії та зрозумілий процес обміну.",
    },
    {
        "title": "Швидке оновлення даних",
        "text": "Курси будуються на основі останніх заявок у системі або довідкових значень, коли історії ще мало.",
    },
    {
        "title": "Готово до масштабування",
        "text": "Структура сторінки вже підтримує додавання нових валют, міст і додаткових сервісів.",
    },
]
HOME_PROCESS_STEPS = [
    {
        "step": "01",
        "title": "Оберіть пару в калькуляторі",
        "text": "На головній сторінці користувач одразу бачить напрямок обміну та орієнтовний результат.",
    },
    {
        "step": "02",
        "title": "Звірте актуальні курси",
        "text": "Таблиця нижче показує основні пари у форматі купівлі та продажу, як у класичному обміннику.",
    },
    {
        "step": "03",
        "title": "Перейдіть у робочий модуль",
        "text": "Працівник або менеджер може продовжити операцію у модулі замовлень без пошуку потрібного розділу.",
    },
]
HOME_TESTIMONIALS = [
    {
        "author": "Iryna",
        "title": "Клієнт сервісу",
        "text": "Головна сторінка тепер виглядає як справжній сервіс обміну з курсами, калькулятором і зрозумілими діями.",
    },
    {
        "author": "Oleksandr",
        "title": "Операційний менеджер",
        "text": "Сторінка стала значно ближчою до реального сайту обміну валют і водночас залишила внутрішні дії під рукою.",
    },
    {
        "author": "Maryna",
        "title": "Оператор каси",
        "text": "З першого екрана одразу видно головне: доступні пари, останні оновлення та куди переходити далі.",
    },
]
HOME_SERVICE_ACCESS = [
    {
        "title": "Працівник",
        "description": "Операційний доступ до замовлень, створення обміну та оновлення статусів.",
        "url": "/admin-panel/?role=worker",
        "cta": "Відкрити режим працівника",
    },
    {
        "title": "Менеджер",
        "description": "Контроль черги, моніторинг статусів і координація активних операцій.",
        "url": "/admin-panel/?role=manager",
        "cta": "Відкрити режим менеджера",
    },
    {
        "title": "Адміністратор",
        "description": "Керування доступом, реєстрація адміністратора, відновлення пароля та системні ролі.",
        "url": "/admin-panel/?role=admin",
        "cta": "Відкрити адмін-панель",
    },
]

TEAM_SEED = [
    {
        "name": "Iryna Melnyk",
        "role": "Адміністратор",
        "email": "admin@exchange.local",
    },
    {
        "name": "Oleh Shevchenko",
        "role": "Менеджер",
        "email": "manager@exchange.local",
    },
    {
        "name": "Maryna Koval",
        "role": "Працівник",
        "email": "support@exchange.local",
    },
]

ROLE_DASHBOARDS = [
    {
        "slug": "worker",
        "label": "Працівник",
        "emoji": "🧾",
        "summary": "Операційна робота із заявками на обмін у щоденному режимі.",
        "cta_label": "Перейти як працівник",
        "cta_url": "/admin-panel/?role=worker",
        "features": [
            "Вхід у службовий режим працівника",
            "Доступ до сторінки замовлень",
            "Створення нового замовлення на обмін",
            "Вибір валюти продажу та купівлі",
            "Введення суми та курсу обміну",
            "Автоматичний розрахунок результату",
            "Перегляд списку всіх замовлень",
            "Оновлення статусу замовлення",
            "Перегляд лічильників по статусах",
        ],
    },
    {
        "slug": "manager",
        "label": "Менеджер",
        "emoji": "📋",
        "summary": "Контроль обробки заявок, статусів і поточної операційної картини.",
        "cta_label": "Перейти як менеджер",
        "cta_url": "/admin-panel/?role=manager",
        "features": [
            "Вхід у режим менеджера",
            "Доступ до робочого столу замовлень",
            "Перегляд усіх створених операцій",
            "Контроль статусів нових, підтверджених і виконаних заявок",
            "Оновлення статусу кожного замовлення",
            "Моніторинг загальної кількості операцій",
            "Перегляд останнього замовлення на головній",
            "Контроль кількості працівників і менеджерів у системі",
        ],
    },
    {
        "slug": "admin",
        "label": "Адмін",
        "emoji": "🛡️",
        "summary": "Головний службовий розділ для керування доступом, ролями та системними інструментами.",
        "cta_label": "Перейти до реєстрації адміна",
        "cta_url": "/admin-panel/?role=admin",
        "features": [
            "Реєстрація нового адміністратора",
            "Відновлення пароля адміністратора",
            "Перемикання службових ролей",
            "Контроль кількості адміністраторів",
            "Перегляд командних контактів на головній",
            "Доступ до API-документації",
        ],
        "action_cards": [
            {
                "title": "Реєстрація нового адміністратора",
                "url": "/admin-panel/?role=admin",
            },
            {
                "title": "Відновлення пароля адміністратора",
                "url": "/admin-panel/password-reset/",
            },
            {
                "title": "Перемикання службових ролей",
                "url": "/admin-panel/?role=worker",
            },
            {
                "title": "Контроль кількості адміністраторів",
                "url": "#overview",
            },
            {
                "title": "Перегляд командних контактів на головній",
                "url": "#team",
            },
            {
                "title": "Доступ до API-документації",
                "url": "/api/docs/",
            },
        ],
    },
]

HOME_ROLE_DASHBOARDS = list(ROLE_DASHBOARDS)

GOOGLE_OAUTH_SESSION_KEY = "google_oauth_state"
GOOGLE_OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_AUTH_ERROR_MESSAGES = {
    "google_not_configured": "Google sign-in is not configured yet. Create a .env file in the project root and add GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
    "google_access_denied": "Google sign-in was canceled.",
    "google_state_invalid": "The Google session could not be verified. Please try again.",
    "google_profile_failed": "Could not load the Google profile.",
    "google_email_missing": "The Google account did not return an email address.",
    "google_user_not_found": "No account with this Google email was found in the system.",
    "google_role_denied": "The Google account does not have access to the selected role.",
    "google_login_failed": "Google sign-in could not be completed.",
}


def _detect_user_role_level(user):
    if not user.is_authenticated or not user.is_active:
        return 0

    if user.is_superuser or user.is_staff:
        return ROLE_LEVELS["admin"]

    name = (user.username or "").strip().lower()
    for role_name, aliases in ROLE_ALIASES.items():
        if name in aliases:
            return ROLE_LEVELS[role_name]

    group_names = {
        (group_name or "").strip().lower()
        for group_name in user.groups.values_list("name", flat=True)
    }
    for role_name, aliases in ROLE_ALIASES.items():
        if group_names & aliases:
            return ROLE_LEVELS[role_name]

    return 0


def _detect_user_role_name(user):
    if not user.is_active:
        return None

    if user.is_superuser or user.is_staff:
        return "admin"

    name = (user.username or "").strip().lower()
    for role_name, aliases in ROLE_ALIASES.items():
        if name in aliases:
            return role_name

    group_names = {
        (group_name or "").strip().lower()
        for group_name in user.groups.values_list("name", flat=True)
    }
    for role_name, aliases in ROLE_ALIASES.items():
        if group_names & aliases:
            return role_name

    return None


def _normalize_role_name(role_name, default="user"):
    normalized_role = (role_name or "").strip().lower()
    if normalized_role in ROLE_LEVELS:
        return normalized_role

    for canonical_role, aliases in ROLE_ALIASES.items():
        if normalized_role in aliases:
            return canonical_role

    return default


def _is_google_oauth_enabled():
    client_id = (getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or "").strip()
    client_secret = (getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or "").strip()
    return bool(client_id and client_secret)


def _get_google_error_message(request):
    error_code = (request.GET.get("error") or "").strip()
    return GOOGLE_AUTH_ERROR_MESSAGES.get(error_code, "")


def _get_requested_role_name(request, default="user"):
    return _normalize_role_name(
        request.POST.get("role_name")
        or request.POST.get("role")
        or request.GET.get("role"),
        default=default,
    )


def _get_role_destination(role_name):
    normalized_role = _normalize_role_name(role_name, default=None)
    if normalized_role is None:
        return "/"
    return ROLE_DESTINATIONS[normalized_role]


def _get_safe_next_url(request, fallback="/admin/"):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback


def _get_local_next_url(next_url, fallback="/"):
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


def _build_google_start_url(intent, *, next_url, role_name="worker"):
    params = {
        "intent": intent,
        "next": next_url,
    }
    if intent == "login":
        params["role"] = _normalize_role_name(role_name, default="worker")
    return f"/auth/google/start/?{urlencode(params)}"


def _build_google_return_url(intent, *, error_code="", next_url="", role_name="worker"):
    base_url = "/admin-panel/register/" if intent == "register_admin" else "/admin-panel/"
    params = {}
    if next_url:
        params["next"] = next_url
    if intent == "login":
        params["role"] = _normalize_role_name(role_name, default="worker")
    if error_code:
        params["error"] = error_code

    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def _build_google_redirect_uri(request):
    configured_redirect_uri = (
        getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or ""
    ).strip()
    if configured_redirect_uri:
        return configured_redirect_uri
    return request.build_absolute_uri(reverse("google_auth_callback"))


def _google_request_json(url, *, data=None, headers=None):
    request_headers = {
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)

    request_data = None
    method = "GET"
    if data is not None:
        request_data = urlencode(data).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        method = "POST"

    request = Request(url, data=request_data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Google request failed") from exc


def _fetch_google_profile(request, code):
    token_payload = _google_request_json(
        GOOGLE_OAUTH_TOKEN_URL,
        data={
            "code": code,
            "client_id": getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""),
            "client_secret": getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "redirect_uri": _build_google_redirect_uri(request),
            "grant_type": "authorization_code",
        },
    )
    access_token = token_payload.get("access_token")
    if not access_token:
        raise ValueError("Google token missing access_token")

    return _google_request_json(
        GOOGLE_OAUTH_USERINFO_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )


def _generate_unique_username(email):
    local_part = (email.split("@", 1)[0] if email else "") or "googleuser"
    safe_local_part = "".join(
        char for char in local_part.lower() if char.isalnum() or char in {"_", ".", "-"}
    ).strip("._-")
    base_username = (safe_local_part or "googleuser")[:20]
    candidate = base_username
    suffix = 1

    while User.objects.filter(username__iexact=candidate).exists():
        suffix += 1
        suffix_part = f"-{suffix}"
        candidate = f"{base_username[: max(1, 20 - len(suffix_part))]}{suffix_part}"

    return candidate


def _find_user_for_google_email(email):
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        return user

    username_candidate = (email.split("@", 1)[0] if email else "").strip()
    if not username_candidate:
        return None

    return User.objects.filter(username__iexact=username_candidate).first()


def _sync_google_user_profile(user, profile, *, force_admin=False):
    email = (profile.get("email") or "").strip().lower()
    first_name = (profile.get("given_name") or "").strip()
    last_name = (profile.get("family_name") or "").strip()

    if email:
        user.email = email
    if first_name and not user.first_name:
        user.first_name = first_name
    if last_name and not user.last_name:
        user.last_name = last_name

    user.is_active = True
    if force_admin:
        user.is_staff = True
        user.is_superuser = True

    if not user.has_usable_password():
        user.set_unusable_password()

    user.save()
    return user


def _get_or_create_google_admin_user(profile):
    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise ValueError("Google email missing")

    user = _find_user_for_google_email(email)
    if user is None:
        user = User.objects.create_user(
            username=_generate_unique_username(email),
            email=email,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        user.set_unusable_password()

    user = _sync_google_user_profile(user, profile, force_admin=True)
    admin_group, _ = Group.objects.get_or_create(name="admin")
    user.groups.add(admin_group)
    return user


def _get_google_login_user(profile, required_role):
    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise ValueError("Google email missing")

    user = _find_user_for_google_email(email)
    if user is None:
        raise LookupError("User not found")
    if not user.is_active:
        raise PermissionError("Inactive user")

    user = _sync_google_user_profile(user, profile)
    if _detect_user_role_level(user) < ROLE_LEVELS[required_role]:
        raise PermissionError("Role denied")

    return user


def _build_admin_role_menu_context(request, *, error_message="", username=""):
    selected_role = _get_requested_role_name(request)
    return _build_role_login_context(
        request,
        selected_role,
        error_message=error_message,
        username=username,
    )


def _build_role_login_context(request, selected_role, *, error_message="", username=""):
    selected_role = _normalize_role_name(selected_role)
    next_url = _get_safe_next_url(request, fallback=_get_role_destination(selected_role))

    if selected_role == "user":
        role_hint = "The default option opens the public homepage."
    elif request.user.is_authenticated:
        role_hint = (
            f"After sign-in, the system will open this workspace: "
            f"{ROLE_LABELS[selected_role]}."
        )
    else:
        role_hint = (
            f"To continue in the {ROLE_LABELS[selected_role].lower()}, "
            f"workspace, please sign in first."
        )

    return {
        "error_message": error_message or _get_google_error_message(request),
        "google_login_url": _build_google_start_url(
            "login",
            next_url=next_url,
            role_name=selected_role,
        ),
        "google_oauth_enabled": _is_google_oauth_enabled(),
        "google_redirect_uri_hint": _build_google_redirect_uri(request),
        "next_url": next_url,
        "role_choices": ROLE_CHOICES,
        "role_hint": role_hint,
        "selected_role": selected_role,
        "selected_role_label": ROLE_LABELS[selected_role],
        "username": username,
    }


def _build_workspace_login_context(request, selected_role, *, error_message="", username=""):
    context = _build_role_login_context(
        request,
        selected_role,
        error_message=error_message,
        username=username,
    )
    context["locked_role"] = True
    return context


def _require_role(request, required_role, next_url):
    normalized_role = _normalize_role_name(required_role, default=None)
    if normalized_role is None:
        return HttpResponseForbidden("Unknown role.")

    if not request.user.is_authenticated:
        return redirect(f"/admin-panel/?next={next_url}&role={normalized_role}")

    if _detect_user_role_level(request.user) < ROLE_LEVELS[normalized_role]:
        return HttpResponseForbidden(
            "This area is available only to the required internal role."
        )

    return None


def _parse_float(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _parse_local_datetime(value):
    raw_value = (value or "").strip()
    if not raw_value:
        return None

    try:
        parsed_value = datetime.strptime(raw_value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return False

    return timezone.make_aware(parsed_value, timezone.get_current_timezone())


def _build_home_currency_rates():
    currency_rates = []

    for currency_code in SUPPORTED_CURRENCIES:
        if currency_code == HOME_RATE_QUOTE_CURRENCY:
            continue

        rate_value = None
        source_label = "Reference rate"

        direct_order = (
            Order.objects.filter(
                sell_currency=currency_code,
                buy_currency=HOME_RATE_QUOTE_CURRENCY,
                rate__gt=0,
            )
            .order_by("-created_at")
            .first()
        )
        if direct_order is not None:
            rate_value = round(direct_order.rate, 4)
            source_label = "From the latest order"
        else:
            reverse_order = (
                Order.objects.filter(
                    sell_currency=HOME_RATE_QUOTE_CURRENCY,
                    buy_currency=currency_code,
                    rate__gt=0,
                )
                .order_by("-created_at")
                .first()
            )
            if reverse_order is not None:
                rate_value = round(1 / reverse_order.rate, 4)
                source_label = "Calculated from reverse pair"

        if rate_value is None:
            rate_value = HOME_REFERENCE_RATES[currency_code]

        currency_rates.append(
            {
                "code": currency_code,
                "pair": f"{currency_code}/{HOME_RATE_QUOTE_CURRENCY}",
                "rate": rate_value,
                "quote_currency": HOME_RATE_QUOTE_CURRENCY,
                "source": source_label,
            }
        )

    return currency_rates


def _round_home_cash_rate(value, *, decimals):
    return round(max(value, 0.0001), decimals)


def _build_home_rate_lookup(currency_rates):
    rate_lookup = {
        HOME_RATE_QUOTE_CURRENCY: {
            "rate": 1.0,
            "source": "Base currency",
        }
    }
    for item in currency_rates:
        rate_lookup[item["code"]] = {
            "rate": item["rate"],
            "source": item["source"],
        }
    return rate_lookup


def _build_home_cash_quotes(rate_lookup):
    pair_specs = [
        ("USD", HOME_RATE_QUOTE_CURRENCY, "US Dollar"),
        ("EUR", HOME_RATE_QUOTE_CURRENCY, "Euro"),
        ("PLN", HOME_RATE_QUOTE_CURRENCY, "Polish Zloty"),
        ("GBP", HOME_RATE_QUOTE_CURRENCY, "Британський фунт"),
        ("EUR", "USD", "EUR/USD Cross Rate"),
    ]
    quotes = []

    for base_currency, quote_currency, label in pair_specs:
        base_rate = rate_lookup[base_currency]["rate"]
        decimals = 2 if quote_currency == HOME_RATE_QUOTE_CURRENCY else 4

        if quote_currency == HOME_RATE_QUOTE_CURRENCY:
            mid_rate = round(base_rate, 4)
            source_label = rate_lookup[base_currency]["source"]
            spread = max(0.05, base_rate * 0.0025)
        else:
            quote_rate = rate_lookup[quote_currency]["rate"]
            mid_rate = round(base_rate / quote_rate, 4)
            source_label = "Calculated from core pairs"
            spread = max(0.002, mid_rate * 0.003)

        buy_rate = _round_home_cash_rate(mid_rate - spread, decimals=decimals)
        sell_rate = _round_home_cash_rate(mid_rate + spread, decimals=decimals)
        quotes.append(
            {
                "label": label,
                "pair": f"{base_currency}/{quote_currency}",
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "buy_rate": buy_rate,
                "sell_rate": sell_rate,
                "mid_rate": mid_rate,
                "decimals": decimals,
                "calculator_text": (
                    f"1 {base_currency} ≈ {mid_rate:.{decimals}f} {quote_currency}"
                ),
                "source": source_label,
            }
        )

    return quotes


def _decorate_orders(orders):
    decorated_orders = list(orders)
    for order in decorated_orders:
        order.display_status = ORDER_STATUS_LABELS.get(order.status, order.status)
        order.pair_label = f"{order.sell_currency} \u2192 {order.buy_currency}"
        order.worker_url = f"/orders/?selected_order={order.id}"
        order.has_planned_exchange = order.planned_for is not None
    return decorated_orders


def _build_manager_queue_orders(orders):
    queue_orders = []
    for order in orders:
        if order.status not in MANAGER_QUEUE_STATUSES:
            continue

        if order.status == "confirmed":
            order.manager_state_key = "ready"
            order.manager_state = "Ready for worker handoff"
            order.manager_note = "The manager confirmed the details and passed the order into active processing."
        elif order.status == "in_progress":
            order.manager_state_key = "active"
            order.manager_state = "Already in progress"
            order.manager_note = "The order is already active, and the worker can continue the client flow right away."
        else:
            order.manager_state_key = "new"
            order.manager_state = "New manager order"
            order.manager_note = "The order has just entered the queue and is waiting to be opened by a worker."

        queue_orders.append(order)

    return queue_orders


def _build_manager_search_orders(orders):
    return [
        {
            "id": order.id,
            "pair": order.pair_label,
            "status": order.display_status,
            "manager_state": order.manager_state,
            "amount": f"{order.amount:.2f}",
            "rate": f"{order.rate:.4f}",
            "url": order.worker_url,
        }
        for order in orders
    ]


def _get_selected_order(orders, selected_order_id):
    if not orders:
        return None

    if selected_order_id is not None:
        try:
            numeric_selected_id = int(selected_order_id)
        except (TypeError, ValueError):
            numeric_selected_id = None
        if numeric_selected_id is not None:
            for order in orders:
                if order.id == numeric_selected_id:
                    return order

    for order in orders:
        if order.status in MANAGER_QUEUE_STATUSES:
            return order

    return orders[0]


def _filter_orders(orders, query):
    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return list(orders)

    tokens = [token for token in normalized_query.replace("/", " ").replace(",", " ").split() if token]
    filtered_orders = []

    for order in orders:
        haystack = " ".join(
            [
                str(order.id),
                order.sell_currency,
                order.buy_currency,
                order.pair_label,
                order.display_status,
                getattr(order, "manager_state", ""),
                f"{order.amount:.2f}",
                f"{order.rate:.4f}",
                f"{order.result:.2f}",
                timezone.localtime(order.planned_for).strftime("%d.%m.%Y %H:%M")
                if order.planned_for
                else "",
            ]
        ).lower()
        if all(token in haystack for token in tokens):
            filtered_orders.append(order)

    return filtered_orders


def _build_worker_assistant(order):
    if order is None:
        return []

    return [
        f"Привітайте клієнта і уточніть заявку #{order.id} на пару {order.pair_label}.",
        f"Підтвердіть суму {order.amount:.2f}, курс {order.rate:.4f} і очікуваний результат {order.result:.2f}.",
        (
            "Перевірте, чи клієнту зручний запланований час "
            f"{timezone.localtime(order.planned_for).strftime('%d.%m.%Y %H:%M')}."
            if order.planned_for
            else "Перевірте, чи клієнту зручний формат видачі і чи немає змін по часу."
        ),
        f"Якщо є збої або сумніви, одразу переведіть діалог на телефон {HOME_PHONE}.",
    ]


def _build_worker_quick_replies(order):
    if order is None:
        return []

    return [
        f"Доброго дня. Бачу вашу заявку #{order.id} на {order.pair_label}. Можемо підтвердити обмін?",
        f"Працюємо по курсу {order.rate:.4f}. Для суми {order.amount:.2f} результат буде {order.result:.2f}.",
        (
            "Маємо у системі запланований час "
            f"{timezone.localtime(order.planned_for).strftime('%d.%m.%Y %H:%M')}. "
            "Чи він вам підходить?"
            if order.planned_for
            else "За потреби можемо одразу погодити зручний час для обміну."
        ),
        f"Якщо зручніше, продовжимо по телефону {HOME_PHONE}.",
    ]


def _build_orders_workspace(search_query="", selected_order_id=None):
    all_orders = _decorate_orders(Order.objects.all().order_by("-created_at"))
    filtered_orders = _filter_orders(all_orders, search_query)
    selected_order = _get_selected_order(filtered_orders, selected_order_id)

    for order in filtered_orders:
        order.is_selected = selected_order is not None and order.id == selected_order.id
        order.search_blob = " ".join(
            [
                str(order.id),
                order.sell_currency,
                order.buy_currency,
                order.pair_label,
                order.display_status,
                getattr(order, "manager_state", ""),
                f"{order.amount:.2f}",
                f"{order.rate:.4f}",
                f"{order.result:.2f}",
                timezone.localtime(order.planned_for).strftime("%d.%m.%Y %H:%M")
                if order.planned_for
                else "",
            ]
        ).lower()

    queue_orders = _build_manager_queue_orders(filtered_orders)
    stats_source = filtered_orders if search_query else all_orders
    status_counts = {
        key: len([order for order in stats_source if order.status == key])
        for key in ORDER_STATUS_LABELS.keys()
    }
    return {
        "orders": filtered_orders,
        "queue_orders": queue_orders,
        "queue_count": len(queue_orders),
        "selected_order": selected_order,
        "stats": {
            "total": len(stats_source),
            "new": status_counts.get("new", 0),
            "confirmed": status_counts.get("confirmed", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "done": status_counts.get("done", 0),
            "canceled": status_counts.get("canceled", 0),
            "error": status_counts.get("error", 0),
        },
    }


def home(request):
    now = timezone.localtime()
    last_order = Order.objects.order_by("-created_at").first()
    total_orders = Order.objects.count()
    home_orders = _decorate_orders(Order.objects.all().order_by("-created_at"))
    manager_queue_orders = _build_manager_queue_orders(home_orders)
    currency_rates = _build_home_currency_rates()
    rate_lookup = _build_home_rate_lookup(currency_rates)
    cash_quotes = _build_home_cash_quotes(rate_lookup)
    calculator_rates = {
        code: data["rate"]
        for code, data in rate_lookup.items()
    }
    total_role_features = sum(len(role["features"]) for role in HOME_ROLE_DASHBOARDS)
    role_counts = {"manager": 0, "worker": 0, "admin": 0}
    for user in User.objects.prefetch_related("groups"):
        role_name = _detect_user_role_name(user)
        if role_name in role_counts:
            role_counts[role_name] += 1

    context = {
        "now": now,
        "city": HOME_CITY,
        "phone": HOME_PHONE,
        "phone_link": HOME_PHONE_LINK,
        "schedule": HOME_SCHEDULE,
        "address": HOME_ADDRESS,
        "service_tags": HOME_SERVICE_TAGS,
        "benefits": HOME_BENEFITS,
        "process_steps": HOME_PROCESS_STEPS,
        "testimonials": HOME_TESTIMONIALS,
        "service_access": HOME_SERVICE_ACCESS,
        "last_order": last_order,
        "total_orders": total_orders,
        "home_orders": home_orders,
        "manager_queue_orders": manager_queue_orders,
        "manager_queue_count": len(manager_queue_orders),
        "manager_search_orders": _build_manager_search_orders(manager_queue_orders),
        "currency_rates": currency_rates,
        "currency_rates_count": len(currency_rates),
        "cash_quotes": cash_quotes,
        "featured_quotes": cash_quotes[:4],
        "calculator_currencies": SUPPORTED_CURRENCIES,
        "calculator_rates": calculator_rates,
        "role_dashboards": HOME_ROLE_DASHBOARDS,
        "role_dashboards_count": len(HOME_ROLE_DASHBOARDS),
        "total_role_features": total_role_features,
        "role_counts": role_counts,
        "active_staff": role_counts["worker"] + role_counts["manager"] + role_counts["admin"],
        "team": TEAM_SEED,
    }
    return render(request, "home.html", context)


def admin_role_menu(request):
    if request.method == "POST":
        selected_role = _get_requested_role_name(request)
        return redirect(f"/admin-panel/role/{selected_role}/")

    context = _build_admin_role_menu_context(request)
    return render(request, "admin_role_menu.html", context)


def admin_login(request):
    if request.user.is_authenticated and _detect_user_role_level(request.user) >= ROLE_LEVELS["worker"]:
        return redirect(_get_safe_next_url(request, fallback=_get_role_destination(_get_requested_role_name(request, default="worker"))))

    context = _build_admin_role_menu_context(request)

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        context["username"] = username

        user = authenticate(request, username=username, password=password)
        if user is None:
            context["error_message"] = "The username or password is incorrect."
        elif not user.is_active:
            context["error_message"] = "This account is currently inactive."
        elif _detect_user_role_level(user) < ROLE_LEVELS["worker"]:
            context["error_message"] = "This account does not have access to the internal workspace."
        else:
            login(request, user)
            request.session["selected_role"] = _detect_user_role_name(user) or "user"
            return redirect(context["next_url"])

    return render(request, "admin_role_menu.html", context)


def admin_register(request):
    if request.user.is_authenticated and _detect_user_role_level(request.user) >= ROLE_LEVELS["admin"]:
        return redirect("/admin/")

    next_url = _get_safe_next_url(request)
    context = {
        "error_message": _get_google_error_message(request),
        "google_oauth_enabled": _is_google_oauth_enabled(),
        "google_redirect_uri_hint": _build_google_redirect_uri(request),
        "google_register_url": _build_google_start_url(
            "register_admin",
            next_url=next_url,
            role_name="admin",
        ),
        "next_url": next_url,
        "username": "",
    }

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        password_confirm = request.POST.get("password_confirm") or ""
        context["username"] = username

        if not username:
            context["error_message"] = "Please enter a username for the new account."
        elif not password:
            context["error_message"] = "Please enter a password."
        elif password != password_confirm:
            context["error_message"] = "The passwords do not match."
        elif User.objects.filter(username__iexact=username).exists():
            context["error_message"] = "An account with this username already exists."
        else:
            user = User.objects.create_user(
                username=username,
                password=password,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            admin_group, _ = Group.objects.get_or_create(name="admin")
            user.groups.add(admin_group)

            login(request, user)
            request.session["selected_role"] = "admin"
            return redirect(context["next_url"])

    return render(request, "admin_register.html", context)


def admin_password_reset(request):
    context = {
        "error_message": "",
        "success_message": "",
        "email": "",
    }

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        context["email"] = email
        form = PasswordResetForm({"email": email})
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="admin_password_reset_email.txt",
                subject_template_name="admin_password_reset_subject.txt",
            )
            context["success_message"] = (
                "If this email address exists in the system, a reset link has already been sent."
            )
        else:
            context["error_message"] = "Please enter a valid email address."

    return render(request, "admin_password_reset.html", context)


def google_auth_start(request):
    intent = (request.GET.get("intent") or "login").strip().lower()
    role_name = _get_requested_role_name(request, default="worker")

    if intent == "register_admin":
        role_name = "admin"
        next_url = _get_safe_next_url(request, fallback="/admin/")
    else:
        next_url = _get_safe_next_url(request, fallback=_get_role_destination(role_name))

    if intent not in {"login", "register_admin"}:
        return redirect(
            _build_google_return_url(
                "login",
                error_code="google_login_failed",
                next_url=next_url,
                role_name=role_name,
            )
        )

    if not _is_google_oauth_enabled():
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_not_configured",
                next_url=next_url,
                role_name=role_name,
            )
        )

    state = secrets.token_urlsafe(32)
    request.session[GOOGLE_OAUTH_SESSION_KEY] = {
        "intent": intent,
        "next_url": next_url,
        "role_name": role_name,
        "state": state,
    }

    authorize_params = {
        "client_id": getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""),
        "redirect_uri": _build_google_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect(f"{GOOGLE_OAUTH_AUTHORIZE_URL}?{urlencode(authorize_params)}")


def google_auth_callback(request):
    oauth_payload = request.session.pop(GOOGLE_OAUTH_SESSION_KEY, None)
    if not oauth_payload:
        return redirect(
            _build_google_return_url(
                "login",
                error_code="google_state_invalid",
                next_url="/orders/",
                role_name="worker",
            )
        )

    intent = oauth_payload.get("intent") or "login"
    role_name = _normalize_role_name(oauth_payload.get("role_name"), default="worker")
    if intent == "register_admin":
        role_name = "admin"

    fallback_next_url = "/admin/" if intent == "register_admin" else _get_role_destination(role_name)
    next_url = _get_local_next_url(oauth_payload.get("next_url"), fallback=fallback_next_url)

    if request.GET.get("error"):
        error_code = "google_access_denied" if request.GET.get("error") == "access_denied" else "google_login_failed"
        return redirect(
            _build_google_return_url(
                intent,
                error_code=error_code,
                next_url=next_url,
                role_name=role_name,
            )
        )

    state = (request.GET.get("state") or "").strip()
    if not state or state != oauth_payload.get("state"):
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_state_invalid",
                next_url=next_url,
                role_name=role_name,
            )
        )

    code = (request.GET.get("code") or "").strip()
    if not code:
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_login_failed",
                next_url=next_url,
                role_name=role_name,
            )
        )

    try:
        profile = _fetch_google_profile(request, code)
    except ValueError:
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_profile_failed",
                next_url=next_url,
                role_name=role_name,
            )
        )

    try:
        if intent == "register_admin":
            user = _get_or_create_google_admin_user(profile)
            selected_role = "admin"
        else:
            user = _get_google_login_user(profile, role_name)
            selected_role = role_name
    except LookupError:
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_user_not_found",
                next_url=next_url,
                role_name=role_name,
            )
        )
    except PermissionError:
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_role_denied",
                next_url=next_url,
                role_name=role_name,
            )
        )
    except ValueError:
        return redirect(
            _build_google_return_url(
                intent,
                error_code="google_email_missing",
                next_url=next_url,
                role_name=role_name,
            )
        )

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["selected_role"] = selected_role
    return redirect(next_url)


def enter_admin_role(request, role_name):
    normalized_role = _normalize_role_name(role_name, default=None)
    if normalized_role is None:
        return HttpResponseForbidden("Unknown role.")

    if normalized_role == "user":
        request.session["selected_role"] = "user"
        return redirect("/")

    if not request.user.is_authenticated:
        return redirect(
            f"/admin-panel/?next=/admin-panel/role/{normalized_role}/"
            f"&role={normalized_role}"
        )

    required_level = ROLE_LEVELS.get(normalized_role)
    user_level = _detect_user_role_level(request.user)
    if user_level < required_level:
        return HttpResponseForbidden(
            "Access denied: your role does not have permission to open this area."
        )

    request.session["selected_role"] = normalized_role
    return redirect(_get_role_destination(normalized_role))


def orders_page(request):
    search_query = (request.GET.get("q") or "").strip()
    currency_rates = _build_home_currency_rates()
    rate_lookup = _build_home_rate_lookup(currency_rates)
    cash_quotes = _build_home_cash_quotes(rate_lookup)
    workspace = _build_orders_workspace()
    return render(
        request,
        "orders.html",
        {
            "cash_quotes": cash_quotes,
            "search_query": search_query,
            "queue_orders": workspace["queue_orders"],
            "queue_count": workspace["queue_count"],
        },
    )


def worker_page(request):
    if not request.user.is_authenticated:
        context = _build_workspace_login_context(request, "worker")
        return render(request, "role_workspace_login.html", context)

    guard = _require_role(request, "worker", "/worker/")
    if guard is not None:
        return guard

    error_message = ""
    success_message = ""
    search_query = (request.GET.get("q") or "").strip()
    form_data = {
        "sell_currency": "USD",
        "buy_currency": "UAH",
        "amount": "",
        "rate": "",
        "planned_for": "",
    }

    if request.method == "POST":
        sell_currency = (request.POST.get("sell_currency") or "").strip().upper()
        buy_currency = (request.POST.get("buy_currency") or "").strip().upper()
        amount_value = _parse_float(request.POST.get("amount"))
        rate_value = _parse_float(request.POST.get("rate"))
        planned_for_value = _parse_local_datetime(request.POST.get("planned_for"))

        form_data.update(
            {
                "sell_currency": sell_currency,
                "buy_currency": buy_currency,
                "amount": request.POST.get("amount") or "",
                "rate": request.POST.get("rate") or "",
                "planned_for": request.POST.get("planned_for") or "",
            }
        )

        if sell_currency not in SUPPORTED_CURRENCIES:
            error_message = "Please choose the sell currency."
        elif buy_currency not in SUPPORTED_CURRENCIES:
            error_message = "Please choose the buy currency."
        elif sell_currency == buy_currency:
            error_message = "Sell and buy currencies must be different."
        elif amount_value is None or amount_value <= 0:
            error_message = "Please enter a valid amount."
        elif rate_value is None or rate_value <= 0:
            error_message = "Please enter a valid exchange rate."
        elif planned_for_value is False:
            error_message = "Please enter a valid planned date and time."
        else:
            result_value = round(amount_value * rate_value, 4)
            created_order = Order.objects.create(
                sell_currency=sell_currency,
                buy_currency=buy_currency,
                amount=amount_value,
                rate=rate_value,
                result=result_value,
                planned_for=planned_for_value,
                status="new",
            )
            return redirect(f"/worker/?created=1&selected_order={created_order.id}")

    if request.GET.get("created") == "1":
        success_message = "The order has been created."
    elif request.GET.get("updated") == "1":
        success_message = "The order status has been updated."
    elif request.GET.get("error") == "status":
        error_message = "The selected status is not valid."

    workspace = _build_orders_workspace(search_query, request.GET.get("selected_order"))
    context = {
        **workspace,
        "currencies": SUPPORTED_CURRENCIES,
        "status_choices": list(ORDER_STATUS_LABELS.items()),
        "error_message": error_message,
        "success_message": success_message,
        "form_data": form_data,
        "worker_assistant_messages": _build_worker_assistant(workspace["selected_order"]),
        "worker_quick_replies": _build_worker_quick_replies(workspace["selected_order"]),
        "support_phone": HOME_PHONE,
        "support_phone_link": HOME_PHONE_LINK,
        "search_query": search_query,
    }
    return render(request, "worker.html", context)


def manager_page(request):
    if not request.user.is_authenticated:
        context = _build_workspace_login_context(request, "manager")
        return render(request, "role_workspace_login.html", context)

    guard = _require_role(request, "manager", "/manager/")
    if guard is not None:
        return guard

    error_message = ""
    success_message = ""
    search_query = (request.GET.get("q") or "").strip()
    if request.GET.get("updated") == "1":
        success_message = "The order status has been updated."
    elif request.GET.get("error") == "status":
        error_message = "The selected status is not valid."

    workspace = _build_orders_workspace(search_query, request.GET.get("selected_order"))
    context = {
        **workspace,
        "status_choices": list(ORDER_STATUS_LABELS.items()),
        "error_message": error_message,
        "success_message": success_message,
        "search_query": search_query,
    }
    return render(request, "manager.html", context)


def order_status_update(request, order_id):
    next_path = _get_local_next_url(request.POST.get("next"), fallback="/worker/")
    guard = _require_role(request, "worker", next_path)
    if guard is not None:
        return guard

    if request.method != "POST":
        return redirect(next_path)

    new_status = (request.POST.get("status") or "").strip()
    if new_status not in ORDER_STATUS_LABELS:
        return redirect(f"{next_path}?error=status&selected_order={order_id}")

    Order.objects.filter(id=order_id).update(status=new_status)
    return redirect(f"{next_path}?updated=1&selected_order={order_id}")


class OrderViewSet(ModelViewSet):
    queryset = Order.objects.all().order_by("-created_at")
    serializer_class = OrderSerializer









