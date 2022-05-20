# VAT reverse charge plugin for Saleor

Implements VAT reverse charge procedure.

This plugins applies a VAT reverse charge to a checkout, if checkout is performed by
a EU-VAT registered business.
In this scenario, VAT is not charged and calculated VAT amount is deducted from
checkout and lines totals, in case taxes were included into prices.

## VATIN validation
In order to prove that checkout is performed by a EU-VAT registered business,
this plugin attempts to validate the VATIN and stores the result of validation
into checkout metadata.

Currently, it does this via [VIES](https://ec.europa.eu/taxation_customs/vies/faqvies.do#item_1).
Another option is to implement VATIN validation via VATLayer API as a fallback,
because this plugin already depends on Saleor's VATlayer plugin.

Note that this plugin does not perform tax calculations on its own,
instead it relies on VAT calculations done by another plugin (currently VATLayer).

Read more at [https://europa.eu/youreurope/business/taxation/vat/cross-border-vat/index_en.htm#withintheeu](https://europa.eu/youreurope/business/taxation/vat/cross-border-vat/index_en.htm#withintheeu)
