from setuptools import setup, find_packages

setup(
    name="batch_queue2",
    version="1.0.5",
    author="Neal Becker",
    author_email="ndbecker2@gmail.com",
    description="A Python-based batch queue manager",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://sr.ht/~ndbecker2/batch_queue2/",
    packages=find_packages(),  # Automatically includes 'batch_queue' directory
    entry_points={
        "console_scripts": [
            "batch_queue=batch_queue2.batch_queue:main",  # Correct path
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        # Add required dependencies here
    ],
    include_package_data=True,
)
