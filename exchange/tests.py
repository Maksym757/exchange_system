from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Order


class HomePageRoleDashboardTests(TestCase):
    def test_home_page_shows_currency_list_and_admin_access(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Список курсів валют")
        self.assertContains(response, "USD/UAH")
        self.assertContains(response, "EUR/UAH")
        self.assertContains(response, "Працівник")
        self.assertContains(response, "Менеджер")
        self.assertContains(response, "Адмін")
        self.assertContains(response, "Створення нового замовлення на обмін")
        self.assertContains(response, "Перейти як працівник")
        self.assertContains(response, "Перейти як менеджер")
        self.assertContains(response, "/admin-panel/?role=admin")
        self.assertContains(response, "Реєстрація нового адміністратора")
        self.assertContains(response, "Контроль кількості адміністраторів")
        self.assertContains(response, "/admin-panel/register/")
        self.assertContains(response, "/admin-panel/password-reset/")

    def test_home_page_uses_latest_order_rate_for_currency_list(self):
        Order.objects.create(
            sell_currency="USD",
            buy_currency="UAH",
            amount=100,
            rate=40,
            result=4000,
            status="new",
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "40,0000")
        self.assertContains(response, "З останньої заявки")


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="google-client-id",
    GOOGLE_OAUTH_CLIENT_SECRET="google-client-secret",
)
class GoogleAuthFlowTests(TestCase):
    def test_register_page_shows_google_button(self):
        response = self.client.get("/admin-panel/register/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/auth/google/start/?intent=register_admin")
        self.assertContains(response, "Continue with Google")

    def test_google_start_redirects_to_google_authorize_url(self):
        response = self.client.get(
            "/auth/google/start/?intent=login&role=admin&next=/admin-panel/role/admin/"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com/o/oauth2/v2/auth", response["Location"])

        session = self.client.session
        self.assertIn("google_oauth_state", session)
        self.assertEqual(session["google_oauth_state"]["intent"], "login")
        self.assertEqual(session["google_oauth_state"]["role_name"], "admin")

    @patch(
        "exchange.views._fetch_google_profile",
        return_value={
            "email": "chief@example.com",
            "given_name": "Chief",
            "family_name": "Admin",
        },
    )
    def test_google_register_callback_creates_admin_and_logs_in(self, mocked_profile):
        session = self.client.session
        session["google_oauth_state"] = {
            "intent": "register_admin",
            "next_url": "/admin/",
            "role_name": "admin",
            "state": "state-123",
        }
        session.save()

        response = self.client.get(
            "/auth/google/callback/?state=state-123&code=test-code"
        )

        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
        user = User.objects.get(email="chief@example.com")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.groups.filter(name="admin").exists())
        self.assertEqual(self.client.session["selected_role"], "admin")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.id))
        mocked_profile.assert_called_once()

    @patch(
        "exchange.views._fetch_google_profile",
        return_value={
            "email": "worker@example.com",
            "given_name": "Worker",
            "family_name": "User",
        },
    )
    def test_google_login_callback_logs_in_existing_matching_user(self, mocked_profile):
        user = User.objects.create_user(
            username="worker",
            email="worker@example.com",
            password="strong-pass-123",
            is_active=True,
        )

        session = self.client.session
        session["google_oauth_state"] = {
            "intent": "login",
            "next_url": "/orders/",
            "role_name": "worker",
            "state": "state-456",
        }
        session.save()

        response = self.client.get(
            "/auth/google/callback/?state=state-456&code=test-code"
        )

        self.assertRedirects(response, "/orders/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["selected_role"], "worker")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.id))
        mocked_profile.assert_called_once()


class RoleEntryFlowTests(TestCase):
    def test_user_role_redirects_home_immediately(self):
        response = self.client.get("/admin-panel/role/user/")

        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_worker_role_redirects_guest_to_login(self):
        response = self.client.get("/admin-panel/role/worker/")

        self.assertRedirects(
            response,
            "/admin-panel/?next=/admin-panel/role/worker/&role=worker",
            fetch_redirect_response=False,
        )

    def test_orders_shows_rates_and_worker_queue(self):
        Order.objects.create(
            sell_currency="USD",
            buy_currency="UAH",
            amount=100,
            rate=40,
            result=4000,
            status="new",
        )

        response = self.client.get("/orders/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пошук курсу валют")
        self.assertContains(response, "USD/UAH")
        self.assertContains(response, "Робочі замовлення працівника")
        self.assertContains(response, "Відкрити в роботі")

    def test_worker_page_shows_admin_style_login_for_guest(self):
        response = self.client.get("/worker/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вхід у робочий простір")
        self.assertContains(response, 'value="worker"')
        self.assertContains(response, 'action="/admin-panel/auth/"')

    def test_manager_page_shows_admin_style_login_for_guest(self):
        response = self.client.get("/manager/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вхід у робочий простір")
        self.assertContains(response, 'value="manager"')
        self.assertContains(response, 'action="/admin-panel/auth/"')

    def test_worker_can_log_in_and_enter_orders_workspace(self):
        User.objects.create_user(
            username="worker",
            password="strong-pass-123",
            is_active=True,
        )

        login_response = self.client.post(
            "/admin-panel/auth/?next=/admin-panel/role/worker/",
            {
                "username": "worker",
                "password": "strong-pass-123",
                "next": "/admin-panel/role/worker/",
                "role": "worker",
            },
        )

        self.assertRedirects(
            login_response,
            "/admin-panel/role/worker/",
            fetch_redirect_response=False,
        )
        role_response = self.client.get("/admin-panel/role/worker/")
        self.assertRedirects(role_response, "/worker/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["selected_role"], "worker")

    def test_worker_can_render_orders_page_with_status_label(self):
        Order.objects.create(
            sell_currency="USD",
            buy_currency="UAH",
            amount=100,
            rate=40,
            result=4000,
            status="new",
        )
        User.objects.create_user(
            username="worker",
            password="strong-pass-123",
            is_active=True,
        )
        self.client.login(username="worker", password="strong-pass-123")

        response = self.client.get("/worker/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Опрацювання заявок на обмін")
        self.assertContains(response, "USD")
        self.assertContains(response, "Вибране замовлення")
        self.assertContains(response, '/admin-panel/?role=admin')

    def test_worker_can_create_order_with_planned_datetime(self):
        User.objects.create_user(
            username="worker",
            password="strong-pass-123",
            is_active=True,
        )
        self.client.login(username="worker", password="strong-pass-123")

        response = self.client.post(
            "/worker/",
            {
                "sell_currency": "USD",
                "buy_currency": "UAH",
                "amount": "100",
                "rate": "41.5",
                "planned_for": "2026-04-10T14:30",
            },
        )

        created_order = Order.objects.latest("id")
        self.assertRedirects(
            response,
            f"/worker/?created=1&selected_order={created_order.id}",
            fetch_redirect_response=False,
        )
        self.assertIsNotNone(created_order.planned_for)
        localized_planned_for = timezone.localtime(created_order.planned_for)
        self.assertEqual(localized_planned_for.strftime("%Y-%m-%dT%H:%M"), "2026-04-10T14:30")

    def test_manager_role_opens_manager_workspace(self):
        User.objects.create_user(
            username="manager",
            password="strong-pass-123",
            is_active=True,
        )

        login_response = self.client.post(
            "/admin-panel/auth/?next=/admin-panel/role/manager/",
            {
                "username": "manager",
                "password": "strong-pass-123",
                "next": "/admin-panel/role/manager/",
                "role": "manager",
            },
        )

        self.assertRedirects(
            login_response,
            "/admin-panel/role/manager/",
            fetch_redirect_response=False,
        )
        role_response = self.client.get("/admin-panel/role/manager/")
        self.assertRedirects(role_response, "/manager/", fetch_redirect_response=False)

    def test_admin_can_log_in_and_enter_admin_workspace(self):
        User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="super-pass-123",
        )

        login_response = self.client.post(
            "/admin-panel/auth/?next=/admin-panel/role/admin/",
            {
                "username": "admin",
                "password": "super-pass-123",
                "next": "/admin-panel/role/admin/",
                "role": "admin",
            },
        )

        self.assertRedirects(
            login_response,
            "/admin-panel/role/admin/",
            fetch_redirect_response=False,
        )
        role_response = self.client.get("/admin-panel/role/admin/")
        self.assertRedirects(role_response, "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["selected_role"], "admin")


class AdminDashboardLandingTests(TestCase):
    def test_admin_index_shows_shortcuts_for_superuser(self):
        admin_user = User.objects.create_superuser(
            username="admin-dashboard",
            email="admin-dashboard@example.com",
            password="super-pass-123",
        )
        self.client.force_login(admin_user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quick access to key admin tasks")
        self.assertContains(response, "Create a new administrator")
        self.assertContains(response, "Reset an administrator password")
        self.assertContains(response, "Switch service roles")
        self.assertContains(response, "Review administrator accounts")
        self.assertContains(response, "/admin-panel/register/")
        self.assertContains(response, "/admin-panel/password-reset/")
        self.assertContains(response, "/admin/auth/user/")
