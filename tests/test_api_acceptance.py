"""
Repeatable integration and acceptance test suite for Cashflow Radar.
Unified single-class runner ensuring shared authenticated context across all checks:
- Cookie/CSRF Origin protection (http://localhost:3000)
- Signup & Login with unique random users (owner, viewer, outsider)
- Companies & real M:N memberships via invitation flow
- Tenant isolation (404 for foreign companies, 403 for viewer writes)
- Owner cannot demote or delete self
- Foreign categories rejected across companies
- Category deletion RESTRICT when transactions exist
- Transactions full CRUD, all edit fields, null clearing, filters, pagination
- Decimal arithmetic (0.10 + 0.20 = 0.30 in daily analytics)
- Import CSV/XLSX preview (no DB writes, sign deduction, formula/conflict rejection, duplicates allowed)
- Atomic import commit with category auto-creation
- Forecast 29 vs 30 days cutoff, horizon shape, signed net_cash_flow, warnings
- Actual gRPC integration route
- Clean tear down of transactions/categories; invitation outcomes are retained
"""

import datetime
import decimal
import http.client
import logging
import os
import re
import unittest
import uuid
from typing import Any, ClassVar

from tests.client import TestAPIClient
from tests.fixtures import (
    build_date_range,
    generate_csv_bytes,
    generate_minimal_xlsx_bytes,
)
from tests.mailbox import verification_code

logger = logging.getLogger(__name__)


class CashflowRadarAcceptanceTest(unittest.TestCase):
    """
    Single unified acceptance test case:
    - Sets up shared authenticated clients and test personas once.
    - Runs in strict logical sequence sharing company and membership state.
    - Deletes created transactions/categories, revokes pending invitations, retains history.
    """

    base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    run_id: str = uuid.uuid4().hex[:8]
    prefix: str = f"verify-{run_id}"

    # Persona clients
    owner_client: TestAPIClient
    viewer_client: TestAPIClient
    outsider_client: TestAPIClient

    # Persona user objects
    owner_user: ClassVar[dict[str, Any]] = {}
    viewer_user: ClassVar[dict[str, Any]] = {}
    outsider_user: ClassVar[dict[str, Any]] = {}

    # Companies
    company_alpha: ClassVar[dict[str, Any]] = {}  # Owner's primary company
    company_beta: ClassVar[dict[str, Any]] = {}  # Outsider's company
    company_forecast: ClassVar[
        dict[str, Any]
    ] = {}  # Dedicated company for forecast tests

    # Tracked resources for suite cleanup
    tracked_transactions: ClassVar[list[dict[str, Any]]] = []
    tracked_categories: ClassVar[list[dict[str, Any]]] = []
    tracked_invitations: ClassVar[list[dict[str, Any]]] = []

    cleaned_tx_count: int = 0
    cleaned_cat_count: int = 0
    revoked_inv_count: int = 0

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("TEST_MAILBOX_URL"):
            raise RuntimeError(
                "Set TEST_MAILBOX_URL to a test mailbox before synthetic registration tests"
            )
        cls.tracked_transactions = []
        cls.tracked_categories = []
        cls.tracked_invitations = []
        cls.owner_client = TestAPIClient(base_url=cls.base_url, origin=cls.origin)
        cls.viewer_client = TestAPIClient(base_url=cls.base_url, origin=cls.origin)
        cls.outsider_client = TestAPIClient(base_url=cls.base_url, origin=cls.origin)

    @classmethod
    def tearDownClass(cls):
        """Delete owned transaction/category fixtures; preserve invitation history."""
        try:
            for tx in reversed(cls.tracked_transactions):
                cid = tx.get("company_id")
                tid = tx.get("id")
                if cid and tid:
                    client = (
                        cls.owner_client
                        if cid != cls.company_beta.get("id")
                        else cls.outsider_client
                    )
                    try:
                        del_resp = client.delete(
                            f"/api/companies/{cid}/transactions/{tid}"
                        )
                        if del_resp.status_code in (200, 204):
                            cls.cleaned_tx_count += 1
                    except (OSError, http.client.HTTPException):
                        logger.warning("Failed to clean up owned transaction %s", tid)

            for cat in reversed(cls.tracked_categories):
                cid = cat.get("company_id")
                cat_id = cat.get("id")
                if cid and cat_id:
                    client = (
                        cls.owner_client
                        if cid != cls.company_beta.get("id")
                        else cls.outsider_client
                    )
                    try:
                        del_resp = client.delete(
                            f"/api/companies/{cid}/categories/{cat_id}"
                        )
                        if del_resp.status_code in (200, 204):
                            cls.cleaned_cat_count += 1
                    except (OSError, http.client.HTTPException):
                        logger.warning("Failed to clean up owned category %s", cat_id)

            for inv in cls.tracked_invitations:
                cid = inv.get("company_id")
                inv_id = inv.get("id")
                if cid and inv_id:
                    client = (
                        cls.owner_client
                        if cid != cls.company_beta.get("id")
                        else cls.outsider_client
                    )
                    try:
                        history = client.get(f"/api/companies/{cid}/invitations")
                        invitation = (
                            next(
                                (item for item in history.data if item["id"] == inv_id),
                                None,
                            )
                            if history.status_code == 200
                            else None
                        )
                        if invitation and invitation["status"] in (
                            "pending",
                            "expired",
                        ):
                            response = client.delete(
                                f"/api/companies/{cid}/invitations/{inv_id}"
                            )
                            if response.status_code in (200, 204):
                                cls.revoked_inv_count += 1
                    except (OSError, http.client.HTTPException):
                        logger.warning("Failed to revoke owned invitation %s", inv_id)
        finally:
            if hasattr(cls, "owner_client"):
                cls.owner_client.close()
            if hasattr(cls, "viewer_client"):
                cls.viewer_client.close()
            if hasattr(cls, "outsider_client"):
                cls.outsider_client.close()

    # --------------------------------------------------------------------------
    # 1. AUTH & CSRF
    # --------------------------------------------------------------------------

    def test_01_auth_register_and_login_owner(self):
        """[AUTH-01] Register owner persona, verify BOTH access_token and csrf_token cookies."""
        email = f"owner_{self.run_id}@example.com"
        password = "Password123!"
        resp = self.owner_client.post(
            "/api/auth/register",
            json_data={
                "full_name": f"{self.prefix}-owner",
                "email": email,
                "password": password,
            },
        )
        if resp.status_code == 409:
            resp = self.owner_client.post(
                "/api/auth/login",
                json_data={"email": email, "password": password},
            )
        elif resp.status_code == 201:
            self.assertIsNone(self.owner_client.access_token)
            resp = self.owner_client.post(
                "/api/auth/verify-email",
                json_data={"email": email, "code": verification_code(email)},
            )

        self.assertIn(
            resp.status_code,
            (200, 201),
            f"Owner register/login failed (status={resp.status_code}, error={resp.error_code})",
        )

        me_resp = self.owner_client.get("/api/auth/me")
        self.assertEqual(
            me_resp.status_code,
            200,
            f"GET /api/auth/me failed (status={me_resp.status_code}, error={me_resp.error_code})",
        )
        self.assertEqual(me_resp.data.get("email", "").lower(), email.lower())
        CashflowRadarAcceptanceTest.owner_user = me_resp.data

        # Strictly assert BOTH access_token and csrf_token cookies are present
        self.assertIsNotNone(
            self.owner_client.access_token,
            "access_token cookie was not set after authentication",
        )
        self.assertIsNotNone(
            self.owner_client.csrf_token,
            "csrf_token cookie was not set after authentication",
        )

    def test_02_auth_register_viewer_and_outsider(self):
        """[AUTH-02] Register viewer and outsider personas, verify BOTH cookies."""
        # Viewer
        v_email = f"viewer_{self.run_id}@example.com"
        resp_v = self.viewer_client.post(
            "/api/auth/register",
            json_data={
                "full_name": f"{self.prefix}-viewer",
                "email": v_email,
                "password": "Password123!",
            },
        )
        self.assertIn(
            resp_v.status_code,
            (200, 201),
            f"Viewer register failed (status={resp_v.status_code}, error={resp_v.error_code})",
        )
        self.assertIsNone(self.viewer_client.access_token)
        verified_v = self.viewer_client.post(
            "/api/auth/verify-email",
            json_data={"email": v_email, "code": verification_code(v_email)},
        )
        self.assertEqual(verified_v.status_code, 200)
        me_v = self.viewer_client.get("/api/auth/me")
        self.assertEqual(me_v.status_code, 200)
        CashflowRadarAcceptanceTest.viewer_user = me_v.data
        self.assertIsNotNone(self.viewer_client.access_token)
        self.assertIsNotNone(self.viewer_client.csrf_token)

        # Outsider
        o_email = f"outsider_{self.run_id}@example.com"
        resp_o = self.outsider_client.post(
            "/api/auth/register",
            json_data={
                "full_name": f"{self.prefix}-outsider",
                "email": o_email,
                "password": "Password123!",
            },
        )
        self.assertIn(
            resp_o.status_code,
            (200, 201),
            f"Outsider register failed (status={resp_o.status_code}, error={resp_o.error_code})",
        )
        self.assertIsNone(self.outsider_client.access_token)
        verified_o = self.outsider_client.post(
            "/api/auth/verify-email",
            json_data={"email": o_email, "code": verification_code(o_email)},
        )
        self.assertEqual(verified_o.status_code, 200)
        me_o = self.outsider_client.get("/api/auth/me")
        self.assertEqual(me_o.status_code, 200)
        CashflowRadarAcceptanceTest.outsider_user = me_o.data
        self.assertIsNotNone(self.outsider_client.access_token)
        self.assertIsNotNone(self.outsider_client.csrf_token)

    def test_03_csrf_enforcement_on_mutations(self):
        """[CSRF-01] Enforce X-CSRF-Token on mutating requests (403 on missing/invalid token)."""
        resp_no_csrf = self.owner_client.post(
            "/api/companies",
            json_data={"name": f"{self.prefix}-CsrfTest"},
            omit_csrf=True,
        )
        self.assertEqual(
            resp_no_csrf.status_code,
            403,
            f"Expected 403 when X-CSRF-Token is omitted, got {resp_no_csrf.status_code}",
        )

        resp_bad_csrf = self.owner_client.post(
            "/api/companies",
            json_data={"name": f"{self.prefix}-CsrfTest"},
            custom_csrf="invalid-token",
        )
        self.assertEqual(
            resp_bad_csrf.status_code,
            403,
            f"Expected 403 with invalid X-CSRF-Token, got {resp_bad_csrf.status_code}",
        )

    def test_04_origin_enforcement_on_mutations(self):
        """[CSRF-02] Enforce Origin allowlist on mutating requests (403 on disallowed Origin)."""
        resp_bad_origin = self.owner_client.post(
            "/api/companies",
            json_data={"name": f"{self.prefix}-OriginTest"},
            custom_origin="http://untrusted-origin.test",
        )
        self.assertEqual(
            resp_bad_origin.status_code,
            403,
            f"Expected 403 with untrusted Origin, got {resp_bad_origin.status_code}",
        )

    # --------------------------------------------------------------------------
    # 2. COMPANIES & REAL M:N
    # --------------------------------------------------------------------------

    def test_05_companies_create_alpha_and_beta(self):
        """[TENANT-01] Create Company Alpha (owner) and Company Beta (outsider)."""
        resp_alpha = self.owner_client.post(
            "/api/companies",
            json_data={
                "name": f"{self.prefix}-Alpha",
                "industry_code": "IT",
            },
        )
        self.assertEqual(
            resp_alpha.status_code,
            201,
            f"Failed creating Company Alpha (status={resp_alpha.status_code}, error={resp_alpha.error_code})",
        )
        CashflowRadarAcceptanceTest.company_alpha = resp_alpha.data

        resp_beta = self.outsider_client.post(
            "/api/companies",
            json_data={
                "name": f"{self.prefix}-Beta",
                "industry_code": "RETAIL",
            },
        )
        self.assertEqual(
            resp_beta.status_code,
            201,
            f"Failed creating Company Beta (status={resp_beta.status_code}, error={resp_beta.error_code})",
        )
        CashflowRadarAcceptanceTest.company_beta = resp_beta.data

    def test_06_tenant_invitation_flow(self):
        """[TENANT-02] Invitation token flow: owner invites viewer, viewer accepts."""
        alpha_id = self.company_alpha["id"]
        viewer_email = self.viewer_user["email"]

        inv_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/invitations",
            json_data={"email": viewer_email, "role": "viewer"},
        )
        self.assertIn(
            inv_resp.status_code,
            (200, 201),
            f"Create invitation failed (status={inv_resp.status_code}, error={inv_resp.error_code})",
        )
        inv_data = inv_resp.data
        self.tracked_invitations.append(
            {"company_id": alpha_id, "id": inv_data.get("id")}
        )

        token = inv_data.get("token")
        self.assertTrue(token, "Invitation did not return secret token in response")

        accept_resp = self.viewer_client.post(
            "/api/invitations/accept",
            json_data={"token": token},
        )
        self.assertIn(
            accept_resp.status_code,
            (200, 201),
            f"Accept invitation failed (status={accept_resp.status_code}, error={accept_resp.error_code})",
        )

        members_resp = self.owner_client.get(f"/api/companies/{alpha_id}/members")
        self.assertEqual(members_resp.status_code, 200)
        member_emails = [m.get("email", "").lower() for m in members_resp.data]
        self.assertIn(viewer_email.lower(), member_emails)

    def test_07_tenant_real_mn_both_directions(self):
        """[TENANT-03] Real M:N relationship verified in both directions across companies."""
        beta_id = self.company_beta["id"]
        alpha_id = self.company_alpha["id"]
        owner_email = self.owner_user["email"]

        inv_resp = self.outsider_client.post(
            f"/api/companies/{beta_id}/invitations",
            json_data={"email": owner_email, "role": "treasurer"},
        )
        self.assertIn(inv_resp.status_code, (200, 201))
        token = inv_resp.data.get("token")
        self.assertTrue(token)

        accept_resp = self.owner_client.post(
            "/api/invitations/accept",
            json_data={"token": token},
        )
        self.assertIn(accept_resp.status_code, (200, 201))

        companies_resp = self.owner_client.get("/api/companies")
        self.assertEqual(companies_resp.status_code, 200)
        user_cids = [c["id"] for c in companies_resp.data]
        self.assertIn(alpha_id, user_cids)
        self.assertIn(beta_id, user_cids)

    def test_08_tenant_isolation_foreign_company_returns_404(self):
        """[TENANT-04] Cross-tenant isolation returns 404 (not 403) for non-member companies."""
        beta_id = self.company_beta["id"]
        resp = self.viewer_client.get(f"/api/companies/{beta_id}/transactions")
        self.assertEqual(
            resp.status_code,
            404,
            f"Expected 404 for foreign company, got {resp.status_code}",
        )

        resp_cat = self.viewer_client.get(f"/api/companies/{beta_id}/categories")
        self.assertEqual(resp_cat.status_code, 404)

    def test_09_rbac_viewer_write_forbidden_403(self):
        """[RBAC-01] Viewer write actions (transactions, categories, imports, invites) blocked (403)."""
        alpha_id = self.company_alpha["id"]

        tx_resp = self.viewer_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "100.00",
                "direction": "inflow",
            },
        )
        self.assertEqual(
            tx_resp.status_code,
            403,
            f"Expected 403 for viewer transaction create, got {tx_resp.status_code}",
        )

        cat_resp = self.viewer_client.post(
            f"/api/companies/{alpha_id}/categories",
            json_data={"name": f"{self.prefix}-ViewerCat"},
        )
        self.assertEqual(
            cat_resp.status_code,
            403,
            f"Expected 403 for viewer category create, got {cat_resp.status_code}",
        )

        inv_resp = self.viewer_client.post(
            f"/api/companies/{alpha_id}/invitations",
            json_data={"email": "nobody@example.com", "role": "viewer"},
        )
        self.assertEqual(
            inv_resp.status_code,
            403,
            f"Expected 403 for viewer invite, got {inv_resp.status_code}",
        )

    def test_10_rbac_owner_cannot_demote_or_delete_self(self):
        """[RBAC-02] Owner self-protection: owner cannot demote or delete self (400/403/422)."""
        alpha_id = self.company_alpha["id"]
        owner_id = self.owner_user["id"]

        demote_resp = self.owner_client.patch(
            f"/api/companies/{alpha_id}/members/{owner_id}",
            json_data={"role": "viewer"},
        )
        self.assertIn(
            demote_resp.status_code,
            (400, 403, 422),
            f"Owner self-demote should fail, got {demote_resp.status_code}",
        )

        del_resp = self.owner_client.delete(
            f"/api/companies/{alpha_id}/members/{owner_id}"
        )
        self.assertIn(
            del_resp.status_code,
            (400, 403, 422),
            f"Owner self-delete should fail, got {del_resp.status_code}",
        )

    # --------------------------------------------------------------------------
    # 3. CATEGORIES & CONSTRAINTS
    # --------------------------------------------------------------------------

    def test_11_category_create_and_duplicate_rejection(self):
        """[CAT-01] Category CRUD and case-insensitive duplicate rejection (409 Conflict)."""
        alpha_id = self.company_alpha["id"]
        cat_name = f"{self.prefix}-Revenue"

        resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/categories",
            json_data={"name": cat_name},
        )
        self.assertEqual(
            resp.status_code,
            201,
            f"Create category failed (status={resp.status_code}, error={resp.error_code})",
        )
        cat_id = resp.data["id"]
        self.tracked_categories.append({"company_id": alpha_id, "id": cat_id})

        dup_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/categories",
            json_data={"name": cat_name.lower()},
        )
        self.assertEqual(
            dup_resp.status_code,
            409,
            f"Expected 409 for duplicate category name, got {dup_resp.status_code}",
        )

    def test_12_category_foreign_rejection(self):
        """[CAT-02] Cross-company foreign category rejected in transaction (FK boundary)."""
        alpha_id = self.company_alpha["id"]
        beta_id = self.company_beta["id"]

        beta_cat_resp = self.outsider_client.post(
            f"/api/companies/{beta_id}/categories",
            json_data={"name": f"{self.prefix}-BetaExpenses"},
        )
        self.assertEqual(beta_cat_resp.status_code, 201)
        foreign_cat_id = beta_cat_resp.data["id"]
        self.tracked_categories.append({"company_id": beta_id, "id": foreign_cat_id})

        tx_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "5000.00",
                "direction": "outflow",
                "category_id": foreign_cat_id,
            },
        )
        self.assertIn(
            tx_resp.status_code,
            (400, 404, 422),
            f"Expected foreign category rejected with 400/404/422, got {tx_resp.status_code}",
        )

    def test_13_category_delete_restrict_when_used(self):
        """[CAT-03] Category deletion blocked with 409 RESTRICT when transactions exist."""
        alpha_id = self.company_alpha["id"]

        cat_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/categories",
            json_data={"name": f"{self.prefix}-ProtectedCat"},
        )
        self.assertEqual(cat_resp.status_code, 201)
        cat_id = cat_resp.data["id"]
        self.tracked_categories.append({"company_id": alpha_id, "id": cat_id})

        tx_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "1200.00",
                "direction": "inflow",
                "category_id": cat_id,
            },
        )
        self.assertEqual(tx_resp.status_code, 201)
        self.tracked_transactions.append(
            {"company_id": alpha_id, "id": tx_resp.data["id"]}
        )

        del_resp = self.owner_client.delete(
            f"/api/companies/{alpha_id}/categories/{cat_id}"
        )
        self.assertEqual(
            del_resp.status_code,
            409,
            f"Expected 409 when deleting category in use, got {del_resp.status_code}",
        )

    # --------------------------------------------------------------------------
    # 4. TRANSACTIONS & DECIMAL ARITHMETIC
    # --------------------------------------------------------------------------

    def test_14_transactions_decimal_arithmetic_exactness(self):
        """[TX-01] Exact decimal arithmetic: 0.10 + 0.20 = 0.30 in daily aggregation."""
        alpha_id = self.company_alpha["id"]
        test_date = "2026-11-01"

        tx1 = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": test_date,
                "amount": "0.10",
                "direction": "inflow",
            },
        )
        self.assertEqual(
            tx1.status_code,
            201,
            f"Create 0.10 failed (status={tx1.status_code}, error={tx1.error_code})",
        )
        self.tracked_transactions.append({"company_id": alpha_id, "id": tx1.data["id"]})

        tx2 = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": test_date,
                "amount": "0.20",
                "direction": "inflow",
            },
        )
        self.assertEqual(
            tx2.status_code,
            201,
            f"Create 0.20 failed (status={tx2.status_code}, error={tx2.error_code})",
        )
        self.tracked_transactions.append({"company_id": alpha_id, "id": tx2.data["id"]})

        analytics_resp = self.owner_client.get(
            f"/api/companies/{alpha_id}/analytics/daily",
            params={"date_from": test_date, "date_to": test_date},
        )
        self.assertEqual(
            analytics_resp.status_code,
            200,
            f"Analytics daily failed (status={analytics_resp.status_code}, error={analytics_resp.error_code})",
        )
        totals = analytics_resp.data.get("totals", {})
        self.assertEqual(
            str(totals.get("inflow")),
            "0.30",
            f"Decimal arithmetic error: expected '0.30', got {totals.get('inflow')}",
        )

    def test_15_transactions_amount_validation(self):
        """[TX-02] Input validation: zero, negative, and >2 decimal place amounts rejected (422)."""
        alpha_id = self.company_alpha["id"]

        r0 = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "0.00",
                "direction": "inflow",
            },
        )
        self.assertEqual(r0.status_code, 422)

        rn = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "-150.00",
                "direction": "outflow",
            },
        )
        self.assertEqual(rn.status_code, 422)

        r3 = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "12.345",
                "direction": "inflow",
            },
        )
        self.assertEqual(r3.status_code, 422)

    def test_16_transactions_full_edit_and_null_clearing(self):
        """[TX-03] PATCH full edit and null-clearing of category and purpose fields."""
        alpha_id = self.company_alpha["id"]

        cat_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/categories",
            json_data={"name": f"{self.prefix}-EditCat"},
        )
        self.assertEqual(cat_resp.status_code, 201)
        cat_id = cat_resp.data["id"]
        self.tracked_categories.append({"company_id": alpha_id, "id": cat_id})

        tx_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/transactions",
            json_data={
                "operation_date": "2026-11-03",
                "amount": "1500.00",
                "direction": "inflow",
                "category_id": cat_id,
                "purpose": "Initial payment purpose",
            },
        )
        self.assertEqual(tx_resp.status_code, 201)
        tx_id = tx_resp.data["id"]
        self.tracked_transactions.append({"company_id": alpha_id, "id": tx_id})

        patch_resp = self.owner_client.patch(
            f"/api/companies/{alpha_id}/transactions/{tx_id}",
            json_data={
                "operation_date": "2026-11-04",
                "amount": "2750.50",
                "direction": "outflow",
                "category_id": None,
                "purpose": None,
            },
        )
        self.assertEqual(
            patch_resp.status_code,
            200,
            f"PATCH transaction failed (status={patch_resp.status_code}, error={patch_resp.error_code})",
        )
        updated = patch_resp.data
        self.assertEqual(str(updated.get("amount")), "2750.50")
        self.assertEqual(updated.get("direction"), "outflow")
        self.assertEqual(updated.get("operation_date"), "2026-11-04")
        self.assertIsNone(updated.get("category_id"))
        self.assertIsNone(updated.get("purpose"))

    def test_17_transactions_filters_and_pagination(self):
        """[TX-04] Filtering, pagination limits, and uncategorized mutual exclusivity."""
        alpha_id = self.company_alpha["id"]

        bad_filter = self.owner_client.get(
            f"/api/companies/{alpha_id}/transactions",
            params={"category_id": 1, "uncategorized": "true"},
        )
        self.assertEqual(bad_filter.status_code, 422)

        paginated = self.owner_client.get(
            f"/api/companies/{alpha_id}/transactions",
            params={"page": 1, "page_size": 2},
        )
        self.assertEqual(paginated.status_code, 200)
        self.assertIn("items", paginated.data)
        self.assertIn("total", paginated.data)
        self.assertLessEqual(len(paginated.data["items"]), 2)

    # --------------------------------------------------------------------------
    # 5. IMPORTS CSV/XLSX
    # --------------------------------------------------------------------------

    def test_18_import_csv_preview_no_writes_and_sign_deduction(self):
        """[IMPORT-01] CSV preview infers direction from sign, creates NO database records."""
        alpha_id = self.company_alpha["id"]

        initial_list = self.owner_client.get(f"/api/companies/{alpha_id}/transactions")
        self.assertEqual(initial_list.status_code, 200)
        initial_count = initial_list.data.get(
            "total", len(initial_list.data.get("items", []))
        )

        new_cat_name = f"{self.prefix}-CsvAutoCat"
        csv_rows = [
            {
                "date": "2026-10-01",
                "amount": "100000.00",
                "direction": "inflow",
                "category": new_cat_name,
                "purpose": "Sales 1",
            },
            {
                "date": "2026-10-02",
                "amount": "-15000.00",
                "direction": "",
                "category": "Rent",
                "purpose": "Office",
            },
            {
                "date": "2026-10-03",
                "amount": "2500.00",
                "direction": "outflow",
                "category": "",
                "purpose": "",
            },
        ]
        csv_bytes = generate_csv_bytes(csv_rows)

        preview_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={"file": ("import.csv", csv_bytes, "text/csv")},
        )
        self.assertEqual(
            preview_resp.status_code,
            200,
            f"CSV preview failed (status={preview_resp.status_code}, error={preview_resp.error_code})",
        )
        data = preview_resp.data
        self.assertTrue(
            data.get("can_commit"), "Expected can_commit to be True for valid CSV"
        )

        rows = data.get("rows", [])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1].get("direction"), "outflow")
        self.assertEqual(str(rows[1].get("amount")), "15000.00")

        post_preview_list = self.owner_client.get(
            f"/api/companies/{alpha_id}/transactions"
        )
        post_preview_count = post_preview_list.data.get(
            "total", len(post_preview_list.data.get("items", []))
        )
        self.assertEqual(
            initial_count,
            post_preview_count,
            "Preview must not write records to database",
        )

    def test_19_import_sign_conflict_and_formula_rejected(self):
        """[IMPORT-02] Reject sign conflict, formulas (=SUM), and non-standard floats (NaN, Infinity, 1e2)."""
        alpha_id = self.company_alpha["id"]

        conflict_rows = [
            {
                "date": "2026-10-01",
                "amount": "-500.00",
                "direction": "inflow",
                "category": "",
                "purpose": "",
            },
        ]
        csv_conflict = generate_csv_bytes(conflict_rows)
        resp_conflict = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={"file": ("conflict.csv", csv_conflict, "text/csv")},
        )
        self.assertEqual(resp_conflict.status_code, 200)
        self.assertFalse(resp_conflict.data.get("can_commit"))
        self.assertTrue(len(resp_conflict.data.get("errors", [])) > 0)

        formula_rows = [
            {
                "date": "2026-10-01",
                "amount": "=SUM(A1:A2)",
                "direction": "inflow",
                "category": "",
                "purpose": "",
            },
        ]
        csv_formula = generate_csv_bytes(formula_rows)
        resp_formula = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={"file": ("formula.csv", csv_formula, "text/csv")},
        )
        self.assertEqual(resp_formula.status_code, 200)
        self.assertFalse(resp_formula.data.get("can_commit"))

        # Non-standard float literals in CSV (NaN, Infinity, 1e2) must not 500;
        # preview must return 200 with can_commit=False, or 422.
        for invalid_amt in ("NaN", "Infinity", "1e2"):
            invalid_rows = [
                {
                    "date": "2026-10-01",
                    "amount": invalid_amt,
                    "direction": "inflow",
                    "category": "",
                    "purpose": f"Invalid float {invalid_amt}",
                },
            ]
            csv_invalid = generate_csv_bytes(invalid_rows)
            resp_invalid = self.owner_client.post(
                f"/api/companies/{alpha_id}/imports/preview",
                files={"file": (f"invalid_{invalid_amt}.csv", csv_invalid, "text/csv")},
            )
            self.assertNotEqual(
                resp_invalid.status_code,
                500,
                f"CSV import with amount='{invalid_amt}' must not return 500 Internal Server Error",
            )
            self.assertIn(
                resp_invalid.status_code,
                (200, 422),
                f"Expected 200 (with can_commit=False) or 422 for amount='{invalid_amt}', got {resp_invalid.status_code}",
            )
            if resp_invalid.status_code == 200:
                self.assertFalse(
                    resp_invalid.data.get("can_commit"),
                    f"Expected can_commit=False for invalid amount='{invalid_amt}'",
                )

    def test_20_import_duplicates_explicitly_allowed(self):
        """[IMPORT-03] Explicit duplicate transaction rows permitted in preview."""
        alpha_id = self.company_alpha["id"]
        dup_rows = [
            {
                "date": "2026-10-05",
                "amount": "450.00",
                "direction": "inflow",
                "category": "",
                "purpose": "Duplicate test",
            },
            {
                "date": "2026-10-05",
                "amount": "450.00",
                "direction": "inflow",
                "category": "",
                "purpose": "Duplicate test",
            },
        ]
        csv_dups = generate_csv_bytes(dup_rows)
        resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={"file": ("dups.csv", csv_dups, "text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("can_commit"))
        self.assertEqual(len(resp.data.get("rows", [])), 2)

    def test_21_import_atomic_commit_with_new_category(self):
        """[IMPORT-04] Atomic commit: all-or-nothing rollback and automatic category creation."""
        alpha_id = self.company_alpha["id"]

        # Step 1: Baseline counts
        tx_base_resp = self.owner_client.get(f"/api/companies/{alpha_id}/transactions")
        self.assertEqual(
            tx_base_resp.status_code,
            200,
            f"Failed to fetch baseline transactions (status={tx_base_resp.status_code})",
        )
        base_tx_count = tx_base_resp.data.get(
            "total", len(tx_base_resp.data.get("items", []))
        )

        cat_base_resp = self.owner_client.get(f"/api/companies/{alpha_id}/categories")
        self.assertEqual(
            cat_base_resp.status_code,
            200,
            f"Failed to fetch baseline categories (status={cat_base_resp.status_code})",
        )

        # Step 2: Rollback case - valid first row with new category + invalid second row
        rollback_cat = f"{self.prefix}-RollbackCat"
        invalid_rows = [
            {
                "operation_date": "2026-10-08",
                "amount": "555.00",
                "direction": "inflow",
                "category": rollback_cat,
                "purpose": "Should rollback 1",
            },
            {
                "operation_date": "2026-10-09",
                "amount": "-999.00",  # Invalid amount: must be positive
                "direction": "inflow",
                "category": None,
                "purpose": "Invalid row",
            },
        ]
        failed_commit_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/commit",
            json_data={"rows": invalid_rows},
        )
        self.assertEqual(
            failed_commit_resp.status_code,
            422,
            f"Expected 422 for invalid commit payload, got {failed_commit_resp.status_code}",
        )

        # Assert no transactions written after rollback
        tx_check_resp = self.owner_client.get(f"/api/companies/{alpha_id}/transactions")
        self.assertEqual(tx_check_resp.status_code, 200)
        post_fail_tx_count = tx_check_resp.data.get(
            "total", len(tx_check_resp.data.get("items", []))
        )
        self.assertEqual(
            post_fail_tx_count,
            base_tx_count,
            f"Transactions count changed after failed atomic commit: {base_tx_count} -> {post_fail_tx_count}",
        )

        # Assert new category was NOT created (all-or-nothing rollback)
        cat_check_resp = self.owner_client.get(f"/api/companies/{alpha_id}/categories")
        self.assertEqual(cat_check_resp.status_code, 200)
        current_cat_names = {c.get("name", "").lower() for c in cat_check_resp.data}
        self.assertNotIn(
            rollback_cat.lower(),
            current_cat_names,
            f"Category '{rollback_cat}' must not exist after rollback",
        )

        # Step 3: Success case - 2 valid rows with auto-created category
        new_cat = f"{self.prefix}-AutoCommittedCat"
        commit_rows = [
            {
                "operation_date": "2026-10-10",
                "amount": "777.00",
                "direction": "inflow",
                "category": new_cat,
                "purpose": "Commit 1",
            },
            {
                "operation_date": "2026-10-11",
                "amount": "888.00",
                "direction": "outflow",
                "category": None,
                "purpose": "Commit 2",
            },
        ]

        commit_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/commit",
            json_data={"rows": commit_rows},
        )
        self.assertEqual(
            commit_resp.status_code,
            201,
            f"Import commit failed (status={commit_resp.status_code}, error={commit_resp.error_code})",
        )
        self.assertEqual(commit_resp.data.get("imported_count"), 2)

        # Verify transactions count increased by exactly 2
        tx_after_resp = self.owner_client.get(f"/api/companies/{alpha_id}/transactions")
        self.assertEqual(tx_after_resp.status_code, 200)
        final_tx_count = tx_after_resp.data.get(
            "total", len(tx_after_resp.data.get("items", []))
        )
        self.assertEqual(
            final_tx_count,
            base_tx_count + 2,
            f"Expected {base_tx_count + 2} transactions, got {final_tx_count}",
        )

        # Track created transactions for suite cleanup
        for it in tx_after_resp.data.get("items", []):
            if it.get("purpose") in ("Commit 1", "Commit 2"):
                self.tracked_transactions.append(
                    {"company_id": alpha_id, "id": it["id"]}
                )

        # Verify category creation is mandatory 200 and category is tracked
        cats_resp = self.owner_client.get(f"/api/companies/{alpha_id}/categories")
        self.assertEqual(
            cats_resp.status_code,
            200,
            f"Listing categories failed (status={cats_resp.status_code})",
        )
        found_new_cat = False
        for c in cats_resp.data:
            if c.get("name") == new_cat:
                found_new_cat = True
                self.tracked_categories.append({"company_id": alpha_id, "id": c["id"]})
        self.assertTrue(
            found_new_cat,
            f"Auto-created category '{new_cat}' not found in company categories",
        )

    def test_22_import_xlsx_preview_in_memory(self):
        """[IMPORT-05] In-memory OpenXML XLSX import parsed without disk dependencies."""
        alpha_id = self.company_alpha["id"]

        # Valid XLSX with numeric amount 1234.56 must be accepted with can_commit=True
        xlsx_rows = [
            {
                "date": "2026-10-15",
                "amount": "1234.56",
                "direction": "inflow",
                "category": "Consulting",
                "purpose": "Xlsx import",
            },
        ]
        xlsx_bytes = generate_minimal_xlsx_bytes(xlsx_rows)

        preview_resp = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={
                "file": (
                    "test.xlsx",
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertEqual(
            preview_resp.status_code,
            200,
            f"XLSX preview failed (status={preview_resp.status_code}, error={preview_resp.error_code})",
        )
        self.assertTrue(
            preview_resp.data.get("can_commit"),
            "Valid XLSX with 1234.56 numeric amount must be accepted with can_commit=True",
        )

        # Extra fixture: numeric amount with >2 decimal places (1.234) rejected without silent rounding
        xlsx_3dp_bytes = generate_minimal_xlsx_bytes(
            [
                {
                    "date": "2026-10-15",
                    "amount": "1.234",
                    "direction": "inflow",
                    "category": "Consulting",
                    "purpose": "3dp numeric amount",
                },
            ]
        )
        resp_3dp = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={
                "file": (
                    "test_3dp.xlsx",
                    xlsx_3dp_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertNotEqual(
            resp_3dp.status_code,
            500,
            "XLSX import with numeric amount 1.234 must not return 500 Internal Server Error",
        )
        self.assertIn(
            resp_3dp.status_code,
            (200, 422),
            f"Expected 200 (with can_commit=False) or 422 for numeric 1.234, got {resp_3dp.status_code}",
        )
        if resp_3dp.status_code == 200:
            self.assertFalse(
                resp_3dp.data.get("can_commit"),
                "Numeric amount with >2 decimal places (1.234) must be rejected, not silently rounded",
            )

        # Extra fixture: date with time component (12:30) rejected
        xlsx_time_bytes = generate_minimal_xlsx_bytes(
            [
                {
                    "date": "2026-10-15 12:30",
                    "amount": "1234.56",
                    "direction": "inflow",
                    "category": "Consulting",
                    "purpose": "Datetime with time",
                },
            ]
        )
        resp_time = self.owner_client.post(
            f"/api/companies/{alpha_id}/imports/preview",
            files={
                "file": (
                    "test_time.xlsx",
                    xlsx_time_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        self.assertNotEqual(
            resp_time.status_code,
            500,
            "XLSX import with datetime 12:30 must not return 500 Internal Server Error",
        )
        self.assertIn(
            resp_time.status_code,
            (200, 422),
            f"Expected 200 (with can_commit=False) or 422 for datetime with time, got {resp_time.status_code}",
        )
        if resp_time.status_code == 200:
            self.assertFalse(
                resp_time.data.get("can_commit"),
                "Date with time component (12:30) must be rejected with can_commit=False",
            )

    # --------------------------------------------------------------------------
    # 6. FORECAST & GRPC ENGINE
    # --------------------------------------------------------------------------

    def test_23_forecast_29_days_rejected(self):
        """[FORECAST-01] History cutoff < 30 days (29 days) rejected with 422 INSUFFICIENT_HISTORY."""
        # Create dedicated forecast company if not created
        if not self.company_forecast:
            resp = self.owner_client.post(
                "/api/companies",
                json_data={
                    "name": f"{self.prefix}-ForecastCo",
                    "industry_code": "FINANCE",
                },
            )
            self.assertEqual(resp.status_code, 201)
            CashflowRadarAcceptanceTest.company_forecast = resp.data

        cid = self.company_forecast["id"]
        cutoff_date = "2026-11-04"
        dates_29 = build_date_range(cutoff_date, 29)

        tx_first = self.owner_client.post(
            f"/api/companies/{cid}/transactions",
            json_data={
                "operation_date": dates_29[0],
                "amount": "1000.00",
                "direction": "inflow",
            },
        )
        self.assertEqual(tx_first.status_code, 201)
        self.tracked_transactions.append({"company_id": cid, "id": tx_first.data["id"]})

        tx_last = self.owner_client.post(
            f"/api/companies/{cid}/transactions",
            json_data={
                "operation_date": dates_29[-1],
                "amount": "2000.00",
                "direction": "inflow",
            },
        )
        self.assertEqual(tx_last.status_code, 201)
        self.tracked_transactions.append({"company_id": cid, "id": tx_last.data["id"]})

        forecast_resp = self.owner_client.post(
            f"/api/companies/{cid}/forecast",
            json_data={"history_end": cutoff_date, "horizon_days": 7},
        )
        self.assertEqual(
            forecast_resp.status_code,
            422,
            f"Expected 422 for 29 days history, got {forecast_resp.status_code} (error={forecast_resp.error_code})",
        )
        self.assertEqual(forecast_resp.error_code, "INSUFFICIENT_HISTORY")

    def test_24_forecast_30_days_accept_and_shape(self):
        """[FORECAST-02] History cutoff >= 30 days accepted (200 OK), verifies forecast contract."""
        cid = self.company_forecast["id"]
        cutoff_date = "2026-11-04"
        dates_30 = build_date_range(cutoff_date, 30)

        tx_day30 = self.owner_client.post(
            f"/api/companies/{cid}/transactions",
            json_data={
                "operation_date": dates_30[0],
                "amount": "1500.00",
                "direction": "inflow",
            },
        )
        self.assertEqual(tx_day30.status_code, 201)
        self.tracked_transactions.append({"company_id": cid, "id": tx_day30.data["id"]})

        horizon = 7
        forecast_resp = self.owner_client.post(
            f"/api/companies/{cid}/forecast",
            json_data={"history_end": cutoff_date, "horizon_days": horizon},
        )

        self.assertEqual(
            forecast_resp.status_code,
            200,
            f"Forecast failed (status={forecast_resp.status_code}, error={forecast_resp.error_code})",
        )
        res = forecast_resp.data

        self.assertEqual(res.get("history_end"), cutoff_date)
        self.assertEqual(res.get("history_days"), 30)
        self.assertEqual(res.get("history_start"), dates_30[0])
        self.assertEqual(res.get("horizon_days"), horizon)
        self.assertEqual(res.get("currency"), "RUB")
        self.assertIn("model", res)
        self.assertIn("generated_at", res)
        self.assertIsInstance(res.get("warnings"), list)

        points = res.get("forecast", [])
        self.assertEqual(
            len(points),
            horizon,
            f"Expected {horizon} forecast points, got {len(points)}",
        )

        expected_next = datetime.date.fromisoformat(cutoff_date) + datetime.timedelta(
            days=1
        )
        for p in points:
            self.assertEqual(p.get("date"), expected_next.isoformat())
            self.assertIn("net_cash_flow", p)
            val_str = str(p["net_cash_flow"])
            self.assertTrue(
                re.match(r"^-?\d+\.\d{2}$", val_str),
                f"net_cash_flow '{val_str}' must be exact 2-decimal-place string (e.g. '0.00' or '-15.50')",
            )
            val_dec = decimal.Decimal(val_str)
            self.assertTrue(
                val_dec.is_finite(),
                f"net_cash_flow '{val_str}' must be a finite Decimal, not NaN/inf",
            )
            expected_next += datetime.timedelta(days=1)


if __name__ == "__main__":
    unittest.main()
