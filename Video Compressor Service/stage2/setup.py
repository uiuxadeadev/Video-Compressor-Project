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
            # サーバー固有の依存関係
        ],
        'client': [
            # クライアント固有の依存関係
        ]
    },
    author="author",
    author_email="taiu.engineer@example.com",
    description="Video processing service with client/server architecture",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
)