from setuptools import setup

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
    entry_points={
        "saleor.plugins": [
            "vatrc = vatrc.plugin:VatReverseCharge"
        ]
    }
)
