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
        description='LLM backend: mock | anthropic | openai')

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
        launch_arguments={'llm': LaunchConfiguration('llm')}.items(),
    )

    return LaunchDescription([
        llm_arg,
        turtlesim,
        hermes,
    ])
