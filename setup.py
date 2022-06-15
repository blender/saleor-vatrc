from setuptools import setup

setup(
    name="saleor_vatrc",
    version="0.3",
    description="Implements VAT reverse charge in Saleor",
    author="Anna Sirota",
    author_email="anna@blender.org",
    install_requires=[
        'python-stdnum==1.17',
        'zeep==4.1.0',
    ],
    packages=["saleor_vatrc"],
    entry_points={
        "saleor.plugins": [
            "saleor_vatrc = saleor_vatrc.plugin:VatReverseCharge"
        ]
    }
)
