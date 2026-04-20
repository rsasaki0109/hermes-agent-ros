"""Launch the hermes agent stack (Planner + Executor).

Brings up:
  - /hermes_executor   (ExecutorNode, /hermes/execute_plan)
  - /hermes_agent      (AgentNode, /hermes/ask)

Args:
  llm          — ``mock`` (default) or ``ollama`` (local /api/chat).
  ollama_host         — Ollama base URL (default http://localhost:11434).
  ollama_timeout_sec  — HTTP read timeout for /api/chat (default 120).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    llm_arg = DeclareLaunchArgument(
        'llm', default_value='mock',
        description='LLM backend: mock | ollama')
    ollama_host_arg = DeclareLaunchArgument(
        'ollama_host', default_value='http://localhost:11434',
        description='Ollama server base URL')
    ollama_timeout_arg = DeclareLaunchArgument(
        'ollama_timeout_sec', default_value='120.0',
        description='Ollama /api/chat HTTP timeout (seconds)')
    default_cmd_vel_arg = DeclareLaunchArgument(
        'default_cmd_vel_topic', default_value='',
        description='If non-empty, set missing topic_publisher_tool.topic '
                    '(use /turtle1/cmd_vel for turtlesim demo)')

    agent_node = Node(
        package='hermes_agent',
        executable='agent_node',
        name='hermes_agent',
        output='screen',
        parameters=[{
            'llm_provider': LaunchConfiguration('llm'),
            'ollama_host': LaunchConfiguration('ollama_host'),
            'ollama_timeout_sec': LaunchConfiguration('ollama_timeout_sec'),
            'default_cmd_vel_topic': LaunchConfiguration(
                'default_cmd_vel_topic'),
        }],
    )

    executor_node = Node(
        package='hermes_agent',
        executable='executor_node',
        name='hermes_executor',
        output='screen',
    )

    return LaunchDescription([
        llm_arg,
        ollama_host_arg,
        ollama_timeout_arg,
        default_cmd_vel_arg,
        executor_node,
        agent_node,
    ])
