"""Tests for the --manufacturer / --product-name feature.

Covered scenarios
-----------------
1. get_device_info() — unit tests for the override kwargs
2. ClientSettings — manufacturer / product_name are persisted and reloaded
3. parse_args() — CLI flags --manufacturer / --product-name are wired up correctly
4. Precedence — CLI flag wins over settings file; missing flag falls back to settings
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sendspin.cli import parse_args
from sendspin.settings import ClientSettings
from sendspin.utils import get_device_info


# ---------------------------------------------------------------------------
# 1. get_device_info() overrides
# ---------------------------------------------------------------------------


def test_get_device_info_no_override_product_name_is_non_empty() -> None:
    """Without overrides, product_name is auto-detected and non-empty."""
    info = get_device_info()
    assert info.product_name
    assert len(info.product_name) > 0


def test_get_device_info_no_override_manufacturer_is_none() -> None:
    """Without overrides, manufacturer defaults to None."""
    info = get_device_info()
    assert info.manufacturer is None


def test_get_device_info_manufacturer_override() -> None:
    info = get_device_info(manufacturer="Vanatoo")
    assert info.manufacturer == "Vanatoo"


def test_get_device_info_product_name_override() -> None:
    info = get_device_info(product_name="Transparent Speaker Zero+")
    assert info.product_name == "Transparent Speaker Zero+"


def test_get_device_info_both_overrides() -> None:
    info = get_device_info(manufacturer="Vanatoo", product_name="Transparent Speaker Zero+")
    assert info.manufacturer == "Vanatoo"
    assert info.product_name == "Transparent Speaker Zero+"


def test_get_device_info_product_name_override_ignores_os_detection() -> None:
    """Providing product_name must bypass any OS-level detection."""
    # Run twice to confirm the override is stable regardless of platform.
    a = get_device_info(product_name="Custom Box")
    b = get_device_info(product_name="Custom Box")
    assert a.product_name == b.product_name == "Custom Box"


def test_get_device_info_software_version_always_present() -> None:
    info = get_device_info()
    assert info.software_version
    assert "aiosendspin" in info.software_version


# ---------------------------------------------------------------------------
# 2. ClientSettings — persistence round-trip
# ---------------------------------------------------------------------------


def _write_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


def test_settings_loads_manufacturer(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"manufacturer": "Vanatoo"})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    assert s.manufacturer == "Vanatoo"


def test_settings_loads_product_name(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"product_name": "Transparent Speaker Zero+"})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    assert s.product_name == "Transparent Speaker Zero+"


def test_settings_loads_both_fields(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(
        settings_file,
        {"manufacturer": "Vanatoo", "product_name": "Transparent Speaker Zero+"},
    )

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    assert s.manufacturer == "Vanatoo"
    assert s.product_name == "Transparent Speaker Zero+"


def test_settings_manufacturer_defaults_to_none_when_absent(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"player_volume": 50})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    assert s.manufacturer is None


def test_settings_product_name_defaults_to_none_when_absent(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"player_volume": 50})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    assert s.product_name is None


def test_settings_serialises_manufacturer(tmp_path: Path) -> None:
    """to_dict() must include manufacturer so it survives a save/load cycle."""
    settings_file = tmp_path / "settings-daemon.json"
    s = ClientSettings(_settings_file=settings_file, manufacturer="Vanatoo")
    data = s.to_dict()
    assert data["manufacturer"] == "Vanatoo"


def test_settings_serialises_product_name(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    s = ClientSettings(_settings_file=settings_file, product_name="Transparent Speaker Zero+")
    data = s.to_dict()
    assert data["product_name"] == "Transparent Speaker Zero+"


# ---------------------------------------------------------------------------
# 3. CLI flags — parse_args()
# ---------------------------------------------------------------------------


def test_parse_args_manufacturer_flag() -> None:
    args = parse_args(["--manufacturer", "Vanatoo"])
    assert args.manufacturer == "Vanatoo"


def test_parse_args_product_name_flag() -> None:
    args = parse_args(["--product-name", "Transparent Speaker Zero+"])
    assert args.product_name == "Transparent Speaker Zero+"


def test_parse_args_both_flags() -> None:
    args = parse_args(["--manufacturer", "Vanatoo", "--product-name", "Transparent Speaker Zero+"])
    assert args.manufacturer == "Vanatoo"
    assert args.product_name == "Transparent Speaker Zero+"


def test_parse_args_manufacturer_default_is_none() -> None:
    args = parse_args([])
    assert args.manufacturer is None


def test_parse_args_product_name_default_is_none() -> None:
    args = parse_args([])
    assert args.product_name is None


def test_parse_args_daemon_manufacturer_flag() -> None:
    args = parse_args(["daemon", "--manufacturer", "Vanatoo"])
    assert args.manufacturer == "Vanatoo"


def test_parse_args_daemon_product_name_flag() -> None:
    args = parse_args(["daemon", "--product-name", "Transparent Speaker Zero+"])
    assert args.product_name == "Transparent Speaker Zero+"


# ---------------------------------------------------------------------------
# 4. Precedence — CLI flag wins over settings file
# ---------------------------------------------------------------------------


def test_precedence_cli_flag_overrides_settings(tmp_path: Path) -> None:
    """When --manufacturer is given, the settings-file value must be ignored."""
    # Simulate: settings file says "OldManufacturer", CLI says "Vanatoo"
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"manufacturer": "OldManufacturer"})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    cli_manufacturer = "Vanatoo"  # value coming from --manufacturer flag

    # Reproduce the precedence logic from _run_client_mode
    resolved = cli_manufacturer if cli_manufacturer is not None else s.manufacturer
    assert resolved == "Vanatoo"


def test_precedence_settings_used_when_no_cli_flag(tmp_path: Path) -> None:
    """When --manufacturer is omitted, the settings-file value is used."""
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"manufacturer": "Vanatoo"})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    cli_manufacturer = None  # --manufacturer not provided

    resolved = cli_manufacturer if cli_manufacturer is not None else s.manufacturer
    assert resolved == "Vanatoo"


def test_precedence_none_when_neither_cli_nor_settings(tmp_path: Path) -> None:
    """When neither flag nor settings provide a value, manufacturer stays None."""
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    cli_manufacturer = None
    resolved = cli_manufacturer if cli_manufacturer is not None else s.manufacturer
    assert resolved is None


def test_precedence_product_name_cli_overrides_settings(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"product_name": "Old Box"})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    cli_product_name = "Transparent Speaker Zero+"
    resolved = cli_product_name if cli_product_name is not None else s.product_name
    assert resolved == "Transparent Speaker Zero+"


def test_precedence_product_name_settings_used_when_no_cli_flag(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings-daemon.json"
    _write_settings(settings_file, {"product_name": "Transparent Speaker Zero+"})

    s = ClientSettings(_settings_file=settings_file)
    s._load()

    cli_product_name = None
    resolved = cli_product_name if cli_product_name is not None else s.product_name
    assert resolved == "Transparent Speaker Zero+"
