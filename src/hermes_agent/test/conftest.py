"""Shared pytest hooks for hermes_agent."""
from __future__ import annotations

import os

import pytest

# Isolate DDS traffic from unrelated ROS nodes on the developer machine.
_DEFAULT_DOMAIN = '237'


@pytest.fixture(scope='session', autouse=True)
def _hermes_ros_domain_id():
    os.environ.setdefault('ROS_DOMAIN_ID', _DEFAULT_DOMAIN)
