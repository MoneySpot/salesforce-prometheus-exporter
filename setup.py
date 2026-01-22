from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

install_requires = [
    "click>=8.1.0",
    "click-plugins>=1.1.1",
    "prometheus-client>=0.17.0",
    "requests>=2.28.0",
    "Flask>=3.0.0",
    "Werkzeug>=3.0.0",
]

setup(
    name="salesforce-prometheus-exporter",
    version="1.0.1",
    author="Hector Droguett-Alfaro",
    author_email="hector@moneyspot.com.au",
    description="Prometheus exporter for Salesforce org limits and metrics using OAuth 2.0 Client Credentials flow.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/moneyspot/salesforce-prometheus-exporter",
    install_requires=install_requires,
    entry_points={"console_scripts": ["salesforce-exporter=cli.main:main"]},
    project_urls={
        "Bug Tracker": "https://github.com/moneyspot/salesforce-prometheus-exporter/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Monitoring",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
)
