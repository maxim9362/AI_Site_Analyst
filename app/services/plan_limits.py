from dataclasses import dataclass


DEFAULT_ACCOUNT_PLAN = "partner"
VALID_ACCOUNT_PLANS = {"demo", "start", "partner", "agency"}


@dataclass(frozen=True)
class PlanLimits:
    key: str
    label: str
    max_sites: int
    can_use_gsc: bool
    can_use_email_reports: bool
    can_use_partner_clients: bool
    can_use_pagespeed: bool = True
    can_use_ai_reports: bool = True

    @property
    def feature_labels(self) -> list[str]:
        features = ["AI-анализ", "PageSpeed", f"до {self.max_sites} сайтов"]
        if self.can_use_gsc:
            features.append("Search Console")
        if self.can_use_partner_clients:
            features.append("несколько клиентских сайтов")
        if self.can_use_email_reports:
            features.append("email-отчеты, если включены")
        return features


_PLAN_LIMITS = {
    "demo": PlanLimits(
        key="demo",
        label="Demo",
        max_sites=0,
        can_use_gsc=False,
        can_use_email_reports=False,
        can_use_partner_clients=False,
        can_use_pagespeed=False,
        can_use_ai_reports=False,
    ),
    "start": PlanLimits(
        key="start",
        label="Start",
        max_sites=1,
        can_use_gsc=True,
        can_use_email_reports=False,
        can_use_partner_clients=False,
    ),
    "partner": PlanLimits(
        key="partner",
        label="Partner",
        max_sites=3,
        can_use_gsc=True,
        can_use_email_reports=True,
        can_use_partner_clients=True,
    ),
    "agency": PlanLimits(
        key="agency",
        label="Agency",
        max_sites=10,
        can_use_gsc=True,
        can_use_email_reports=True,
        can_use_partner_clients=True,
    ),
}


def normalize_account_plan(plan: str | None) -> str:
    normalized = (plan or DEFAULT_ACCOUNT_PLAN).strip().lower()
    if normalized not in VALID_ACCOUNT_PLANS:
        return DEFAULT_ACCOUNT_PLAN
    return normalized


def get_plan_limits(plan: str | None) -> PlanLimits:
    return _PLAN_LIMITS[normalize_account_plan(plan)]


def site_limit_message(limits: PlanLimits) -> str:
    if limits.max_sites == 0:
        return "В текущем режиме аккаунта нельзя добавлять реальные сайты. Если нужно подключить сайт, свяжитесь с администратором сервиса."
    return (
        f"Вы достигли лимита сайтов для текущего режима аккаунта. "
        f"В текущем режиме аккаунта можно добавить до {limits.max_sites} сайтов. "
        "Если нужно больше сайтов, свяжитесь с администратором сервиса."
    )
