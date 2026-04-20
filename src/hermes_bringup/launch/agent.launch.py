"""Launch the hermes agent stack (Planner + Executor).

Brings up:
  - /hermes_executor   (ExecutorNode, /hermes/execute_plan)
  - /hermes_agent      (AgentNode, /hermes/ask)

Args:
  llm        — LLM backend name. Currently only 'mock' is wired up
               from launch; real backends are swapped by editing the
               entrypoint (T-07 follow-up).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    llm_arg = DeclareLaunchArgument(
        'llm', default_value='mock',
        description='LLM backend: mock | anthropic | openai')

    agent_node = Node(
        package='hermes_agent',
        executable='agent_node',
        name='hermes_agent',
        output='screen',
        parameters=[{
            'llm_provider': LaunchConfiguration('llm'),
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
        executor_node,
        agent_node,
    ])
