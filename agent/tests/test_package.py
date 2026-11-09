"""Smoke checks for the installed agent package."""

from importlib import import_module


def test_agent_package_is_importable():
    package = import_module("athena_agent")

    assert package.__name__ == "athena_agent"
