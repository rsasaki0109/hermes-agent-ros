"""Shared pytest hooks for hermes_agent."""
from __future__ import annotations

import os
import random

import pytest

# Fast DDS multicast port math requires domain id <= 232.
_DOMAIN_LO = 200
_DOMAIN_HI = 230


@pytest.fixture(scope='session', autouse=True)
def _hermes_ros_test_isolation():
    """Avoid cross-talk with manual demos (other agents on domain 0 / 224).

    A random domain per pytest session keeps CI deterministic enough while
    making local collisions with a leftover `ros2 launch` unlikely.
    """
    os.environ.pop('ROS_LOCALHOST_ONLY', None)
    if 'HERMES_TEST_ROS_DOMAIN_ID' in os.environ:
        os.environ['ROS_DOMAIN_ID'] = os.environ['HERMES_TEST_ROS_DOMAIN_ID']
    else:
        os.environ['ROS_DOMAIN_ID'] = str(
            random.randint(_DOMAIN_LO, _DOMAIN_HI))
