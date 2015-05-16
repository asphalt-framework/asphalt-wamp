import os.path

from setuptools import setup

here = os.path.dirname(__file__)
readme_path = os.path.join(here, 'README.rst')
readme = open(readme_path).read()

setup(
    name='asphalt-wamp',
    use_scm_version={
        'local_scheme': 'dirty-tag'
    },
    description='WAMP client component for the Asphalt framework',
    long_description=readme,
    author='Alex Grönholm',
    author_email='alex.gronholm@nextday.fi',
    url='https://github.com/asphalt-framework/asphalt-wamp',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'
    ],
    license='Apache License 2.0',
    zip_safe=False,
    packages=[
        'asphalt.wamp'
    ],
    setup_requires=[
        'setuptools_scm >= 1.7.0'
    ],
    install_requires=[
        'asphalt >= 1.1, < 1.999',
        'asphalt-serialization >= 1.0, < 2.0',
        'autobahn >= 0.11.0'
    ],
    extras_require={
        'crossbar': 'crossbar >= 0.11.2'
    },
    entry_points={
        'asphalt.components': [
            'wamp = asphalt.wamp.component:WAMPComponent'
        ],
        'pytest11': [
            'crossbar = asphalt.wamp.pytest',
        ]
    }
)
