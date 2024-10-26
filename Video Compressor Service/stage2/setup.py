# setup.py

from setuptools import setup, find_packages

setup(
    name="video_processing",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "psutil>=5.9.0",
        "ffmpeg-python>=0.2.0",
        "python-daemon>=3.0.1",
    ],
    extras_require={
        'server': [
            'python-daemon>=3.0.1',
        ],
        'client': [],
        'dev': [
            'pytest>=7.0.0',
            'black>=22.0.0',
            'flake8>=4.0.0',
            'mypy>=0.950',
        ],
    },
    entry_points={
        'console_scripts': [
            'video-process=video_processing.client.client:main',
            'video-server=video_processing.server.server:main',
        ],
    },
    author="author",
    author_email="taiu.engineer@example.com",
    description="Video processing service with client/server architecture",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="video, processing, ffmpeg, compression, server, client",
    project_urls={
        "Source": "https://github.com/yourusername/video_processing",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Multimedia :: Video",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    platforms=["any"],
    package_data={
        'video_processing': [
            'README.md',
        ],
    },
    include_package_data=True,
    zip_safe=False,
    options={
        'bdist_wheel': {
            'universal': True
        }
    },
)