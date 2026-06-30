import requests
import logging
from django.conf import settings
from .models import VerificationLog
from fuzzywuzzy import fuzz
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class VerificationService:
    """
    Handles identity verification using the Dojah API for Nigerian KYC.

    Supports:
        - NIN  (National Identity Number)
        - vNIN (Virtual NIN)
        - BVN  (Bank Verification Number)
        - CAC  (Corporate Affairs Commission)

    Confidence scoring automatically determines whether a submission
    should be auto-approved, sent for manual review, or auto-rejected.

    Required Django settings:
        DOJAH_APP_ID      – Your Dojah App ID
        DOJAH_API_KEY     – Your Dojah private/secret API key
        DOJAH_BASE_URL    – (optional) defaults to Dojah's production URL

    Optional threshold settings (percentages, 0–100):
        AUTO_VERIFY_CONFIDENCE_THRESHOLD   – default 85
        REQUIRE_MANUAL_REVIEW_BELOW        – default 70
        AUTO_REJECT_BELOW                  – default 50
    """

    DOJAH_BASE_URL = "https://api.dojah.io"

    ENDPOINTS = {
        "nin":      "/api/v1/kyc/nin",
        "vnin":     "/api/v1/kyc/vnin",
        "bvn":      "/api/v1/kyc/bvn",
        "bvn_full": "/api/v1/kyc/bvn/full",
        "cac":      "/api/v1/kyc/cac",
    }

    def __init__(self):
        self.provider = "dojah"
        self.app_id   = getattr(settings, "DOJAH_APP_ID",  None)
        self.api_key  = getattr(settings, "DOJAH_API_KEY", None)
        self.base_url = getattr(settings, "DOJAH_BASE_URL", self.DOJAH_BASE_URL).rstrip("/")

        self.auto_verify_threshold   = getattr(settings, "AUTO_VERIFY_CONFIDENCE_THRESHOLD", 85)
        self.manual_review_threshold = getattr(settings, "REQUIRE_MANUAL_REVIEW_BELOW",      70)
        self.auto_reject_threshold   = getattr(settings, "AUTO_REJECT_BELOW",                50)

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _get_headers(self):
        """Build Dojah authentication headers."""
        if not self.api_key or not self.app_id:
            raise ValueError(
                "Dojah credentials not configured. "
                "Set DOJAH_APP_ID and DOJAH_API_KEY in your Django settings."
            )
        return {
            "AppId":         self.app_id,
            "Authorization": self.api_key,
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }

    def _generate_reference(self):
        return f"VER-{uuid.uuid4().hex[:12].upper()}"

    def _log_attempt(
        self,
        user,
        v_type,
        request_data,
        response_data,
        status,
        is_match=False,
        confidence_score=None,
        error=None,
    ):
        """
        Persist a verification attempt to the database.
        Never raises — a logging failure must never block the verification result.
        """
        try:
            # Strip the photo from response_data before saving to avoid huge DB blobs
            safe_response = {}
            if isinstance(response_data, dict):
                safe_response = {
                    k: (v if k != "photo" and not (isinstance(v, str) and len(v) > 500) else "[truncated]")
                    for k, v in response_data.items()
                }
                entity = safe_response.get("entity")
                if isinstance(entity, dict):
                    safe_response["entity"] = {
                        k: (v if not (isinstance(v, str) and len(v) > 500) else "[truncated]")
                        for k, v in entity.items()
                    }

            return VerificationLog.objects.create(
                user=user,
                verification_type=v_type,
                api_provider=self.provider,
                request_data=request_data,
                response_data=safe_response,
                status=status,
                is_match=is_match,
                confidence_score=confidence_score,
                error_message=error,
            )
        except Exception as e:
            logger.error(
                "_log_attempt failed for user=%s type=%s status=%s — %s",
                getattr(user, "pk", "?"), v_type, status, e,
                exc_info=True,
            )
            return None

    def _make_request(self, endpoint_key, params):
        """
        Perform a GET request to a Dojah KYC endpoint.

        Returns:
            tuple[bool, dict]: (success, response_dict)
        """
        if not self.api_key or not self.app_id:
            logger.error("Dojah credentials not configured.")
            return False, {"error": "Verification system is temporarily unavailable."}

        url = f"{self.base_url}{self.ENDPOINTS[endpoint_key]}"

        try:
            headers = self._get_headers()
            logger.info("Dojah request → %s | params keys: %s", url, list(params.keys()))

            response = requests.get(url, params=params, headers=headers, timeout=30)

            # ── Log status + raw text before attempting JSON parse ──────────────
            logger.debug(
                "Dojah raw response [%s] | body preview: %s",
                response.status_code,
                response.text[:300] if response.text else "<empty>",
            )

            # Guard: empty body means Dojah returned nothing parseable
            if not response.text or not response.text.strip():
                msg = (
                    f"Dojah returned an empty response body (HTTP {response.status_code}). "
                    "This usually means the endpoint is not enabled on your plan, "
                    "your App ID / API Key is wrong, or you have exceeded your quota."
                )
                logger.error(msg)
                return False, {"error": msg}

            # Parse JSON — catch malformed responses gracefully
            try:
                data = response.json()
            except (ValueError, Exception) as json_err:
                msg = (
                    f"Dojah returned non-JSON (HTTP {response.status_code}). "
                    f"Parse error: {json_err}. "
                    f"Raw response: {response.text[:200]}"
                )
                logger.error(msg)
                return False, {"error": msg}

            logger.info("Dojah response [%s]: entity present=%s", response.status_code, bool(data.get("entity")))

            # Success: 200 + entity key present and non-empty
            if response.status_code == 200 and data.get("entity"):
                return True, data

            # Dojah sometimes returns 200 with no entity (e.g. NIN not found)
            error_msg = (
                data.get("error")
                or data.get("message")
                or (data.get("errors") or [None])[0]
                or f"HTTP {response.status_code} — no entity in response"
            )
            logger.error("Dojah verification failed: %s", error_msg)
            return False, {"error": error_msg, "raw_response": data}

        except requests.exceptions.Timeout:
            msg = "Dojah API request timed out after 30 seconds."
            logger.exception(msg)
            return False, {"error": msg}

        except requests.exceptions.ConnectionError as exc:
            msg = f"Could not connect to Dojah API: {exc}"
            logger.exception(msg)
            return False, {"error": msg}

        except requests.exceptions.RequestException as exc:
            msg = f"Network error contacting Dojah API: {exc}"
            logger.exception(msg)
            return False, {"error": msg}

        except Exception as exc:
            msg = f"Unexpected error during Dojah request: {exc}"
            logger.exception(msg)
            return False, {"error": msg}

    # ---------------------------------------------------------------------------
    # Response normalisation
    # ---------------------------------------------------------------------------

    def _extract_nin_data(self, response):
        """
        Normalise a Dojah NIN/vNIN response.
        Handles both old-style keys (firstname/surname) and new-style (first_name/last_name).
        """
        try:
            entity = response.get("entity") or {}
            if not isinstance(entity, dict):
                logger.warning("_extract_nin_data: entity is not a dict — got %s", type(entity))
                entity = {}

            return {
                "status":        "verified",
                "first_name":    entity.get("firstname")  or entity.get("first_name"),
                "last_name":     entity.get("surname")    or entity.get("last_name"),
                "middle_name":   entity.get("middlename") or entity.get("middle_name"),
                "date_of_birth": (
                    entity.get("birthdate")
                    or entity.get("date_of_birth")
                    or entity.get("dob")
                ),
                "phone":         (
                    entity.get("phone_number")
                    or entity.get("phone")
                    or entity.get("mobile")
                ),
                "email":         entity.get("email"),
                "gender":        entity.get("gender"),
                "address":       entity.get("residence_address") or entity.get("address"),
                "photo":         entity.get("photo"),
                "nin":           entity.get("nin"),
                "raw_data":      entity,
            }
        except Exception as exc:
            logger.exception("_extract_nin_data failed: %s", exc)
            return {"status": "extraction_error", "error": str(exc), "raw_data": response}

    def _extract_bvn_data(self, response):
        """
        Normalise a Dojah BVN response.
        Handles both standard and full BVN shapes.
        """
        try:
            entity = response.get("entity") or {}
            if not isinstance(entity, dict):
                logger.warning("_extract_bvn_data: entity is not a dict — got %s", type(entity))
                entity = {}

            return {
                "status":            "verified",
                "first_name":        entity.get("first_name")   or entity.get("firstname"),
                "last_name":         entity.get("last_name")    or entity.get("surname"),
                "middle_name":       entity.get("middle_name")  or entity.get("middlename"),
                "date_of_birth":     (
                    entity.get("date_of_birth")
                    or entity.get("dob")
                    or entity.get("birthdate")
                ),
                "phone":             (
                    entity.get("phone_number")
                    or entity.get("mobile")
                    or entity.get("phone")
                ),
                "email":             entity.get("email"),
                "gender":            entity.get("gender"),
                "bvn":               entity.get("bvn"),
                "enrollment_bank":   entity.get("enrollment_bank"),
                "enrollment_branch": entity.get("enrollment_branch"),
                "photo":             entity.get("image"),
                "raw_data":          entity,
            }
        except Exception as exc:
            logger.exception("_extract_bvn_data failed: %s", exc)
            return {"status": "extraction_error", "error": str(exc), "raw_data": response}

    def _extract_cac_data(self, response):
        """Normalise a Dojah CAC response."""
        try:
            entity = response.get("entity") or {}
            if not isinstance(entity, dict):
                logger.warning("_extract_cac_data: entity is not a dict — got %s", type(entity))
                entity = {}

            return {
                "status":            "verified",
                "company_name":      entity.get("company_name") or entity.get("name"),
                "rc_number":         entity.get("rc_number"),
                "company_status":    entity.get("status"),
                "company_type":      entity.get("company_type") or entity.get("type"),
                "registration_date": entity.get("registration_date"),
                "address":           entity.get("address"),
                "email":             entity.get("email"),
                "phone":             entity.get("phone"),
                "directors":         entity.get("directors", []),
                "raw_data":          entity,
            }
        except Exception as exc:
            logger.exception("_extract_cac_data failed: %s", exc)
            return {"status": "extraction_error", "error": str(exc), "raw_data": response}

    # ---------------------------------------------------------------------------
    # Public verification methods
    # ---------------------------------------------------------------------------

    def verify_nin(self, user, nin, first_name=None, last_name=None, dob=None):
        """
        Verify a National Identity Number (NIN) via Dojah.

        Args:
            first_name: Name as entered by user on the verification form.
            last_name:  Surname as entered by user on the verification form.
            dob:        Date of birth string (YYYY-MM-DD or DD-MM-YYYY) from form.

        Returns:
            (True,  extracted_dict)  on success
            (False, error_string)    on failure
        """
        log_params = {"nin": nin}

        try:
            success, result = self._make_request("nin", {"nin": nin})

            if not success:
                error_msg = result.get("error", "NIN verification failed.")
                logger.warning("NIN verification failed for user=%s: %s", user.pk, error_msg)
                self._log_attempt(user, "nin", log_params, result, "failed", error=error_msg)
                return False, error_msg

            extracted = self._extract_nin_data(result)

            if extracted.get("status") == "extraction_error":
                error_msg = f"Failed to parse Dojah NIN response: {extracted.get('error')}"
                logger.error(error_msg)
                self._log_attempt(user, "nin", log_params, result, "failed", error=error_msg)
                return False, error_msg

            confidence = self.calculate_confidence_score(
                extracted, user,
                submitted_first_name=first_name,
                submitted_last_name=last_name,
                submitted_dob=dob,
            )
            extracted["confidence"] = confidence

            self._log_attempt(
                user, "nin", log_params, result, "success",
                is_match=confidence["overall_confidence"] >= self.manual_review_threshold,
                confidence_score=confidence["overall_confidence"],
            )
            logger.info(
                "NIN verification succeeded for user=%s | confidence=%.1f | recommendation=%s",
                user.pk, confidence["overall_confidence"], confidence["recommendation"],
            )
            return True, extracted

        except Exception as exc:
            logger.exception("Unexpected error during NIN verification for user=%s", user.pk)
            self._log_attempt(user, "nin", log_params, {}, "failed", error=str(exc))
            return False, f"An unexpected error occurred during NIN verification: {exc}"

    def verify_vnin(self, user, vnin, first_name=None, last_name=None, dob=None):
        """
        Verify a Virtual NIN (vNIN) via Dojah.

        Args:
            first_name: Name as entered by user on the verification form.
            last_name:  Surname as entered by user on the verification form.
            dob:        Date of birth string from form.

        Returns:
            (True,  extracted_dict)  on success
            (False, error_string)    on failure
        """
        log_params = {"vnin": vnin}

        try:
            success, result = self._make_request("vnin", {"vnin": vnin})

            if not success:
                error_msg = result.get("error", "vNIN verification failed.")
                logger.warning("vNIN verification failed for user=%s: %s", user.pk, error_msg)
                self._log_attempt(user, "vnin", log_params, result, "failed", error=error_msg)
                return False, error_msg

            extracted = self._extract_nin_data(result)  # same shape as NIN

            if extracted.get("status") == "extraction_error":
                error_msg = f"Failed to parse Dojah vNIN response: {extracted.get('error')}"
                logger.error(error_msg)
                self._log_attempt(user, "vnin", log_params, result, "failed", error=error_msg)
                return False, error_msg

            confidence = self.calculate_confidence_score(
                extracted, user,
                submitted_first_name=first_name,
                submitted_last_name=last_name,
                submitted_dob=dob,
            )
            extracted["confidence"] = confidence

            self._log_attempt(
                user, "vnin", log_params, result, "success",
                is_match=confidence["overall_confidence"] >= self.manual_review_threshold,
                confidence_score=confidence["overall_confidence"],
            )
            logger.info(
                "vNIN verification succeeded for user=%s | confidence=%.1f | recommendation=%s",
                user.pk, confidence["overall_confidence"], confidence["recommendation"],
            )
            return True, extracted

        except Exception as exc:
            logger.exception("Unexpected error during vNIN verification for user=%s", user.pk)
            self._log_attempt(user, "vnin", log_params, {}, "failed", error=str(exc))
            return False, f"An unexpected error occurred during vNIN verification: {exc}"

    def verify_bvn(self, user, bvn, first_name=None, last_name=None, dob=None):
        """
        Verify a Bank Verification Number (BVN) via Dojah.

        Args:
            first_name: Name as entered by user on the verification form.
            last_name:  Surname as entered by user on the verification form.
            dob:        Date of birth string from form.

        Returns:
            (True,  extracted_dict)  on success
            (False, error_string)    on failure
        """
        log_params = {"bvn": bvn}

        try:
            success, result = self._make_request("bvn", {"bvn": bvn})

            if not success:
                error_msg = result.get("error", "BVN verification failed.")
                logger.warning("BVN verification failed for user=%s: %s", user.pk, error_msg)
                self._log_attempt(user, "bvn", log_params, result, "failed", error=error_msg)
                return False, error_msg

            extracted = self._extract_bvn_data(result)

            if extracted.get("status") == "extraction_error":
                error_msg = f"Failed to parse Dojah BVN response: {extracted.get('error')}"
                logger.error(error_msg)
                self._log_attempt(user, "bvn", log_params, result, "failed", error=error_msg)
                return False, error_msg

            confidence = self.calculate_confidence_score(
                extracted, user,
                submitted_first_name=first_name,
                submitted_last_name=last_name,
                submitted_dob=dob,
            )
            extracted["confidence"] = confidence

            self._log_attempt(
                user, "bvn", log_params, result, "success",
                is_match=confidence["overall_confidence"] >= self.manual_review_threshold,
                confidence_score=confidence["overall_confidence"],
            )
            logger.info(
                "BVN verification succeeded for user=%s | confidence=%.1f | recommendation=%s",
                user.pk, confidence["overall_confidence"], confidence["recommendation"],
            )
            return True, extracted

        except Exception as exc:
            logger.exception("Unexpected error during BVN verification for user=%s", user.pk)
            self._log_attempt(user, "bvn", log_params, {}, "failed", error=str(exc))
            return False, f"An unexpected error occurred during BVN verification: {exc}"

    def verify_cac(self, user, rc_number, company_name=None):
        """
        Verify a CAC (Corporate Affairs Commission) registration via Dojah.

        Returns:
            (True,  extracted_dict)  on success
            (False, error_string)    on failure
        """
        log_params = {"rc_number": rc_number}

        try:
            clean_rc = rc_number.upper().lstrip("RC").lstrip("0") if rc_number else rc_number
            success, result = self._make_request("cac", {"rc_number": clean_rc})

            if not success:
                error_msg = result.get("error", "CAC verification failed.")
                logger.warning("CAC verification failed for user=%s: %s", user.pk, error_msg)
                self._log_attempt(user, "cac", log_params, result, "failed", error=error_msg)
                return False, error_msg

            extracted = self._extract_cac_data(result)

            if extracted.get("status") == "extraction_error":
                error_msg = f"Failed to parse Dojah CAC response: {extracted.get('error')}"
                logger.error(error_msg)
                self._log_attempt(user, "cac", log_params, result, "failed", error=error_msg)
                return False, error_msg

            is_match = True
            if company_name and extracted.get("company_name"):
                name_score = self._fuzzy_match_name(company_name, extracted["company_name"])
                is_match   = name_score >= self.manual_review_threshold
                extracted["company_name_match_score"] = name_score

            self._log_attempt(
                user, "cac", log_params, result,
                "success" if is_match else "failed",
                is_match=is_match,
            )

            logger.info("CAC verification succeeded for user=%s | match=%s", user.pk, is_match)
            return True, extracted

        except Exception as exc:
            logger.exception("Unexpected error during CAC verification for user=%s", user.pk)
            self._log_attempt(user, "cac", log_params, {}, "failed", error=str(exc))
            return False, f"An unexpected error occurred during CAC verification: {exc}"

    # ---------------------------------------------------------------------------
    # Confidence scoring
    # ---------------------------------------------------------------------------

    def calculate_confidence_score(
        self,
        api_data,
        user,
        submitted_first_name=None,
        submitted_last_name=None,
        submitted_dob=None,
        user_profile=None,
    ):
        """
        Compare API-returned identity data against user-submitted form values.

        Priority for comparison values:
            submitted form field  >  Django user model field  >  skipped

        Weighted scoring model (weights sum to 100):
            First name :  35 pts  — fuzzy matched
            Last name  :  35 pts  — fuzzy matched
            Date of birth: 20 pts — exact date match
            Phone      :  10 pts  — last-10-digit match (bonus check)

        Only checks that have BOTH an API value and a user value contribute.
        Weights are re-normalised over the checks that actually ran, so a
        missing DOB does not automatically tank the score.

        Returns:
            {
                "overall_confidence": float (0–100),
                "breakdown":          dict,
                "checks_performed":   int,
                "recommendation":     str   (auto_approve | manual_review | auto_reject),
            }
        """
        WEIGHTS = {
            "first_name": 35,
            "last_name":  35,
            "dob":        20,
            "phone":      10,
        }

        # (field_key, raw_score 0-100, weight)
        checks: list[tuple[str, float, int]] = []
        breakdown: dict = {}

        try:
            # ── Collect all name parts from API response ────────────────────────
            api_first = (
                (api_data.get("first_name") or api_data.get("firstname") or "")
                .strip()
            )
            api_last = (
                (
                    api_data.get("last_name")
                    or api_data.get("lastname")
                    or api_data.get("surname")
                    or ""
                ).strip()
            )
            api_middle = (
                (api_data.get("middle_name") or api_data.get("middlename") or "")
                .strip()
            )
            # All non-empty API name parts for cross-matching
            api_name_parts = [n for n in (api_first, api_middle, api_last) if n]

            cmp_first = (
                (submitted_first_name or getattr(user, "first_name", "") or "")
                .strip()
            )
            cmp_last = (
                (submitted_last_name or getattr(user, "last_name", "") or "")
                .strip()
            )

            # ── Cross-match names ────────────────────────────────────────────────
            # Nigerian IDs commonly store names in different field orders
            # (e.g. user's "last name" is stored as "middle_name" in NIN DB).
            # We find the best match for each submitted name across ALL API parts.

            if api_name_parts and cmp_first:
                # Score submitted first name against every API name part
                first_scores = [
                    (self._fuzzy_match_name(cmp_first, part), part)
                    for part in api_name_parts
                ]
                best_first_score, best_first_part = max(first_scores, key=lambda x: x[0])

                # Also try direct first↔first comparison in case cross-match picks wrong
                direct_first_score = (
                    self._fuzzy_match_name(cmp_first, api_first) if api_first else 0
                )
                score = max(best_first_score, direct_first_score)

                checks.append(("first_name", score, WEIGHTS["first_name"]))
                breakdown["first_name"] = {
                    "api":    (best_first_part if best_first_score >= direct_first_score else api_first).title(),
                    "yours":  cmp_first.title(),
                    "score":  score,
                    "weight": WEIGHTS["first_name"],
                }
                logger.debug(
                    "first_name cross-match: user=%r best_api=%r score=%s (direct=%s)",
                    cmp_first, best_first_part, best_first_score, direct_first_score,
                )

            if api_name_parts and cmp_last:
                # Score submitted last name against every API name part
                last_scores = [
                    (self._fuzzy_match_name(cmp_last, part), part)
                    for part in api_name_parts
                ]
                best_last_score, best_last_part = max(last_scores, key=lambda x: x[0])

                # Also try direct last↔last comparison
                direct_last_score = (
                    self._fuzzy_match_name(cmp_last, api_last) if api_last else 0
                )
                score = max(best_last_score, direct_last_score)

                checks.append(("last_name", score, WEIGHTS["last_name"]))
                breakdown["last_name"] = {
                    "api":    (best_last_part if best_last_score >= direct_last_score else api_last).title(),
                    "yours":  cmp_last.title(),
                    "score":  score,
                    "weight": WEIGHTS["last_name"],
                }
                logger.debug(
                    "last_name cross-match: user=%r best_api=%r score=%s (direct=%s)",
                    cmp_last, best_last_part, best_last_score, direct_last_score,
                )

            # ── Date of birth ────────────────────────────────────────────────────
            api_dob_raw = (
                api_data.get("date_of_birth")
                or api_data.get("dob")
                or api_data.get("birthdate")
            )
            cmp_dob_raw = submitted_dob or (
                user_profile and getattr(user_profile, "date_of_birth", None)
            )
            if api_dob_raw and cmp_dob_raw:
                api_dob = self._parse_date(str(api_dob_raw))
                cmp_dob = (
                    self._parse_date(str(cmp_dob_raw))
                    if isinstance(cmp_dob_raw, str)
                    else cmp_dob_raw
                )
                if api_dob and cmp_dob:
                    score = 100 if api_dob == cmp_dob else 0
                    checks.append(("dob", score, WEIGHTS["dob"]))
                    breakdown["date_of_birth"] = {
                        "match":  api_dob == cmp_dob,
                        "score":  score,
                        "weight": WEIGHTS["dob"],
                    }
                    logger.debug("dob: api=%s user=%s match=%s", api_dob, cmp_dob, api_dob == cmp_dob)

            # ── Phone (bonus integrity check — low weight) ───────────────────────
            api_phone_raw = (
                api_data.get("phone")
                or api_data.get("phone_number")
                or api_data.get("mobile")
                or ""
            )
            if api_phone_raw:
                def _clean_phone(p):
                    return str(p).replace("+234", "0").replace(" ", "").replace("-", "")

                api_phone = _clean_phone(api_phone_raw)
                user_phone = ""
                if user_profile and getattr(user_profile, "phone", None):
                    user_phone = _clean_phone(user_profile.phone)
                elif hasattr(user, "phone_number") and user.phone_number:
                    user_phone = _clean_phone(user.phone_number)

                if api_phone and user_phone and len(api_phone) >= 10 and len(user_phone) >= 10:
                    score = 100 if api_phone[-10:] == user_phone[-10:] else 0
                    checks.append(("phone", score, WEIGHTS["phone"]))
                    breakdown["phone"] = {
                        "match":  api_phone[-10:] == user_phone[-10:],
                        "score":  score,
                        "weight": WEIGHTS["phone"],
                    }
                    logger.debug(
                        "phone: api=%s user=%s match=%s",
                        api_phone[-10:], user_phone[-10:], score == 100,
                    )

        except Exception as exc:
            logger.exception("calculate_confidence_score error: %s", exc)

        # ── Weighted average (re-normalised over checks that ran) ────────────────
        if not checks:
            # No comparable fields — API record exists but we have nothing to match
            # against. Treat as manual review rather than auto-approve to be safe.
            overall = 72.0
            breakdown["note"] = (
                "No personal details were submitted for comparison. "
                "Routed to manual review for safety."
            )
            logger.warning(
                "calculate_confidence_score: no comparable fields for user=%s",
                getattr(user, "pk", "?"),
            )
        else:
            total_weight = sum(w for _, _, w in checks)
            weighted_sum = sum(s * w for _, s, w in checks)
            overall = round(weighted_sum / total_weight, 2)

        recommendation = self._get_recommendation(overall)

        logger.info(
            "Confidence result for user=%s: overall=%.1f checks=%d recommendation=%s",
            getattr(user, "pk", "?"), overall, len(checks), recommendation,
        )

        return {
            "overall_confidence": overall,
            "breakdown":          breakdown,
            "checks_performed":   len(checks),
            "recommendation":     recommendation,
        }

    # ---------------------------------------------------------------------------
    # Private utilities
    # ---------------------------------------------------------------------------

    def _fuzzy_match_name(self, name1, name2):
        """
        Return the best fuzzy similarity score (0–100) between two name strings.
        Uses three algorithms and picks the highest to be lenient with
        transpositions, middle-name insertion, and minor typos.
        """
        if not name1 or not name2:
            return 0
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        return max(
            fuzz.ratio(n1, n2),
            fuzz.partial_ratio(n1, n2),
            fuzz.token_sort_ratio(n1, n2),
        )

    def _parse_date(self, date_str):
        """Parse a date string into a date object. Supports YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY."""
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    def _get_recommendation(self, confidence):
        """
        Translate a confidence score into an action recommendation.

        Thresholds (configurable via Django settings):
            >= AUTO_VERIFY_CONFIDENCE_THRESHOLD  (default 85) → auto_approve
            >= REQUIRE_MANUAL_REVIEW_BELOW        (default 70) → manual_review
            <  REQUIRE_MANUAL_REVIEW_BELOW               → auto_reject
        """
        if confidence >= self.auto_verify_threshold:
            return "auto_approve"
        if confidence >= self.manual_review_threshold:
            return "manual_review"
        return "auto_reject"