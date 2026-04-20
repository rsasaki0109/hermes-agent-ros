"""Launch Demo-1: turtlesim + hermes agent stack."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


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

    turtlesim = Node(
        package='turtlesim',
        executable='turtlesim_node',
        name='turtlesim',
        output='screen',
    )

    hermes = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('hermes_bringup'),
                'launch', 'agent.launch.py',
            ])
        ]),
        launch_arguments={
            'llm': LaunchConfiguration('llm'),
            'ollama_host': LaunchConfiguration('ollama_host'),
            'ollama_timeout_sec': LaunchConfiguration('ollama_timeout_sec'),
        }.items(),
    )

    return LaunchDescription([
        llm_arg,
        ollama_host_arg,
        ollama_timeout_arg,
        turtlesim,
        hermes,
    ])
