from pathlib import Path

from setuptools import setup

setup(
    name='asphalt-wamp',
    use_scm_version={
        'version_scheme': 'post-release',
        'local_scheme': 'dirty-tag'
    },
    description='WAMP client component for the Asphalt framework',
    long_description=Path(__file__).parent.joinpath('README.rst').open().read(),
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
        'Programming Language :: Python :: 3.5',
        'Topic :: Communications'
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
        'asphalt >= 1.2, < 2.0',
        'asphalt-serialization[cbor] >= 1.1, < 2.0',
        'autobahn >= 0.12.1'
    ],
    extras_require={
        'crossbar': 'crossbar >= 0.12.1'
    },
    entry_points={
        'asphalt.components': [
            'wamp = asphalt.wamp.component:WAMPComponent'
        ]
    }
)
