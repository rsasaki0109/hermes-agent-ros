from setuptools import find_packages, setup

package_name = 'hermes_agent'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ryohei Sasaki',
    maintainer_email='rsasaki0109@gmail.com',
    description='Planner / Executor nodes and LLM clients for hermes-agent-ros.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'agent_node = hermes_agent.agent_node:main',
            'executor_node = hermes_agent.executor_node:main',
        ],
    },
)
