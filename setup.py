from setuptools import setup, find_packages

setup(
    name='tax_bracket_ingest',
    version='0.1.0',
    author='Hamza Olowu',
    packages=find_packages(),
    install_requires=[
        "beautifulsoup4==4.13.4",
        "boto3==1.38.36",
        "numpy==1.26.4",
        "pandas==2.3.0",
        "python-dotenv==1.1.0",
        "psycopg[binary]==3.3.3",
        "python-json-logger==3.3.0",
        "requests==2.32.4",
    ],
    description='A package to scrape, parse, and normalize IRS tax bracket data.'
)
