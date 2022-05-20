from decimal import Decimal
from typing import TYPE_CHECKING, List, Dict, Iterable, Optional, Union, Tuple
import logging

from stdnum.eu import vat
import stdnum.exceptions

from prices import TaxedMoney, TaxedMoneyRange
from saleor.checkout.interface import CheckoutTaxedPricesData
from saleor.core.taxes import include_taxes_in_prices
from saleor.order.interface import OrderTaxedPricesData
from saleor.plugins.base_plugin import BasePlugin
from saleor.plugins.manager import get_plugins_manager


if TYPE_CHECKING:
    from saleor.account.models import Address
    from saleor.checkout.fetch import CheckoutInfo, CheckoutLineInfo
    from saleor.checkout.models import Checkout
    from saleor.discount import DiscountInfo
    from saleor.plugins.models import PluginConfiguration


logger = logging.getLogger(__name__)


class VatReverseCharge(BasePlugin):
    """Implement VAT reverse charge procedure.

    This plugins applies a VAT reverse charge to a checkout, if checkout is performed by
    a EU-VAT registered business.
    In this scenario, VAT is not charged and calculated VAT amount is deducted from
    checkout and lines totals, in case taxes were included into prices.

    In order to prove that checkout is performed by a EU-VAT registered business,
    this plugin attempts to validate the VATIN and stores the result of validation
    into checkout metadata.

    Note that this plugin does not perform tax calculations on its own,
    instead it relies on VAT calculations done by another plugin (currently VATLayer).

    Read more at
    https://europa.eu/youreurope/business/taxation/vat/cross-border-vat/index_en.htm#withintheeu
    """
    PLUGIN_ID = "blender.saleor_vatrc"
    PLUGIN_NAME = "VAT reverse charge"
    PLUGIN_DESCRIPTION = (
        "Applies a VAT reverse charge to a checkout, if checkout is performed by"
        " a EU-VAT registered business."
    )
    META_VATIN_KEY = "vatrc.vatin"
    META_VATIN_VALIDATED_KEY = "vatrc.vatin_validated"

    # This plugin depends on another plugin for calculating VAT
    VAT_PLUGIN_ID = 'mirumee.taxes.vatlayer'

    CONFIGURATION_PER_CHANNEL = True
    DEFAULT_ACTIVE = False

    @property
    def vat_plugin(self) -> "PluginConfiguration":
        manager = get_plugins_manager()
        plugins = manager.plugins_per_channel[self.channel.slug]
        return next((p for p in plugins if p.PLUGIN_ID == self.VAT_PLUGIN_ID), None)

    @property
    def vat_plugin_config(self) -> Dict[str, str]:
        # Convert to dict to easier get config elements of the plugin we depend on
        return {
            item["name"]: item["value"] for item in self.vat_plugin.configuration
        }

    def _skip_plugin(
        self,
        checkout_info: "CheckoutInfo",
        previous_value: Union[
            TaxedMoney,
            TaxedMoneyRange,
            Decimal,
            CheckoutTaxedPricesData,
            OrderTaxedPricesData,
        ],
    ) -> bool:
        if not self.active:
            return True

        # Skip when plugin that calculates VAT isn't active
        if not self.vat_plugin.active:
            return True

        # If taxes aren't included into prices, there's no reverse charge to apply.
        if not include_taxes_in_prices():
            return True

        # If there's no tax on the given prices
        if isinstance(previous_value, TaxedMoney):
            return previous_value.net == previous_value.gross
        if isinstance(previous_value, CheckoutTaxedPricesData):
            return (
                previous_value.price_with_sale.net
                == previous_value.price_with_sale.gross
            )
        if isinstance(previous_value, OrderTaxedPricesData):
            return (
                previous_value.price_with_discounts.net
                == previous_value.price_with_discounts.gross
            )

        return False

    def _get_seller_country_code(self) -> str:
        return self.vat_plugin_config.get("origin_country", "").upper()

    def _get_buyer_country_code(self, address: Optional["Address"]) -> str:
        return address.country.code if address else ""

    def _parse_vatin_value(self, vatin_metadata_value: str) -> Tuple[str]:
        try:
            vatin = vat.validate(vatin_metadata_value)
        except stdnum.exceptions.ValidationError:
            logger.exception('Invalid VATIN format')
            return '', ''
        vatin_country = vat.guess_country(vatin)
        if not vatin_country:
            return '', ''
        return next(iter(vatin_country)).upper(), vatin

    def _validate_vatin_value(self, vatin: str) -> bool:
        # Attempt to validate the number against VIES
        is_valid = False
        try:
            vies_response = vat.check_vies(vatin)
            logger.debug('Got response from VIES: %s', vies_response)
            is_valid = vies_response.valid
        except Exception:
            logger.exception('Unable to verify the VAT identification number')
            return False

        return is_valid

    def _validate_vatin_metadata(
        self,
        checkout: "Checkout",
        address: Optional["Address"],
    ) -> bool:
        vatin_metadata_value = checkout.get_value_from_metadata(self.META_VATIN_KEY)
        valid_vatin_previous = checkout.get_value_from_metadata(
            self.META_VATIN_VALIDATED_KEY
        )
        buyer_country = self._get_buyer_country_code(address)
        if not vatin_metadata_value and not valid_vatin_previous:
            return False

        vatin_country, vatin = self._parse_vatin_value(vatin_metadata_value)

        # Does not look like a valid VATIN
        if not vatin_country or not vatin or vatin_country != buyer_country:
            logger.debug('Invalid VATIN format: missing or mismatching country code')
            checkout.delete_value_from_metadata(self.META_VATIN_KEY)
            checkout.delete_value_from_metadata(self.META_VATIN_VALIDATED_KEY)
            checkout.save(update_fields=["metadata"])
        # Only validate the VATIN further if it differs from an already validated one:
        elif vatin != valid_vatin_previous and self._validate_vatin_value(vatin):
            logger.debug('Updating VATIN: %s', vatin)
            metadata_items = {
                self.META_VATIN_KEY: vatin,
                self.META_VATIN_VALIDATED_KEY: vatin,
            }
            checkout.store_value_in_metadata(items=metadata_items)
            checkout.save(update_fields=["metadata"])

    def _deduct_tax(self, previous_value: "TaxedMoney") -> "TaxedMoney":
        return TaxedMoney(gross=previous_value.net, net=previous_value.net)

    def calculate_checkout_total(
        self,
        checkout_info: "CheckoutInfo",
        lines: List["CheckoutLineInfo"],
        address: Optional["Address"],
        discounts: Iterable["DiscountInfo"],
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        if self._skip_plugin(checkout_info, previous_value):
            return previous_value

        checkout = checkout_info.checkout

        self._validate_vatin_metadata(checkout, address)

        valid_vatin = checkout.get_value_from_metadata(self.META_VATIN_VALIDATED_KEY)
        buyer_country_code = self._get_buyer_country_code(address)
        seller_country_code = self._get_seller_country_code()
        # If a valid VATIN is provided and the sale isn't within the same country,
        # reverse-charged applies.
        if valid_vatin and seller_country_code != buyer_country_code:
            # VAT is reverse-charged, so it must be excluded from total.
            return self._deduct_tax(previous_value)

        return previous_value

    def calculate_checkout_line_total(
        self,
        checkout_info: "CheckoutInfo",
        lines: List["CheckoutLineInfo"],
        checkout_line_info: "CheckoutLineInfo",
        address: Optional["Address"],
        discounts: Iterable["DiscountInfo"],
        previous_value: CheckoutTaxedPricesData,
    ) -> CheckoutTaxedPricesData:
        if self._skip_plugin(checkout_info, previous_value):
            return previous_value

        checkout = checkout_info.checkout

        self._validate_vatin_metadata(checkout, address)

        valid_vatin = checkout.get_value_from_metadata(self.META_VATIN_VALIDATED_KEY)
        buyer_country_code = self._get_buyer_country_code(address)
        seller_country_code = self._get_seller_country_code()
        # If a valid VATIN is provided and the sale isn't within the same country,
        # reverse-charged applies.
        if valid_vatin and seller_country_code != buyer_country_code:
            # VAT is reverse-charged, so it must be excluded from line total.
            return CheckoutTaxedPricesData(
                price_with_discounts=self._deduct_tax(
                    previous_value.price_with_discounts
                ),
                price_with_sale=self._deduct_tax(previous_value.price_with_sale),
                undiscounted_price=self._deduct_tax(previous_value.undiscounted_price),
            )
        return previous_value
