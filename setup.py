from setuptools import setup, find_packages

setup(
    name="saleor_vatrc",
    version="0.1",
    description="Implements VAT reverse charge in Saleor",
    author="Anna Sirota",
    author_email="anna@blender.org",
    install_requires=[
        'python-stdnum==1.17',
        'zeep==4.1.0',
    ],
    packages=find_packages(),
    entry_points={
        "saleor.plugins": [
            "saleor_vatrc = saleor_vatrc.plugin:VatReverseCharge"
        ]
    }
)
