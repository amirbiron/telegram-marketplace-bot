import importlib
import pkgutil
from typing import List, Tuple

import pytest
from sqlalchemy.orm import configure_mappers


def _import_all_submodules(package_name: str) -> List[str]:
    """מייבא את כל תתי המודולים תחת חבילה נתונה ומחזיר את שמותיהם.

    אם יש כשל בייבוא של אחד המודולים, מפיל את הטסט עם פירוט.
    """
    package = importlib.import_module(package_name)

    imported_module_names: List[str] = []
    failures: List[Tuple[str, Exception]] = []

    # הליכה רקורסיבית על כל המודולים תחת החבילה
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        module_name = module_info.name
        try:
            importlib.import_module(module_name)
            imported_module_names.append(module_name)
        except Exception as exc:  # noqa: BLE001 - חשוב לתפוס הכל כדי לדווח
            failures.append((module_name, exc))

    if failures:
        details = "\n".join(
            f"- {name}: {exc.__class__.__name__}: {exc}" for name, exc in failures
        )
        pytest.fail("כשל בייבוא מודולים תחת app.models:\n" + details)

    return imported_module_names


def test_import_app_models_and_configure_mappers() -> None:
    """טסט שמוודא שאפשר לייבא את כל מודלי SQLAlchemy ושמיפויים תקינים.

    המטרה היא לתפוס שגיאות מוקדם (למשל סדר שדות/dataclass/מיפוי) בזמן פיתוח.
    """
    imported = _import_all_submodules("app.models")

    # ודאות שמודולים מרכזיים קיימים תחת app.models
    assert any(name.endswith(".coupon") for name in imported), "מצופה למצוא את המודול app.models.coupon"

    # אימות מיפויים של SQLAlchemy (ללא גישה למסד נתונים)
    configure_mappers()

